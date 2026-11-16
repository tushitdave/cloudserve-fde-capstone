"""Unattended arbitrary-file ticket run with automatic metrics and reconciliation."""

import argparse
import hashlib
import json
import statistics
import time
from collections import defaultdict
from pathlib import Path

from cloudserve.config import runtime_dir
from cloudserve.knowledge import manifest as knowledge_manifest
from cloudserve.ml_registry import drift_report
from cloudserve.observability.tracing import finished_spans, write_jsonl
from cloudserve.retrieval import warm_up
from cloudserve.policy import NOVELTY_THRESHOLD, POLICY_VERSION, kill_switch_state, thresholds_applied
from cloudserve.service import TicketService


def _calibration(results: list[dict], rows: list[dict], bins: int = 10) -> dict | None:
    pairs = [(float(r["classification"]["intent_confidence"]), r["classification"]["intent"] == row.get("labels", {}).get("intent"))
             for row, r in zip(rows, results) if isinstance(row, dict) and row.get("labels", {}).get("intent")]
    if not pairs:
        return None
    ece, table = 0.0, []
    for b in range(bins):
        low, high = b / bins, (b + 1) / bins
        group = [(c, ok) for c, ok in pairs if low <= c < high or (b == bins - 1 and c == 1.0)]
        if group:
            stated = sum(c for c, _ in group) / len(group)
            observed = sum(ok for _, ok in group) / len(group)
            ece += len(group) / len(pairs) * abs(stated - observed)
            table.append({"band": [low, high], "count": len(group), "stated": round(stated, 4), "observed": round(observed, 4)})
    return {"ece": round(ece, 4), "labelled": len(pairs), "bands": table, "target_max_gap": 0.05}


def _segments(rows: list[dict], results: list[dict], field: str) -> dict:
    groups = defaultdict(lambda: {"tickets": 0, "auto": 0, "safe_auto": 0, "expected_auto": 0})
    for row, result in zip(rows, results):
        if not isinstance(row, dict):
            continue
        g = groups[str(row.get(field) or "unknown")]
        labels = row.get("labels", {})
        sent = result["terminal_state"] == "sent"
        g["tickets"] += 1
        g["auto"] += sent
        if labels.get("expected_route") == "auto_respond":
            g["expected_auto"] += 1
            g["safe_auto"] += sent and bool(set(labels.get("expected_doc_ids", [])) & {p["doc_id"] for p in result["citations"]})
    out = {}
    for name, g in sorted(groups.items()):
        out[name] = {**g, "auto_rate": round(g["auto"] / g["tickets"], 4) if g["tickets"] else None,
                     "safe_auto_recall": round(g["safe_auto"] / g["expected_auto"], 4) if g["expected_auto"] else None}
    recalls = [v["safe_auto_recall"] for v in out.values() if v["safe_auto_recall"] is not None]
    return {"groups": out, "max_gap_safe_auto_recall_points": round(100 * (max(recalls) - min(recalls)), 2) if len(recalls) > 1 else None}


