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
from cloudserve.contracts import Ticket

INTENT_GRID = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
NOVELTY_GRID = [0.2, 0.25, 0.3, 0.35, 0.4, 0.45]
DOCUMENT_GRID = [0.12, 0.2, 0.3, 0.4]
EVIDENCE_GRID = [0.04, 0.06, 0.08, 0.10, 0.11, 0.12, 0.14, 0.16, 0.18, 0.20]
MAX_WRONG_ARTICLE_RATE = 0.05
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "manifests" / "threshold_selection_v1.json"
OUT_OF_SCOPE = ROOT / "evaluation" / "fixtures" / "out_of_scope_v1.json"


def _features(rows: list[dict]) -> list[dict]:
    agent = EvidenceAgent()
    saved = (policy.DOCUMENT_THRESHOLD, policy.EVIDENCE_THRESHOLD)
    features = []
    try:
        for row in rows:
            ticket = Ticket.model_validate({k: v for k, v in row.items() if k not in ("labels", "history", "customer_name")})
            classification = classify(ticket)
            blocked = bool(policy.fired_rules(ticket, classification)) or bool(guardrails.failures(guardrails.check_input(ticket.subject, ticket.body)))
            evidence = {}
            if not blocked:
                for doc_t in DOCUMENT_GRID:
                    for ev_t in EVIDENCE_GRID:
                        policy.DOCUMENT_THRESHOLD, policy.EVIDENCE_THRESHOLD = doc_t, ev_t
                        bundle = agent.gather(ticket, classification)
                        evidence[f"{doc_t}|{ev_t}"] = {"score": bundle.top_score, "doc": bundle.document_id,
                                                       "has_article": bundle.reason != "no_approved_article"}
            labels = row.get("labels") or {"intent": None, "must_not_auto_respond": True, "expected_route": "escalate",
                                           "answerable_from_docs": False, "expected_doc_ids": []}
            features.append({"ticket_id": row["ticket_id"], "intent_confidence": classification.intent_confidence,
                             "similarity": classification.nearest_training_similarity,
                             "intent_correct": classification.intent == labels["intent"], "blocked_by_rule": blocked,
                             "protected": labels["must_not_auto_respond"], "expected_route": labels["expected_route"],
                             "answerable": labels["answerable_from_docs"], "expected_docs": labels["expected_doc_ids"],
                             "language_fluency": row.get("language_fluency"), "evidence": evidence})
    finally:
        policy.DOCUMENT_THRESHOLD, policy.EVIDENCE_THRESHOLD = saved
    return features


def _outcome(features: list[dict], intent_t: float, doc_t: float, ev_t: float, novelty_t: float) -> dict:
    sent = protected_auto = wrong_article = label_escalate_auto = safe_auto = 0
    expected_auto = sum(f["expected_route"] == "auto_respond" for f in features)
    for f in features:
        if f["blocked_by_rule"] or f["similarity"] < novelty_t or f["intent_confidence"] < intent_t:
            continue
        ev = f["evidence"][f"{doc_t}|{ev_t}"]
        if not ev["has_article"] or ev["score"] < ev_t:
            continue
        sent += 1
        protected_auto += f["protected"]
        right_doc = ev["doc"] in f["expected_docs"]
        wrong_article += f["answerable"] and not right_doc
        label_escalate_auto += f["expected_route"] == "escalate" and not f["protected"]
        safe_auto += f["expected_route"] == "auto_respond" and right_doc
    n = len(features)
    return {"intent_confidence": intent_t, "min_training_similarity": novelty_t, "document_confidence": doc_t, "evidence_score": ev_t,
            "sent": sent, "coverage": round(sent / n, 4), "protected_false_auto": protected_auto,
            "wrong_article": wrong_article, "wrong_article_rate": round(wrong_article / sent, 4) if sent else 0.0,
            "label_escalate_but_sent": label_escalate_auto, "safe_auto": safe_auto,
            "safe_auto_recall": round(safe_auto / expected_auto, 4) if expected_auto else None}


def select() -> dict:
    _, calibration = split_rows()
    features = _features(calibration)
    out_of_scope = _features(json.loads(OUT_OF_SCOPE.read_text())["tickets"])
    grid = []
    for i in INTENT_GRID:
        for n in NOVELTY_GRID:
            for d in DOCUMENT_GRID:
                for e in EVIDENCE_GRID:
                    row = _outcome(features, i, d, e, n)
                    row["out_of_scope_sent"] = _outcome(out_of_scope, i, d, e, n)["sent"]
                    grid.append(row)
    eligible = [g for g in grid if g["protected_false_auto"] == 0 and g["out_of_scope_sent"] == 0
                and g["wrong_article_rate"] <= MAX_WRONG_ARTICLE_RATE]
    # Highest coverage; ties broken toward the most conservative thresholds.
    chosen = max(eligible, key=lambda g: (g["coverage"], -g["wrong_article_rate"], g["evidence_score"], g["min_training_similarity"],
                                          g["intent_confidence"], g["document_confidence"]))
    curve = {}
    for g in grid:
        if all(g[k] == chosen[k] for k in ("intent_confidence", "document_confidence", "min_training_similarity")):
            curve[str(g["evidence_score"])] = {k: g[k] for k in ("coverage", "wrong_article_rate", "protected_false_auto", "out_of_scope_sent", "safe_auto_recall")}
    return {
        "schema_version": "1.0", "dataset": "development calibration split (data/manifests/development_split_v1.json)",
        "visible_validation_used": False, "tickets": len(features), "classifier_version": MODEL_VERSION,
        "constraints": {"protected_false_auto": 0, "out_of_scope_fixture_sent": 0, "max_wrong_article_rate": MAX_WRONG_ARTICLE_RATE},
        "out_of_scope_fixture": "evaluation/fixtures/out_of_scope_v1.json", "out_of_scope_tickets": len(out_of_scope),
        "objective": "maximise automatic coverage subject to constraints; tie-break toward stricter thresholds",
        "chosen": chosen, "evidence_risk_coverage_curve_at_other_chosen_thresholds": curve,
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
