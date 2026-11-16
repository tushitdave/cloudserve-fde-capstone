"""HTTP contract for the local support-review action."""

import asyncio
import json

from cloudserve.api.routes import tickets as ticket_routes
from cloudserve.main import app
from cloudserve.service import TicketService


async def request(method: str, path: str, payload=None):
    body = json.dumps(payload).encode() if payload is not None else b""
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
             "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
             "query_string": b"", "root_path": "", "headers": [(b"content-type", b"application/json")],
             "client": ("127.0.0.1", 0), "server": ("test", 80)}
    sent = []
    first = True

    async def receive():
        nonlocal first
        if first:
            first = False
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    await app(scope, receive, send)
    return sent[0]["status"], json.loads(sent[-1]["body"])


def test_resolution_http_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setattr(ticket_routes, "service", TicketService(tmp_path / "api.sqlite"))

    async def scenario():
        status, ticket = await request("POST", "/v1/tickets", {"ticket_id": "API-HITL-1", "channel": "chat",
                            "body": "A production key was exposed in a security incident."})
        assert status == 200 and ticket["terminal_state"] == "escalated"
        status, queue = await request("GET", "/v1/escalations")
        assert status == 200 and [row["ticket_id"] for row in queue] == ["API-HITL-1"]
        payload = {"reviewer": "Support reviewer", "resolution_type": "answered_by_human",
                   "notes": "Verified the incident and responded through support."}
        status, resolution = await request("POST", "/v1/escalations/API-HITL-1/resolve", payload)
        assert status == 200 and resolution["reviewer"] == "Support reviewer"
        status, repeated = await request("POST", "/v1/escalations/API-HITL-1/resolve", payload)
        assert status == 200 and repeated == resolution
        status, conflict = await request("POST", "/v1/escalations/API-HITL-1/resolve", {**payload, "notes": "Different resolution."})
        assert status == 409 and "already" in conflict["detail"]
        status, queue = await request("GET", "/v1/escalations")
        assert status == 200 and queue == []
        status, detail = await request("GET", "/v1/tickets/API-HITL-1")
        assert status == 200 and detail["human_resolution"] == resolution
        assert detail["terminal_state"] == "escalated" and detail["trace_id"] == ticket["trace_id"]
        status, decision = await request("GET", "/v1/tickets/API-HITL-1/decision")
        assert status == 200 and [event["stage"] for event in decision["events"]].count("human_resolved") == 1
        status, metrics = await request("GET", "/v1/metrics")
        assert status == 200 and metrics["open_handoffs"] == 0 and metrics["human_resolved"] == 1

    asyncio.run(scenario())
