"""Score terminal results against frozen supplied seed labels, without false gold claims."""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from cloudserve.config import supplied
from cloudserve.knowledge import resolve


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def verify_manifest(manifest: dict, gold_dir: Path) -> None:
    for name, expected in manifest["source_sha256"].items():
        actual = hashlib.sha256(supplied(name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Frozen source changed: {name}; create a new gold version")
    for name, expected in manifest["artifact_sha256"].items():
        actual = hashlib.sha256((gold_dir / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Gold artifact changed: {name}; create a new gold version")


def score(results_path: Path, gold_dir: Path, require_adjudicated: bool = False) -> dict:
    manifest = json.loads((gold_dir / "manifest_v1.json").read_text())
    verify_manifest(manifest, gold_dir)
    labels = {row["ticket_id"]: row for row in read_jsonl(gold_dir / "supplied_labels_v1.jsonl")}
    review = read_jsonl(gold_dir / "review_queue_v1.jsonl")
    approved = sum(row["review_status"] == "approved" for row in review)
    if require_adjudicated and approved != len(review):
        raise ValueError(f"Only {approved}/{len(review)} passage/claim reviews approved")
    results = json.loads(results_path.read_text())
    if not isinstance(results, list):
        raise ValueError("Results must be a JSON list")
    ids = [row["ticket_id"] for row in results]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate ticket IDs in results")
    unknown = set(ids) - labels.keys()
    if unknown:
        raise ValueError(f"Unlabelled result IDs: {sorted(unknown)[:5]}")
    counts = Counter()
    by_intent = defaultdict(lambda: Counter())
    by_channel = defaultdict(lambda: Counter())
    citation_count = citation_resolved = 0
    sent_with_expected_doc = sent_expected_doc_hit = 0
    for result in results:
        gold = labels[result["ticket_id"]]
        actual_sent = result["terminal_state"] == "sent"
        expected_sent = gold["expected_route"] == "auto_respond"
        counts["intent_correct"] += result["classification"]["intent"] == gold["intent"]
        counts["urgency_correct"] += result["classification"]["urgency"] == gold["urgency"]
        counts["route_correct"] += actual_sent == expected_sent
        counts["gold_auto"] += expected_sent
        counts["sent"] += actual_sent
        counts["escalated"] += not actual_sent
        cited_docs = {p["doc_id"] for p in result.get("citations", [])}
        expected_docs = set(gold["expected_doc_ids"])
        if expected_docs:
            counts["expected_doc_cases"] += 1
            counts["cited_expected_doc"] += bool(cited_docs & expected_docs)
            if actual_sent:
                sent_with_expected_doc += 1
                sent_expected_doc_hit += bool(cited_docs & expected_docs)
        unsafe = (gold["must_not_auto_respond"] or not gold["answerable_from_docs"] or not expected_sent
                  or (bool(expected_docs) and not bool(cited_docs & expected_docs)))
        counts["unsafe_auto"] += actual_sent and unsafe
        counts["safe_auto"] += actual_sent and not unsafe
        for cited in result.get("citations", []):
            citation_count += 1
            passage = resolve(cited["passage_id"], cited["source_version"])
            citation_resolved += bool(passage and passage.doc_id == cited["doc_id"]
                                      and passage.source_version == cited["source_version"]
                                      and manifest["corpus"].get(cited["doc_id"]) == cited["source_version"])
        for group, bucket in ((gold["intent"], by_intent), (gold["channel"], by_channel)):
            bucket[group]["total"] += 1
            bucket[group]["sent"] += actual_sent
            bucket[group]["unsafe_auto"] += actual_sent and unsafe
    n = len(results)
    rate = lambda value, denominator: round(value / denominator, 4) if denominator else None
    return {"gold_version": manifest["gold_version"], "label_provenance": "supplied_capstone_dataset",
            "independent_holdout": False, "evaluated": n, "review_queue_size": len(review),
            "human_approved_reviews": approved, "intent_accuracy": rate(counts["intent_correct"], n),
            "urgency_accuracy": rate(counts["urgency_correct"], n),
            "route_accuracy": rate(counts["route_correct"], n),
            "auto_route_precision": rate(counts["safe_auto"], counts["sent"]),
            "auto_route_recall": rate(counts["safe_auto"], counts["gold_auto"]),
            "sent": counts["sent"], "escalated": counts["escalated"],
            "unsafe_auto_count": counts["unsafe_auto"],
            "expected_doc_cited_coverage_all_cases": rate(counts["cited_expected_doc"], counts["expected_doc_cases"]),
            "expected_doc_hit_on_sent": rate(sent_expected_doc_hit, sent_with_expected_doc),
            "expected_doc_cases": counts["expected_doc_cases"],
            "citation_id_version_resolution_rate": rate(citation_resolved, citation_count),
            "citation_count": citation_count,
            "passage_recall_at_k": None, "claim_support_rate": None, "hallucination_rate": None,
            "by_intent": {key: dict(value) for key, value in sorted(by_intent.items())},
            "by_channel": {key: dict(value) for key, value in sorted(by_channel.items())},
            "limitations": ["Development tickets trained the classifier; visible validation labels informed policy tuning.",
                            "Citation ID resolution is not semantic claim support.",
                            "Human passage and claim adjudication is pending."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--gold-dir", type=Path, default=Path("evaluation/gold"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-adjudicated", action="store_true")
    args = parser.parse_args()
    report = score(args.results, args.gold_dir, args.require_adjudicated)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("evaluated", "route_accuracy", "unsafe_auto_count", "human_approved_reviews")}, indent=2))
