"""Validate two independent gold reviewers and summarize disagreements."""

import argparse
import json
from pathlib import Path

from cloudserve.knowledge import resolve
from evaluation.gold_eval import read_jsonl

PASSAGE_LABELS = {"relevant", "partly_relevant", "irrelevant"}
ROUTES = {"auto_respond", "escalate"}


def validate(rows: list[dict], expected_ids: set[str], reviewer_label: str) -> dict[str, dict]:
    indexed = {row["ticket_id"]: row for row in rows}
    if len(indexed) != len(rows) or set(indexed) != expected_ids:
        raise ValueError(f"{reviewer_label}: missing, extra or duplicate ticket IDs")
    for ticket_id, row in indexed.items():
        if not row.get("reviewer_name") or not row.get("reviewed_at"):
            raise ValueError(f"{reviewer_label} {ticket_id}: reviewer identity/date missing")
        if row.get("route") not in ROUTES or not isinstance(row.get("answerable_from_frozen_kb"), bool):
            raise ValueError(f"{reviewer_label} {ticket_id}: route or answerability missing")
        if row["route"] == "auto_respond" and not row["answerable_from_frozen_kb"]:
            raise ValueError(f"{reviewer_label} {ticket_id}: auto route contradicts no-answer label")
        passage_labels = row.get("passage_labels")
        if not isinstance(passage_labels, dict) or any(value not in PASSAGE_LABELS or resolve(pid) is None for pid, value in passage_labels.items()):
            raise ValueError(f"{reviewer_label} {ticket_id}: invalid passage label or ID")
        for span in row.get("supporting_spans", []):
            passage = resolve(span.get("passage_id", ""))
            text = span.get("exact_text", "")
            if passage is None or not text or text not in passage.text:
                raise ValueError(f"{reviewer_label} {ticket_id}: supporting span not found in frozen passage")
        if not isinstance(row.get("required_claims"), list) or not isinstance(row.get("forbidden_claims"), list):
            raise ValueError(f"{reviewer_label} {ticket_id}: claims must be lists")
    return indexed


def compare(a_path: Path, b_path: Path, gold_dir: Path) -> dict:
    queue = read_jsonl(gold_dir / "review_queue_v1.jsonl")
    expected = {row["ticket_id"] for row in queue}
    a = validate(read_jsonl(a_path), expected, "reviewer_a")
    b = validate(read_jsonl(b_path), expected, "reviewer_b")
    route_agree = answerable_agree = 0
    passage_agree = passage_total = 0
    disagreements = []
    for ticket_id in sorted(expected):
        left, right = a[ticket_id], b[ticket_id]
        route_agree += left["route"] == right["route"]
        answerable_agree += left["answerable_from_frozen_kb"] == right["answerable_from_frozen_kb"]
        all_passages = set(left["passage_labels"]) | set(right["passage_labels"])
        differing_passages = []
        for pid in sorted(all_passages):
            passage_total += 1
            same = left["passage_labels"].get(pid) == right["passage_labels"].get(pid)
            passage_agree += same
            if not same:
                differing_passages.append(pid)
        if (left["route"] != right["route"] or left["answerable_from_frozen_kb"] != right["answerable_from_frozen_kb"]
                or differing_passages or left["required_claims"] != right["required_claims"]
                or left["forbidden_claims"] != right["forbidden_claims"]):
            disagreements.append({"ticket_id": ticket_id, "route_a": left["route"], "route_b": right["route"],
                                  "answerable_a": left["answerable_from_frozen_kb"],
                                  "answerable_b": right["answerable_from_frozen_kb"],
                                  "differing_passage_ids": differing_passages,
                                  "required_claims_differ": left["required_claims"] != right["required_claims"],
                                  "forbidden_claims_differ": left["forbidden_claims"] != right["forbidden_claims"]})
    n = len(expected)
    return {"tickets": n, "route_exact_agreement": round(route_agree / n, 4),
            "answerability_exact_agreement": round(answerable_agree / n, 4),
            "passage_label_exact_agreement": round(passage_agree / passage_total, 4) if passage_total else None,
            "passage_comparisons": passage_total, "disagreement_count": len(disagreements),
            "disagreements": disagreements}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviewer-a", type=Path, required=True)
    parser.add_argument("--reviewer-b", type=Path, required=True)
    parser.add_argument("--gold-dir", type=Path, default=Path("evaluation/gold"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = compare(args.reviewer_a, args.reviewer_b, args.gold_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("tickets", "route_exact_agreement", "disagreement_count")}, indent=2))
