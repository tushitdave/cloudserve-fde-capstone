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
from cloudserve.service import TicketService


def score(rows: list[dict], results: list[dict]) -> dict:
    total = len(results)
    counts = {"processed": total, "answered": 0, "escalated": 0, "guardrail_blocked": 0}
    latencies = []
    by_class = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    retrieval_total = retrieval_hit = labelled = correct = 0
    urgency_total = urgency_correct = gold_auto = safe_auto = unsafe_auto = 0
    guardrail_by_type = defaultdict(int)
    for row, result in zip(rows, results):
        counts["answered" if result["terminal_state"] == "sent" else "escalated"] += 1
        counts["guardrail_blocked"] += bool(result["guardrail_findings"])
        for finding in result["guardrail_findings"]:
            guardrail_by_type[finding] += 1
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
        if labels.get("expected_route") == "auto_respond":
            gold_auto += 1
        if result["terminal_state"] == "sent" and labels:
            unsafe = (labels.get("must_not_auto_respond") is True
                      or labels.get("answerable_from_docs") is False
                      or labels.get("expected_route") == "escalate"
                      or (bool(labels.get("expected_doc_ids")) and not set(labels["expected_doc_ids"]) & {p["doc_id"] for p in result["citations"]}))
            unsafe_auto += bool(unsafe)
            safe_auto += not unsafe
        expected = set(labels.get("expected_doc_ids", []))
        if expected:
            retrieval_total += 1
            retrieval_hit += bool(expected & {p["doc_id"] for p in result["citations"]})
    precision_recall = {}
    for name, v in sorted(by_class.items()):
        precision_recall[name] = {
            "precision": round(v["tp"] / (v["tp"] + v["fp"]), 3) if v["tp"] + v["fp"] else 0,
            "recall": round(v["tp"] / (v["tp"] + v["fn"]), 3) if v["tp"] + v["fn"] else 0,
            "support": v["tp"] + v["fn"],
        }
    ordered = sorted(latencies)
    return {
        **counts,
        "decision_log_coverage": 1.0 if total else None,
        "automation_coverage": round(counts["answered"] / total, 3) if total else None,
        "escalation_rate": round(counts["escalated"] / total, 3) if total else None,
        "first_contact_resolution_proxy": round(counts["answered"] / total, 3) if total else None,
        "actual_first_contact_resolution": None,
        "mean_response_latency_ms": round(statistics.mean(latencies)) if latencies else None,
        "median_response_latency_ms": round(statistics.median(latencies)) if latencies else None,
        "p95_response_latency_ms": ordered[max(0, int(0.95 * len(ordered) + 0.9999) - 1)] if ordered else None,
        "classification_accuracy": round(correct / labelled, 3) if labelled else None,
        "urgency_accuracy": round(urgency_correct / urgency_total, 3) if urgency_total else None,
        "classification_per_class": precision_recall,
        "retrieval_cited_doc_hit_rate": round(retrieval_hit / retrieval_total, 3) if retrieval_total else None,
        "retrieval_cited_doc_hit_on_answered": round(retrieval_hit / counts["answered"], 3) if counts["answered"] else None,
        "gold_auto_respond_count": gold_auto,
        "safe_auto_count": safe_auto,
        "unsafe_auto_count": unsafe_auto,
        "auto_route_precision": round(safe_auto / (safe_auto + unsafe_auto), 3) if safe_auto + unsafe_auto else None,
        "guardrail_by_type": dict(guardrail_by_type),
        "private_data_detections": sum("possible_private_data" in r["guardrail_findings"] for r in results),
        "limitations": ["Development set trained the classifier and validation labels informed policy tuning; neither is an untouched final gold set.", "Cited-doc hit uses final answer citations rather than raw retrieval candidates.", "First-contact resolution and response time are offline proxies, not observed customer outcomes."],
    }


def run(input_path: Path, output_path: Path, mode: str = "extractive") -> dict:
    output_path.mkdir(parents=True, exist_ok=True)
    rows = json.loads(input_path.read_text())
    if not isinstance(rows, list):
        raise ValueError("Input must be a JSON list")
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
        "prompt_versions": {"answer": "extractive-v1" if mode == "extractive" else "azure-gpt4o-v1", "verification": "verification-v1"},
        "knowledge": knowledge_manifest(),
        "policy_versions": sorted({result["decision"]["policy_version"] for result in results}),
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
    print(json.dumps({key: metrics[key] for key in ("processed", "answered", "escalated", "guardrail_blocked", "terminal_reconciliation")}, indent=2))


if __name__ == "__main__":
    main()
