"""Acceptance evidence for channel fidelity and arbitrary-file unattended runs."""

import json

from cloudserve.service import TicketService
from evaluation.harness import run


def test_four_channel_normalization_preserves_original_text(tmp_path):
    service = TicketService(tmp_path / "channels.sqlite")
    for channel in ("email", "chat", "docs_comment", "forum"):
        source = {"ticket_id": f"FIDELITY-{channel}", "channel": channel,
                  "subject": "Ação / 設定", "body": "I cannot sign in — कृपया मदद करें 🚀"}
        result = service.process(source)
        assert result.channel == channel
        normalized = service.store.events(result.ticket_id)[0]
        assert normalized["stage"] == "normalized"
        assert normalized["payload"]["channel"] == source["channel"]
        assert normalized["payload"]["subject"] == source["subject"]
        assert normalized["payload"]["body"] == source["body"]
    empty = service.process({"ticket_id": "FIDELITY-empty", "channel": "forum", "body": ""})
    assert empty.terminal_state == "escalated" and empty.decision.reason_codes == ["empty_ticket"]


def test_unseen_file_order_count_and_provider_disabled_reconcile(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDSERVE_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("CLOUDSERVE_MODEL_MODE", "extractive")
    monkeypatch.delenv("AZURE_GPT_4o_API_KEY", raising=False)
    rows = [
        {"ticket_id": "UNSEEN-4", "channel": "forum", "body": "Unknown and unsupported request."},
        {"ticket_id": "UNSEEN-1", "channel": "email", "body": "A production key leaked in a security incident."},
        {"ticket_id": "UNSEEN-3", "channel": "docs_comment", "subject": "No useful details", "body": ""},
        {"ticket_id": "UNSEEN-2", "channel": "chat", "body": "The API returns duplicate records during pagination."},
        {"channel": "chat", "body": "This ticket has no supplied ID."},
        None,
    ]
    input_path = tmp_path / "reordered-unseen.json"
    input_path.write_text(json.dumps(rows))
    output = tmp_path / "arbitrary-output"
    metrics = run(input_path, output, mode="extractive")
    results = json.loads((output / "results.json").read_text())
    manifest = json.loads((output / "run_manifest.json").read_text())
    assert metrics["processed"] == 6 and metrics["terminal_reconciliation"]
    assert [item["ticket_id"] for item in results] == ["UNSEEN-4", "UNSEEN-1", "UNSEEN-3", "UNSEEN-2", "INPUT-000005", "INPUT-000006"]
    assert all(item["terminal_state"] in {"sent", "escalated"} for item in results)
    assert all(item["terminal_state"] == "escalated" for item in results if item["ticket_id"] in {"UNSEEN-1", "UNSEEN-3"})
    assert manifest["input_ticket_ids"] == manifest["terminal_ticket_ids"] == manifest["decision_ticket_ids"]
    assert manifest["knowledge"]["documents"] == 29
    assert manifest["model_versions"] and manifest["policy_versions"] and manifest["prompt_versions"]
    assert len(manifest["input_sha256"]) == 64


def test_same_ticket_and_versions_repeat_routing_decision(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDSERVE_RUNTIME_DIR", str(tmp_path / "runtime"))
    raw = {"ticket_id": "REPEAT-1", "channel": "chat", "subject": "API pagination",
           "body": "Records repeat when I page through a changing collection."}
    first = TicketService(tmp_path / "first.sqlite").process(raw, mode="extractive")
    second = TicketService(tmp_path / "second.sqlite").process(raw, mode="extractive")
    assert first.classification == second.classification
    assert first.decision == second.decision
    assert first.terminal_state == second.terminal_state
