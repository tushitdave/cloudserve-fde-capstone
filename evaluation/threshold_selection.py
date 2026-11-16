"""Risk-coverage threshold selection on the held-out calibration split only.

The classifier and intent→article map are fitted on the train split; this script
replays the routing decision for every calibration ticket over a grid of
(intent, document, evidence) thresholds and chooses the highest automatic coverage
that keeps (a) zero protected false-auto and (b) a wrong-article rate ≤ 5% of sent
answers. The 80 visible validation tickets are not read.

    PYTHONPATH=src:. python -m evaluation.threshold_selection
"""

import argparse
import json
from pathlib import Path

from cloudserve import guardrails, policy
from cloudserve.agents import EvidenceAgent
from cloudserve.classifier import MODEL_VERSION, classify, split_rows
from cloudserve.retrieval import warm_up
from cloudserve.contracts import Ticket

INTENT_GRID = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
NOVELTY_GRID = [0.2, 0.25, 0.3, 0.35, 0.4, 0.45]
DOCUMENT_GRID = [0.12, 0.2, 0.3, 0.4]
EVIDENCE_GRID = {
    "lexical": [0.04, 0.06, 0.08, 0.10, 0.11, 0.12, 0.14, 0.16, 0.18, 0.20],
    "dense": [0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60],
    "hybrid": [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45],
    "hybrid_rerank": [0.001, 0.005, 0.01, 0.05, 0.10, 0.20, 0.30, 0.50],
}
STRATEGY_COST = {"lexical": 0, "dense": 1, "hybrid": 2, "hybrid_rerank": 3}
MAX_WRONG_ARTICLE_RATE = 0.05
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "manifests" / "threshold_selection_v1.json"
OUT_OF_SCOPE = ROOT / "evaluation" / "fixtures" / "out_of_scope_v1.json"


def _features(rows: list[dict]) -> list[dict]:
    """Per ticket: rule/guardrail block, classifier scores, and both bounded searches for every strategy and document threshold."""
    agent = EvidenceAgent()
    saved = policy.DOCUMENT_THRESHOLD
    features = []
    try:
        for row in rows:
            ticket = Ticket.model_validate({k: v for k, v in row.items() if k not in ("labels", "history", "customer_name")})
            classification = classify(ticket)
            blocked = bool(policy.fired_rules(ticket, classification)) or bool(guardrails.failures(guardrails.check_input(ticket.subject, ticket.body)))
            searches = {}
            if not blocked:
                for doc_t in DOCUMENT_GRID:
                    policy.DOCUMENT_THRESHOLD = doc_t
                    plan = agent.plan(ticket, classification)
                    for strategy in EVIDENCE_GRID:
                        if plan.path != "approved_document":
                            searches[f"{doc_t}|{strategy}"] = None
                            continue
                        allowed = set(plan.allowed_doc_ids)
                        first, used, _ = agent.search(plan.query, allowed, strategy)
                        second, _, _ = agent.search(f"{classification.intent.replace('_', ' ')} {plan.query}", allowed, strategy)
                        searches[f"{doc_t}|{strategy}"] = {
                            "used": used,
                            "first": (first[0].score, first[0].doc_id) if first else (0.0, None),
                            "second": (second[0].score, second[0].doc_id) if second else (0.0, None)}
            labels = row.get("labels") or {"intent": None, "must_not_auto_respond": True, "expected_route": "escalate",
                                           "answerable_from_docs": False, "expected_doc_ids": []}
            features.append({"ticket_id": row["ticket_id"], "intent_confidence": classification.intent_confidence,
                             "similarity": classification.nearest_training_similarity, "blocked_by_rule": blocked,
                             "protected": labels["must_not_auto_respond"], "expected_route": labels["expected_route"],
                             "answerable": labels["answerable_from_docs"], "expected_docs": labels["expected_doc_ids"],
                             "language_fluency": row.get("language_fluency"), "searches": searches})
    finally:
        policy.DOCUMENT_THRESHOLD = saved
    return features


def _evidence(search: dict, ev_t: float) -> tuple[float, str | None]:
    """Replays EvidenceAgent.gather: keep the first search if it clears the threshold, else the better of the two."""
    first, second = search["first"], search["second"]
    if first[0] >= ev_t:
        return first
    return second if second[0] > first[0] else first


