"""Honest quality and fairness snapshot from a completed offline batch."""

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from cloudserve.knowledge import resolve


def evaluate(input_path: Path, results_path: Path) -> dict:
    rows = json.loads(input_path.read_text())
    results = json.loads(results_path.read_text())
    source = {row["ticket_id"]: row for row in rows if isinstance(row, dict) and row.get("ticket_id")}
    if len(source) != len(rows) or len(results) != len(rows) or set(source) != {r["ticket_id"] for r in results}:
        raise ValueError("Input/result ticket IDs do not reconcile uniquely")
    confusion = defaultdict(Counter)
    calibration = [[] for _ in range(10)]
    brier_sum = 0.0
    protected = unsafe_auto = 0
    citation_total = citation_resolved = 0
    subgroup = defaultdict(lambda: {"count": 0, "intent_correct": 0, "answered": 0, "unsafe_auto": 0})
    latencies = []
    for result in results:
        row = source[result["ticket_id"]]
        labels = row.get("labels", {})
        actual = labels.get("intent")
        predicted = result["classification"]["intent"]
        correct = actual == predicted
        if actual:
            confusion[actual][predicted] += 1
        confidence = float(result["classification"]["intent_confidence"])
        if not 0 <= confidence <= 1:
            raise ValueError("Intent confidence outside [0,1]")
        calibration[min(9, int(confidence * 10))].append((confidence, int(correct)))
        brier_sum += (confidence - int(correct)) ** 2
        sent = result["terminal_state"] == "sent"
        unsafe = bool(labels.get("must_not_auto_respond") or labels.get("expected_route") == "escalate"
                      or labels.get("answerable_from_docs") is False)
        protected += int(unsafe)
        unsafe_auto += int(sent and unsafe)
        group = str(row.get("language_fluency") or "unknown")
        subgroup[group]["count"] += 1
        subgroup[group]["intent_correct"] += int(correct)
        subgroup[group]["answered"] += int(sent)
        subgroup[group]["unsafe_auto"] += int(sent and unsafe)
        for citation in result.get("citations", []):
            citation_total += 1
            found = resolve(citation["passage_id"], citation["source_version"])
            citation_resolved += int(bool(found and found.text == citation["text"] and found.doc_id == citation["doc_id"]))
        latencies.append(int(result["latency_ms"]))
    classes = sorted(set(confusion) | {pred for item in confusion.values() for pred in item})
    per_class = {}
    for name in classes:
        tp = confusion[name][name]
        support = sum(confusion[name].values())
        predicted_count = sum(item[name] for item in confusion.values())
        per_class[name] = {"tp": tp, "predicted": predicted_count, "support": support,
                           "precision": tp / predicted_count if predicted_count else None,
                           "recall": tp / support if support else None}
    precision_values = [item["precision"] for item in per_class.values() if item["precision"] is not None]
    n = len(results)
    ece = sum(len(bin_rows) / n * abs(sum(x for x, _ in bin_rows) / len(bin_rows) -
                  sum(y for _, y in bin_rows) / len(bin_rows)) for bin_rows in calibration if bin_rows)
    ordered = sorted(latencies)
    groups = {name: {**values, "intent_accuracy": values["intent_correct"] / values["count"],
                     "automation_coverage": values["answered"] / values["count"]}
              for name, values in subgroup.items()}
    coverage_values = [item["automation_coverage"] for item in groups.values()]
    return {
        "dataset": input_path.name, "evaluated_tickets": n,
        "classification_macro_precision": {"value": sum(precision_values) / len(precision_values) if precision_values else None,
                                           "classes_with_predictions": len(precision_values), "classes_total": len(classes),
                                           "target": 0.85},
        "classification_per_class": per_class,
        "intent_calibration": {"ece": ece, "brier": brier_sum / n, "labelled": n,
                               "model_declares_calibrated": all(r["classification"].get("calibrated") is True for r in results),
                               "target_ece": 0.05},
        "protected_false_auto": {"count": unsafe_auto, "protected_or_unsafe_tickets": protected},
        "citation_resolvability_proxy": {"resolved": citation_resolved, "citations": citation_total,
                                         "rate": citation_resolved / citation_total if citation_total else None,
                                         "semantic_support_target": 0.95},
        "hallucination_rate": {"value": None, "human_reviewed_responses": 0, "target_max": 0.05},
        "citation_semantic_accuracy": {"value": None, "human_reviewed_claims": 0, "target_min": 0.95},
        "latency": {"p95_ms": ordered[math.ceil(0.95 * n) - 1], "observations": n, "target_p95_ms": 3000,
                    "scope": "local offline processing, excluding customer delivery and Azure network"},
        "availability": {"value": None, "live_observation_hours": 0, "target_min": 0.995},
        "language_fluency_groups": groups,
        "language_fluency_auto_coverage_gap": max(coverage_values) - min(coverage_values) if len(coverage_values) > 1 else None,
        "limits": ["Development tickets trained the classifier; their precision is in-sample.",
                   "Visible validation labels informed policy tuning and are not untouched final gold.",
                   "Citation resolvability checks source identity and exact text, not semantic claim support.",
                   "ECE/Brier are diagnostic until a leakage-safe calibration set and independent test are used.",
                   "No live customer outcomes or availability observations are present."],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate(args.input, args.results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"tickets": report["evaluated_tickets"], "macro_precision": report["classification_macro_precision"]["value"],
                      "protected_false_auto": report["protected_false_auto"]["count"], "p95_ms": report["latency"]["p95_ms"]}))


if __name__ == "__main__":
    main()
