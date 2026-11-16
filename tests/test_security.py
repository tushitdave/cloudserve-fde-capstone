"""Identity, role checks, tenant isolation, quotas, encryption at rest and retention."""

import asyncio
import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from cloudserve import security
from cloudserve.api.routes import tickets as ticket_routes
from cloudserve.service import TicketService
from tests.test_resolution_api import request


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDSERVE_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setattr(ticket_routes, "service", TicketService(tmp_path / "api.sqlite"))
    return ticket_routes.service


def test_missing_unknown_and_wrong_role_keys_are_rejected(api):
    async def scenario():
        assert (await request("GET", "/v1/tickets", key=None))[0] == 401
        assert (await request("GET", "/v1/tickets", key="not-a-key"))[0] == 401
        assert (await request("POST", "/v1/policy/kill-switch", {"active": True, "operator": "x", "reason": "testing"}, key="demo-agent-key"))[0] == 403
        assert (await request("POST", "/v1/knowledge/jobs", {"doc_id": "DOC-API-001"}, key="demo-customer-key"))[0] == 403
        assert (await request("GET", "/health", key=None))[0] == 200
    asyncio.run(scenario())


def test_customer_sees_only_own_tenant(api):
    async def scenario():
        status, own = await request("POST", "/v1/tickets", {"ticket_id": "T-OWN", "channel": "chat", "body": "How do I paginate results?"},
                                    key="demo-customer-key")
        assert status == 200
        status, _ = await request("POST", "/v1/tickets", {"ticket_id": "T-OTHER", "channel": "email", "customer_id": "CUST-OTHER",
                                                          "body": "How do I paginate results?"}, key="demo-agent-key")
        assert status == 200
        assert (await request("GET", "/v1/tickets/T-OWN", key="demo-customer-key"))[0] == 200
        assert (await request("GET", "/v1/tickets/T-OTHER", key="demo-customer-key"))[0] == 404  # existence not revealed
        status, listed = await request("GET", "/v1/tickets", key="demo-customer-key")
        assert [t["ticket_id"] for t in listed] == ["T-OWN"]
        assert (await request("GET", "/v1/tickets/T-OWN/decision", key="demo-customer-key"))[0] == 403
        status, _ = await request("POST", "/v1/tickets", {"ticket_id": "T-SPOOF", "channel": "chat", "customer_id": "CUST-OTHER",
                                                          "body": "hi"}, key="demo-customer-key")
        assert status == 403
    asyncio.run(scenario())


def test_quota_returns_429(api, monkeypatch):
    monkeypatch.setenv("CLOUDSERVE_RATE_LIMIT_PER_MIN", "3")
    security.LIMITER.calls.clear()

    async def scenario():
        codes = [(await request("GET", "/v1/metrics", key="demo-operator-key"))[0] for _ in range(4)]
        assert codes[:3] == [200, 200, 200] and codes[3] == 429
    asyncio.run(scenario())
    security.LIMITER.calls.clear()


def test_records_are_encrypted_at_rest_and_readable_through_the_store(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDSERVE_RUNTIME_DIR", str(tmp_path / "runtime"))
    service = TicketService(tmp_path / "enc.sqlite")
    secret_text = "My unusual phrase zebra-quartz cannot sign in"
    service.process({"ticket_id": "ENC-1", "channel": "chat", "body": secret_text})
    with sqlite3.connect(tmp_path / "enc.sqlite") as db:
        raw = " ".join(r[0] for r in db.execute("SELECT payload_json FROM events")) + " ".join(r[0] for r in db.execute("SELECT result_json FROM tickets"))
    assert "zebra-quartz" not in raw and raw.count("enc:v1:") >= 2
    assert service.store.events("ENC-1")[0]["payload"]["body"] == secret_text


def test_customer_erasure_and_retention_purge_keep_decisions(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDSERVE_RUNTIME_DIR", str(tmp_path / "runtime"))
    service = TicketService(tmp_path / "ret.sqlite")
    service.process({"ticket_id": "R-1", "channel": "chat", "customer_id": "CUST-9", "body": "A production key was exposed in a security incident"})
    service.process({"ticket_id": "R-2", "channel": "chat", "customer_id": "CUST-8", "body": "How do I paginate results?"})
    assert service.store.erase_customer("CUST-9") == 1
    events = service.store.events("R-1")
    assert "exposed" not in json.dumps(events) and events[-1]["stage"] == "raw_text_erased"
    assert any(e["stage"] == "decision" for e in events)            # audit record kept
    assert service.store.get("R-1")[1].terminal_state == "escalated"
    assert service.store.erase_customer("CUST-9") == 0               # idempotent
    future = datetime.now(timezone.utc) + timedelta(days=100)
    assert service.store.purge_older_than(90, now=future) == 1       # R-2 only; R-1 already erased
    assert "paginate" not in json.dumps(service.store.events("R-2"))
