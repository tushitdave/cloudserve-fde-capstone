"""Compare lexical, dense (Chroma + MiniLM), hybrid and hybrid + cross-encoder retrieval.

Research/02 and ADR-004: "compare dense, lexical and hybrid; add reranking only if
it improves labelled retrieval within latency". Measured on the held-out development
calibration split (the selection set) and reported on visible validation for
information only. Document-level Recall@k and MRR@5 use the supplied
`expected_doc_ids`; passage-level gold is not yet human-adjudicated.

    PYTHONPATH=src:. python -m evaluation.retrieval_comparison
"""

import argparse
import json
import statistics
import time
from pathlib import Path

from cloudserve.classifier import approved_docs_by_intent, classify, split_rows
from cloudserve.config import supplied
from cloudserve.contracts import Ticket
from cloudserve.knowledge import retrieve_with_strategy
from cloudserve.retrieval import DENSE_MODEL, RERANK_MODEL, STRATEGIES, warm_up

OUTPUT = Path(__file__).resolve().parents[1] / "data" / "manifests" / "retrieval_comparison_v1.json"


def _eligible(rows):
    return [r for r in rows if r["labels"]["answerable_from_docs"] and r["labels"]["expected_doc_ids"]
            and not r["labels"]["must_not_auto_respond"]]


def evaluate(rows: list[dict], scoped: bool) -> dict:
    out = {}
    for strategy in STRATEGIES:
        hit1 = hit3 = 0
        rr = 0.0
        latencies, by_fluency, used = [], {}, set()
        for row in rows:
            ticket = Ticket.model_validate({k: v for k, v in row.items() if k not in ("labels", "history", "customer_name")})
            query = f"{ticket.subject} {ticket.body}".strip()
            allowed = approved_docs_by_intent().get(classify(ticket).intent) if scoped else None
            started = time.perf_counter()
            passages, strategy_used, _ = retrieve_with_strategy(query, limit=10, allowed_doc_ids=allowed, strategy=strategy)
            latencies.append((time.perf_counter() - started) * 1000)
            used.add(strategy_used)
            docs = list(dict.fromkeys(p.doc_id for p in passages))
            expected = set(row["labels"]["expected_doc_ids"])
            first = next((i for i, d in enumerate(docs[:5]) if d in expected), None)
            hit1 += bool(docs[:1] and docs[0] in expected)
            hit3 += bool(set(docs[:3]) & expected)
            rr += 1 / (first + 1) if first is not None else 0
            group = by_fluency.setdefault(row.get("language_fluency", "unknown"), [0, 0])
            group[0] += 1
            group[1] += bool(docs[:1] and docs[0] in expected)
        n = len(rows)
        ordered = sorted(latencies)
        out[strategy] = {"tickets": n, "doc_hit_at_1": round(hit1 / n, 4), "doc_recall_at_3": round(hit3 / n, 4),
                         "mrr_at_5": round(rr / n, 4), "latency_ms_median": round(statistics.median(latencies), 1),
                         "latency_ms_p95": round(ordered[max(0, int(0.95 * n + 0.9999) - 1)], 1),
                         "hit_at_1_by_fluency": {k: round(v[1] / v[0], 4) for k, v in sorted(by_fluency.items())},
                         "strategy_actually_used": sorted(used)}
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    status = warm_up()
    _, calibration = split_rows()
    validation = json.loads(supplied("validation_tickets.json").read_text())
    report = {"schema_version": "1.0", "dense_model": DENSE_MODEL, "rerank_model": RERANK_MODEL, "warm_up": status,
              "selection_set": "development calibration split", "metric_level": "document (expected_doc_ids)",
              "calibration_unscoped": evaluate(_eligible(calibration), scoped=False),
              "calibration_intent_scoped": evaluate(_eligible(calibration), scoped=True),
              "validation_unscoped_information_only": evaluate(_eligible(validation), scoped=False)}
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    for key in ("calibration_unscoped", "calibration_intent_scoped", "validation_unscoped_information_only"):
        print(key)
        for strategy, values in report[key].items():
            print(f"  {strategy:14s} hit@1 {values['doc_hit_at_1']:.3f}  R@3 {values['doc_recall_at_3']:.3f}  MRR {values['mrr_at_5']:.3f}"
                  f"  p95 {values['latency_ms_p95']:.0f} ms  fluency {values['hit_at_1_by_fluency']}")


if __name__ == "__main__":
    main()
