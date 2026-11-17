"""Transactional outbox, OpenTelemetry stage spans with budgets, and ingestion retry/dead-letter."""

import json
import sqlite3

from cloudserve import policy
from cloudserve.azure import ModelUnavailable
from cloudserve.config import supplied
from cloudserve.knowledge_pipeline import KnowledgeService
from cloudserve.observability.tracing import finished_spans
from cloudserve.outbox import dispatch
from cloudserve.service import TicketService


def documented_ticket():
    row = next(r for r in json.loads(supplied("development_tickets.json").read_text()) if r["ticket_id"] == "DEV-0026")
    return {k: v for k, v in row.items() if k not in ("labels", "history")}


def test_outbox_written_with_decision_delivered_once_and_dead_lettered_on_outage(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDSERVE_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("CLOUDSERVE_BACKOFF_BASE_S", "0")
    service = TicketService(tmp_path / "o.sqlite")
    service.process(documented_ticket())
    service.process({"ticket_id": "SEC-OB", "channel": "email", "body": "A production key was exposed in a security incident."})
    with sqlite3.connect(tmp_path / "o.sqlite") as db:
        kinds = dict(db.execute("SELECT ticket_id, kind FROM outbox").fetchall())
    assert kinds == {"DEV-0026": "answer", "SEC-OB": "handoff_acknowledgement"}
    delivered = []
    assert dispatch(service.store, delivered.append)["sent"] == 2
    assert dispatch(service.store, delivered.append)["sent"] == 0 and len(delivered) == 2   # never re-sent
    service.process({**documented_ticket(), "ticket_id": "DOWN-1"})

    def down(_delivery):
        raise ConnectionError("channel outage")

    for _ in range(5):
        result = dispatch(service.store, down, max_attempts=5)
    assert result["status"].get("dead_letter") == 1


def test_stage_spans_and_budget_timeout_escalates(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDSERVE_RUNTIME_DIR", str(tmp_path / "runtime"))
    finished_spans()
    service = TicketService(tmp_path / "t.sqlite")
    result = service.process(documented_ticket())
    spans = finished_spans()
    names = {s["name"] for s in spans}
    assert {"cloudserve.ticket", "cloudserve.classify", "cloudserve.evidence", "cloudserve.verify_validate"} <= names
    assert "pagination" not in json.dumps(spans).lower()   # no raw ticket text in traces
    record = next(e for e in service.store.events(result.ticket_id) if e["stage"] == "decision")["payload"]
    assert set(record["stage_timings_ms"]) >= {"classify", "policy_gate", "evidence", "answer", "verify_validate"}

    import time
    monkeypatch.setitem(policy.POLICY["agent_budgets_ms"], "evidence", 50)
    original = service.evidence.gather
    monkeypatch.setattr(service.evidence, "gather", lambda *a, **k: (time.sleep(0.3), original(*a, **k))[1])
    slow = service.process({**documented_ticket(), "ticket_id": "SLOW-1"})
    assert slow.terminal_state == "escalated" and slow.decision.reason_codes == ["processing_failure"]
    failure = next(e for e in service.store.events("SLOW-1") if e["stage"] == "failure")["payload"]
    assert failure["type"] == "AgentTimeout" and failure["stage"] == "evidence"


def test_ingestion_retries_then_dead_letters_and_operator_retry(tmp_path):
    svc = KnowledgeService(tmp_path / "k.sqlite", mode="extractive", max_attempts=3, sleep=lambda _s: None)
    doc = json.loads(supplied("documentation.json").read_text())[0]
    calls = {"n": 0}
    real = svc.steward.review

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise ModelUnavailable("429 rate limit")
        return real(*args, **kwargs)

    svc.steward.review = flaky
    edited = {**doc, "owner": "Ines Varga", "content": doc["content"] + "\n\nAdditional reviewed note."}
    job = svc.stage(edited)
    assert job["status"] == "pending_review" and job["steward"]["attempts"] == 3
    svc.steward.review = lambda *a, **k: (_ for _ in ()).throw(ModelUnavailable("outage"))
    other = {**edited, "content": edited["content"] + " Second change."}
    dead = svc.stage(other)
    assert dead["status"] == "dead_letter" and dead["steward"]["failure_category"] == "model_unavailable"
    svc.steward.review = real
    fresh = svc.retry(dead["job_id"])
    assert fresh["status"] == "pending_review" and svc.store.get_job(dead["job_id"])["status"] == "superseded"


def test_triage_continue_is_rechecked_by_policy(tmp_path, monkeypatch):
    from cloudserve.contracts import Classification
    monkeypatch.setenv("CLOUDSERVE_RUNTIME_DIR", str(tmp_path / "runtime"))
    service = TicketService(tmp_path / "tr.sqlite")
    low = Classification(intent="api_usage_question", urgency="low", intent_confidence=0.4, urgency_confidence=0.5,
                         alternatives=[{"intent": "security_incident", "confidence": 0.3}], nearest_training_similarity=0.9,
                         model_version="test", calibrated=True)
    monkeypatch.setattr("cloudserve.orchestration.ticket_graph.classify", lambda _t: low)
    monkeypatch.setattr(service.triage, "assess", lambda *_a: {"recommendation": "continue", "proposed_intent": "api_usage_question"})
    ok = service.process({**documented_ticket(), "ticket_id": "TRI-1"})
    assert ok.terminal_state == "sent"
    monkeypatch.setattr(service.triage, "assess", lambda *_a: {"recommendation": "continue", "proposed_intent": "security_incident"})
    blocked = service.process({**documented_ticket(), "ticket_id": "TRI-2"})
    assert blocked.terminal_state == "escalated" and blocked.decision.reason_codes == ["low_intent_confidence"]
