import json

from cloudserve.agents import AnswerAgent
from cloudserve.azure import ModelUnavailable
from cloudserve.config import supplied
from cloudserve.knowledge import resolve
from cloudserve.service import DuplicateConflict, TicketService
from evaluation.harness import run


def test_four_channels_and_terminal_log(tmp_path):
    service = TicketService(tmp_path / "tickets.sqlite")
    for channel in ("email", "chat", "docs_comment", "forum"):
        result = service.process({"ticket_id": f"TEST-{channel}", "channel": channel, "body": "I need help with my deployment configuration."})
        assert result.terminal_state in {"sent", "escalated"}
        assert service.store.events(result.ticket_id)[-1]["stage"] == "terminal"
    assert service.store.counts()["decisions_logged"] == 4


def test_protected_request_escalates(tmp_path):
    service = TicketService(tmp_path / "tickets.sqlite")
    result = service.process({"ticket_id": "SEC-1", "channel": "chat", "body": "A production key was exposed in a security incident."})
    assert result.terminal_state == "escalated"
    assert "security" in " ".join(result.decision.reason_codes)
    assert result.escalation_packet and result.escalation_packet.trace_id == result.trace_id
    assert result.escalation_packet.next_step


def test_answer_has_real_citation(tmp_path):
    rows = json.loads(supplied("development_tickets.json").read_text())
    row = next(row for row in rows if row["ticket_id"] == "DEV-0026")
    service = TicketService(tmp_path / "tickets.sqlite")
    result = service.process({k: v for k, v in row.items() if k not in ("labels", "history", "customer_name")})
    assert result.terminal_state == "sent"
    assert result.citations
    assert all(resolve(p.passage_id) and f"[{p.passage_id}]" in result.customer_message for p in result.citations)


def test_guardrail_blocks_forbidden_draft(tmp_path, monkeypatch):
    rows = json.loads(supplied("development_tickets.json").read_text())
    row = next(row for row in rows if row["ticket_id"] == "DEV-0026")
    service = TicketService(tmp_path / "tickets.sqlite")
    monkeypatch.setattr(service.answer, "draft", lambda ticket, passages, mode: f"A refund has been issued. [{passages[0].passage_id}]")
    result = service.process({k: v for k, v in row.items() if k not in ("labels", "history", "customer_name")})
    assert result.terminal_state == "escalated"
    assert "forbidden_commitment" in result.guardrail_findings
    assert "refund" not in result.customer_message.lower()


def test_provider_outage_escalates(tmp_path, monkeypatch):
    rows = json.loads(supplied("development_tickets.json").read_text())
    row = next(row for row in rows if row["ticket_id"] == "DEV-0026")
    service = TicketService(tmp_path / "tickets.sqlite")
    def fail(*_args): raise ModelUnavailable("outage")
    monkeypatch.setattr(service.answer, "draft", fail)
    result = service.process({k: v for k, v in row.items() if k not in ("labels", "history", "customer_name")})
    assert result.terminal_state == "escalated"
    assert result.decision.reason_codes == ["processing_failure"]


def test_idempotency_and_conflict(tmp_path):
    service = TicketService(tmp_path / "tickets.sqlite")
    payload = {"ticket_id": "IDEMP-1", "channel": "chat", "body": "Need help"}
    one = service.process(payload)
    two = service.process(payload)
    assert one.trace_id == two.trace_id
    try:
        service.process({**payload, "body": "Different message"})
    except DuplicateConflict:
        pass
    else:
        raise AssertionError("Expected duplicate conflict")


def test_unattended_full_set_reconciles(tmp_path):
    metrics = run(supplied("development_tickets.json"), tmp_path / "run")
    assert metrics["processed"] == 500
    assert metrics["terminal_reconciliation"]
    assert (tmp_path / "run" / "metrics.json").exists()