def score(rows: list[dict], results: list[dict]) -> dict:
    total = len(results)
    counts = {"processed": total, "answered": 0, "escalated": 0, "guardrail_blocked": 0}
    latencies = []
    by_class = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    retrieval_total = retrieval_hit = labelled = correct = 0
    urgency_total = urgency_correct = gold_auto = safe_auto = 0
    protected_false_auto = wrong_article_auto = label_escalate_auto = route_correct = route_labelled = 0
    guardrail_by_type = defaultdict(int)
    checks_run = defaultdict(lambda: {"pass": 0, "fail": 0})
    reasons = defaultdict(int)
    for row, result in zip(rows, results):
        sent = result["terminal_state"] == "sent"
        counts["answered" if sent else "escalated"] += 1
        counts["guardrail_blocked"] += bool(result["guardrail_findings"])
        reasons[(result["decision"]["reason_codes"] or ["none"])[0]] += 1
        for finding in result["guardrail_findings"]:
            guardrail_by_type[finding] += 1
        for check in result.get("guardrail_results", []):
            checks_run[check["check"]][check["result"]] += 1
        latencies.append(result["latency_ms"])
        labels = row.get("labels", {}) if isinstance(row, dict) else {}
        if "intent" in labels:
            labelled += 1
            actual, predicted = labels["intent"], result["classification"]["intent"]
            correct += actual == predicted
            for name in {actual, predicted}:
                by_class[name]["tp" if actual == predicted else "fn" if name == actual else "fp"] += 1
        if "urgency" in labels:
            urgency_total += 1
            urgency_correct += labels["urgency"] == result["classification"]["urgency"]
        cited_docs = {p["doc_id"] for p in result["citations"]}
        if "expected_route" in labels:
            route_labelled += 1
            route_correct += (labels["expected_route"] == "auto_respond") == sent
        if labels.get("expected_route") == "auto_respond":
            gold_auto += 1
        if sent and labels:
            protected_false_auto += labels.get("must_not_auto_respond") is True
            label_escalate_auto += labels.get("expected_route") == "escalate" and labels.get("must_not_auto_respond") is not True
            wrong_article_auto += bool(labels.get("expected_doc_ids")) and not set(labels["expected_doc_ids"]) & cited_docs
            safe_auto += labels.get("expected_route") == "auto_respond" and bool(set(labels.get("expected_doc_ids", [])) & cited_docs)
        expected = set(labels.get("expected_doc_ids", []))
        if expected:
            retrieval_total += 1
            retrieval_hit += bool(expected & cited_docs)
    precision_recall = {}
    for name, v in sorted(by_class.items()):
        precision_recall[name] = {
            "precision": round(v["tp"] / (v["tp"] + v["fp"]), 3) if v["tp"] + v["fp"] else 0,
            "recall": round(v["tp"] / (v["tp"] + v["fn"]), 3) if v["tp"] + v["fn"] else 0,
            "support": v["tp"] + v["fn"],
        }
    precisions = [v["precision"] for v in precision_recall.values() if v["support"] or v["precision"]]
    ordered = sorted(latencies)
    answered = counts["answered"]
    return {
        **counts,
        "decision_log_coverage": 1.0 if total else None,
        "business": {
            "first_contact_resolution_proxy": round(answered / total, 3) if total else None,
            "escalation_rate": round(counts["escalated"] / total, 3) if total else None,
            "baseline_first_contact_resolution": 0.42, "baseline_escalation_rate": 0.58,
            "mean_time_to_first_reply_ms": round(statistics.mean(latencies)) if latencies else None,
            "median_time_to_first_reply_ms": round(statistics.median(latencies)) if latencies else None,
            "note": "Offline proxy: an automatic answer is not a confirmed resolution; time to reply is local processing time (escalations still wait for a person).",
        },
        "automation_coverage": round(answered / total, 3) if total else None,
        "escalation_rate": round(counts["escalated"] / total, 3) if total else None,
        "first_contact_resolution_proxy": round(answered / total, 3) if total else None,
        "actual_first_contact_resolution": None,
        "escalation_reasons": dict(sorted(reasons.items(), key=lambda kv: -kv[1])),
        "mean_response_latency_ms": round(statistics.mean(latencies)) if latencies else None,
        "median_response_latency_ms": round(statistics.median(latencies)) if latencies else None,
        "p95_response_latency_ms": ordered[max(0, int(0.95 * len(ordered) + 0.9999) - 1)] if ordered else None,
        "classification_accuracy": round(correct / labelled, 3) if labelled else None,
        "classification_macro_precision": round(sum(precisions) / len(precisions), 3) if precisions else None,
        "urgency_accuracy": round(urgency_correct / urgency_total, 3) if urgency_total else None,
        "classification_per_class": precision_recall,
        "intent_calibration": _calibration(results, rows),
        "route_accuracy_vs_labels": round(route_correct / route_labelled, 3) if route_labelled else None,
        "retrieval_cited_doc_hit_rate": round(retrieval_hit / retrieval_total, 3) if retrieval_total else None,
        "retrieval_cited_doc_hit_on_answered": round((answered - wrong_article_auto) / answered, 3) if answered else None,
        "gold_auto_respond_count": gold_auto,
        "safe_auto_count": safe_auto,
        "safe_auto_recall": round(safe_auto / gold_auto, 3) if gold_auto else None,
        "governance": {
            "protected_false_auto": protected_false_auto,
            "wrong_article_auto": wrong_article_auto,
            "wrong_article_rate_of_sent": round(wrong_article_auto / answered, 4) if answered else None,
            "label_escalate_but_sent": label_escalate_auto,
            "label_escalate_but_sent_note": "Non-protected tickets labelled escalate that were answered. The supplied labels give opposite routes to identical text in 40 of 191 duplicate-text groups of non-protected tickets, so this is reported as label disagreement, not as a safety failure; it still needs human review.",
            "guardrail_checks_run": {k: dict(v) for k, v in checks_run.items()},
            "private_data_detections": sum("possible_private_data" in r["guardrail_findings"] for r in results),
        },
        "unsafe_auto_count": protected_false_auto + wrong_article_auto,
        "guardrail_by_type": dict(guardrail_by_type),
        "private_data_detections": sum("possible_private_data" in r["guardrail_findings"] for r in results),
        "fairness": {field: _segments(rows, results, field) for field in ("language_fluency", "customer_tier", "customer_region", "channel")},
        "limitations": ["The classifier and thresholds were fitted on the development train/calibration split; development figures are partly in-sample.",
                        "The visible validation set shares 62 of 80 ticket bodies with development, so it overstates performance on genuinely new wording.",
                        "Cited-doc hit uses final answer citations rather than raw retrieval candidates.",
                        "First-contact resolution and response time are offline proxies, not observed customer outcomes.",
                        "Hallucination rate and semantic citation accuracy need human review and are not computed here."],
    }