def _outcome(features: list[dict], intent_t: float, doc_t: float, strategy: str, ev_t: float, novelty_t: float) -> dict:
    sent = protected_auto = wrong_article = label_escalate_auto = safe_auto = 0
    groups = {}
    expected_auto = sum(f["expected_route"] == "auto_respond" for f in features)
    for f in features:
        group = groups.setdefault(f.get("language_fluency") or "unknown", [0, 0])
        group[0] += f["expected_route"] == "auto_respond"
        if f["blocked_by_rule"] or f["similarity"] < novelty_t or f["intent_confidence"] < intent_t:
            continue
        search = f["searches"].get(f"{doc_t}|{strategy}")
        if search is None:
            continue
        score, doc = _evidence(search, ev_t)
        if score < ev_t:
            continue
        sent += 1
        protected_auto += f["protected"]
        right_doc = doc in f["expected_docs"]
        wrong_article += f["answerable"] and not right_doc
        label_escalate_auto += f["expected_route"] == "escalate" and not f["protected"]
        good = f["expected_route"] == "auto_respond" and right_doc
        safe_auto += good
        group[1] += good
    n = len(features)
    recalls = {k: v[1] / v[0] for k, v in groups.items() if v[0]}
    return {"retrieval_strategy": strategy, "intent_confidence": intent_t, "min_training_similarity": novelty_t,
            "document_confidence": doc_t, "evidence_score": ev_t,
            "sent": sent, "coverage": round(sent / n, 4), "protected_false_auto": protected_auto,
            "wrong_article": wrong_article, "wrong_article_rate": round(wrong_article / sent, 4) if sent else 0.0,
            "label_escalate_but_sent": label_escalate_auto, "safe_auto": safe_auto,
            "safe_auto_recall": round(safe_auto / expected_auto, 4) if expected_auto else None,
            "fluency_gap_points": round(100 * (max(recalls.values()) - min(recalls.values())), 2) if len(recalls) > 1 else None}


def select() -> dict:
    warm_up()
    _, calibration = split_rows()
    features = _features(calibration)
    out_of_scope = _features(json.loads(OUT_OF_SCOPE.read_text())["tickets"])
    grid = []
    for strategy, evidence_grid in EVIDENCE_GRID.items():
        for i in INTENT_GRID:
            for n in NOVELTY_GRID:
                for d in DOCUMENT_GRID:
                    for e in evidence_grid:
                        row = _outcome(features, i, d, strategy, e, n)
                        row["out_of_scope_sent"] = _outcome(out_of_scope, i, d, strategy, e, n)["sent"]
                        grid.append(row)
    eligible = [g for g in grid if g["protected_false_auto"] == 0 and g["out_of_scope_sent"] == 0
                and g["wrong_article_rate"] <= MAX_WRONG_ARTICLE_RATE]
    # Highest coverage; then higher safe-auto recall; then the cheaper strategy; then stricter thresholds.
    chosen = max(eligible, key=lambda g: (g["coverage"], g["safe_auto_recall"], -STRATEGY_COST[g["retrieval_strategy"]],
                                          -g["wrong_article_rate"], g["evidence_score"], g["min_training_similarity"],
                                          g["intent_confidence"], g["document_confidence"]))
    best_per_strategy = {}
    for strategy in EVIDENCE_GRID:
        options = [g for g in eligible if g["retrieval_strategy"] == strategy]
        if options:
            best = max(options, key=lambda g: (g["coverage"], g["safe_auto_recall"], -g["wrong_article_rate"], g["evidence_score"]))
            best_per_strategy[strategy] = {k: best[k] for k in ("coverage", "safe_auto_recall", "wrong_article_rate",
                                                                "fluency_gap_points", "evidence_score", "intent_confidence",
                                                                "min_training_similarity", "document_confidence")}
    curve = {}
    for g in grid:
        if all(g[k] == chosen[k] for k in ("retrieval_strategy", "intent_confidence", "document_confidence", "min_training_similarity")):
            curve[str(g["evidence_score"])] = {k: g[k] for k in ("coverage", "wrong_article_rate", "protected_false_auto", "out_of_scope_sent", "safe_auto_recall")}
    return {
        "schema_version": "1.0", "dataset": "development calibration split (data/manifests/development_split_v1.json)",
        "visible_validation_used": False, "tickets": len(features), "classifier_version": MODEL_VERSION,
        "constraints": {"protected_false_auto": 0, "out_of_scope_fixture_sent": 0, "max_wrong_article_rate": MAX_WRONG_ARTICLE_RATE},
        "out_of_scope_fixture": "evaluation/fixtures/out_of_scope_v1.json", "out_of_scope_tickets": len(out_of_scope),
        "objective": "maximise automatic coverage subject to constraints; tie-break on safe-auto recall, then the cheaper retrieval strategy, then stricter thresholds",
        "chosen": chosen, "best_per_strategy": best_per_strategy,
        "evidence_risk_coverage_curve_at_other_chosen_thresholds": curve,
        "grid_size": len(grid), "eligible_configurations": len(eligible),
        "label_noise_note": ("Identical ticket text carries different expected_route/answerable labels in 40 of 191 duplicate-text groups of non-protected tickets "
                             "(dev+validation). label_escalate_but_sent therefore cannot be driven to zero by any text-based rule and is "
                             "reported, not optimised."),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = select()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["chosen"], indent=2))


if __name__ == "__main__":
    main()
