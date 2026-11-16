import json
from pathlib import Path

import pytest

from cloudserve.config import APP_ROOT, supplied
from cloudserve.service import TicketService
from evaluation.gold_builder import build
from evaluation.gold_eval import score
from evaluation.review_compare import validate


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_gold_seed_is_reproducible_and_stratified(tmp_path):
    first = build(tmp_path / "first")
    second = build(tmp_path / "second")
    assert first["artifact_sha256"] == second["artifact_sha256"]
    assert first["supplied_label_count"] == 580
    assert first["review_queue_count"] == 120
    queue = read_jsonl(tmp_path / "first" / "review_queue_v1.jsonl")
    assert len({row["seed_labels"]["intent"] for row in queue}) == 22
    assert {row["channel"] for row in queue} == {"email", "chat", "docs_comment", "forum"}
    assert {row["seed_labels"]["expected_route"] for row in queue} == {"auto_respond", "escalate"}
    assert all(row["review_status"] == "pending" for row in queue)


def test_gold_scoring_is_labelled_seed_and_rejects_unapproved_claims(tmp_path):
    gold_dir = APP_ROOT / "evaluation" / "gold"
    row = json.loads(supplied("development_tickets.json").read_text())[25]
    result = TicketService(tmp_path / "tickets.sqlite").process({key: value for key, value in row.items() if key not in ("labels", "history", "customer_name")})
    results = tmp_path / "results.json"
    results.write_text(json.dumps([result.model_dump()]))
    report = score(results, gold_dir)
    assert report["evaluated"] == 1
    assert report["independent_holdout"] is False
    assert report["claim_support_rate"] is None
    with pytest.raises(ValueError, match="Only 0/120"):
        score(results, gold_dir, require_adjudicated=True)


def test_gold_scoring_rejects_modified_frozen_artifact(tmp_path):
    build(tmp_path)
    labels = tmp_path / "supplied_labels_v1.jsonl"
    labels.write_text(labels.read_text() + "\n")
    results = tmp_path / "results.json"
    results.write_text("[]")
    with pytest.raises(ValueError, match="Gold artifact changed"):
        score(results, tmp_path)
    with pytest.raises(FileExistsError, match="Frozen artifact differs"):
        build(tmp_path)


def test_reviewer_span_must_exist_in_frozen_passage():
    row = read_jsonl(APP_ROOT / "evaluation" / "gold" / "reviewer_a_template_v1.jsonl")[0]
    row.update({"reviewer_name": "Reviewer A", "reviewed_at": "2026-11-16T12:00:00Z",
                "route": "escalate", "answerable_from_frozen_kb": False,
                "passage_labels": {row["candidate_passages"][0]["passage_id"]: "irrelevant"}})
    assert validate([row], {row["ticket_id"]}, "a")
    row["supporting_spans"] = [{"passage_id": row["candidate_passages"][0]["passage_id"],
                                "exact_text": "This span does not occur in the frozen source."}]
    with pytest.raises(ValueError, match="supporting span not found"):
        validate([row], {row["ticket_id"]}, "a")