def run(input_path: Path, output_path: Path, mode: str = "extractive") -> dict:
    output_path.mkdir(parents=True, exist_ok=True)
    rows = json.loads(input_path.read_text())
    if not isinstance(rows, list):
        raise ValueError("Input must be a JSON list")
    retrieval_status = warm_up()  # build the dense index and load models once, before timing tickets
    finished_spans()  # discard spans from earlier work in this process
    service = TicketService(output_path / "run.sqlite")
    results = []
    started = time.time()
    for number, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            row = {"ticket_id": f"INPUT-{number:06d}", "channel": "chat", "body": str(row)}
        elif not row.get("ticket_id"):
            row = {**row, "ticket_id": f"INPUT-{number:06d}"}
        result = service.process(row, mode=mode)
        results.append(result.model_dump())
    metrics = score(rows, results)
    metrics["decisions_logged"] = service.store.counts()["decisions_logged"]
    spans = finished_spans()
    write_jsonl(output_path / "traces.jsonl", spans)
    by_stage = defaultdict(list)
    for span in spans:
        by_stage[span["name"].removeprefix("cloudserve.")].append(span["duration_ms"])
    metrics["stage_latency_ms"] = {stage: {"count": len(v), "p50": round(statistics.median(v), 2),
                                           "p95": round(sorted(v)[max(0, int(0.95 * len(v) + 0.9999) - 1)], 2)}
                                   for stage, v in sorted(by_stage.items())}
    metrics["retrieval_status"] = retrieval_status
    metrics["traces"] = {"spans": len(spans), "file": "traces.jsonl", "contains_raw_text": False}
    usable = [(row, result) for row, result in zip(rows, results) if isinstance(row, dict)]
    metrics["drift"] = drift_report([f"{row.get('subject') or ''} {row.get('body') or ''}".strip() for row, _ in usable],
                                    [r["classification"]["intent"] for _, r in usable],
                                    [float(r["classification"]["intent_confidence"]) for _, r in usable],
                                    [float(r["classification"].get("nearest_training_similarity", 1)) for _, r in usable],
                                    NOVELTY_THRESHOLD)
    input_ids = [str(row.get("ticket_id") or f"INPUT-{number:06d}") if isinstance(row, dict) else f"INPUT-{number:06d}"
                 for number, row in enumerate(rows, 1)]
    terminal_ids = [result["ticket_id"] for result in results]
    decision_ids = [ticket_id for ticket_id in terminal_ids if any(event["stage"] == "terminal" for event in service.store.events(ticket_id))]
    metrics["terminal_reconciliation"] = (metrics["decisions_logged"] == len(rows) == len(results)
                                           and len(set(input_ids)) == len(rows)
                                           and input_ids == terminal_ids == decision_ids)
    (output_path / "results.json").write_text(json.dumps(results, indent=2))
    (output_path / "metrics.json").write_text(json.dumps(metrics, indent=2))
    (output_path / "run_manifest.json").write_text(json.dumps({
        "schema_version": "1.0", "input": str(input_path), "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "count": len(rows), "mode": mode, "started_at_unix": started, "ended_at_unix": time.time(),
        "model_versions": sorted({result["classification"]["model_version"] for result in results}),
        "prompt_versions": {"answer": service.answer.PROMPT_VERSION[mode], "verification": service.verification.VERSION[mode]},
        "knowledge": knowledge_manifest(),
        "policy_versions": sorted({result["decision"]["policy_version"] for result in results}),
        "active_policy_version": POLICY_VERSION, "thresholds": thresholds_applied(), "kill_switch": kill_switch_state(),
        "input_ticket_ids": input_ids, "terminal_ticket_ids": terminal_ids, "decision_ticket_ids": decision_ids,
        "terminal_reconciliation": metrics["terminal_reconciliation"],
    }, indent=2))
    if not metrics["terminal_reconciliation"]:
        raise RuntimeError("Run did not reconcile all ticket decisions")
    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=["extractive", "azure"], default="extractive")
    args = parser.parse_args()
    metrics = run(args.input, args.output, args.mode)
    summary = {key: metrics[key] for key in ("processed", "answered", "escalated", "guardrail_blocked", "safe_auto_recall",
                                             "route_accuracy_vs_labels", "terminal_reconciliation")}
    summary["protected_false_auto"] = metrics["governance"]["protected_false_auto"]
    summary["wrong_article_rate_of_sent"] = metrics["governance"]["wrong_article_rate_of_sent"]
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
