"""Persistent ticket and decision log for the prototype."""

import json
import sqlite3
from pathlib import Path

from cloudserve.contracts import HumanResolution, TicketResult


class ResolutionConflict(ValueError):
    pass


class NotEscalated(ValueError):
    pass


class Store:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS tickets (ticket_id TEXT PRIMARY KEY, input_hash TEXT NOT NULL, result_json TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS events (event_id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id TEXT NOT NULL, trace_id TEXT NOT NULL, stage TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            db.execute("CREATE TABLE IF NOT EXISTS feedback (feedback_id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id TEXT NOT NULL, rating TEXT NOT NULL, comment TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            db.execute("CREATE TABLE IF NOT EXISTS human_resolutions (ticket_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")

    def _connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def get(self, ticket_id: str) -> tuple[str, TicketResult] | None:
        with self._connect() as db:
            row = db.execute("SELECT t.input_hash, t.result_json, h.payload_json FROM tickets t LEFT JOIN human_resolutions h ON t.ticket_id=h.ticket_id WHERE t.ticket_id=?", (ticket_id,)).fetchone()
        if not row:
            return None
        result = TicketResult.model_validate_json(row[1])
        if row[2]:
            result = result.model_copy(update={"human_resolution": HumanResolution.model_validate_json(row[2])})
        return row[0], result

    def save(self, input_hash: str, result: TicketResult, events: list[tuple[str, dict]]) -> None:
        with self._connect() as db:
            db.execute("INSERT INTO tickets(ticket_id,input_hash,result_json) VALUES(?,?,?)", (result.ticket_id, input_hash, result.model_dump_json()))
            db.executemany("INSERT INTO events(ticket_id,trace_id,stage,payload_json) VALUES(?,?,?,?)", [
                (result.ticket_id, result.trace_id, stage, json.dumps(payload, default=str)) for stage, payload in events
            ])

    def list_results(self, limit: int = 100, state: str | None = None, pending_only: bool = False) -> list[TicketResult]:
        with self._connect() as db:
            rows = db.execute("SELECT t.result_json, h.payload_json FROM tickets t LEFT JOIN human_resolutions h ON t.ticket_id=h.ticket_id ORDER BY t.rowid DESC").fetchall()
        items = []
        for result_json, resolution_json in rows:
            result = TicketResult.model_validate_json(result_json)
            if resolution_json:
                result = result.model_copy(update={"human_resolution": HumanResolution.model_validate_json(resolution_json)})
            if state and result.terminal_state != state:
                continue
            if pending_only and result.human_resolution is not None:
                continue
            items.append(result)
            if len(items) >= limit:
                break
        return items

    def resolve_escalation(self, resolution: HumanResolution) -> HumanResolution:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT result_json FROM tickets WHERE ticket_id=?", (resolution.ticket_id,)).fetchone()
            if not row:
                raise KeyError(resolution.ticket_id)
            result = TicketResult.model_validate_json(row[0])
            if result.terminal_state != "escalated":
                raise NotEscalated("Only escalated tickets can receive a human resolution")
            existing = db.execute("SELECT payload_json FROM human_resolutions WHERE ticket_id=?", (resolution.ticket_id,)).fetchone()
            if existing:
                previous = HumanResolution.model_validate_json(existing[0])
                same = all(getattr(previous, field) == getattr(resolution, field) for field in ("reviewer", "resolution_type", "notes"))
                if same:
                    return previous
                raise ResolutionConflict("Ticket already has a different human resolution")
            db.execute("INSERT INTO human_resolutions(ticket_id,payload_json) VALUES(?,?)", (resolution.ticket_id, resolution.model_dump_json()))
            db.execute("INSERT INTO events(ticket_id,trace_id,stage,payload_json) VALUES(?,?,?,?)", (
                resolution.ticket_id, result.trace_id, "human_resolved", resolution.model_dump_json()))
        return resolution

    def events(self, ticket_id: str) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("SELECT stage,payload_json,created_at,trace_id FROM events WHERE ticket_id=? ORDER BY event_id", (ticket_id,)).fetchall()
        return [{"stage": stage, "payload": json.loads(payload), "created_at": created, "trace_id": trace_id} for stage, payload, created, trace_id in rows]

    def counts(self) -> dict:
        with self._connect() as db:
            rows = db.execute("SELECT result_json FROM tickets").fetchall()
            event_count = db.execute("SELECT COUNT(DISTINCT ticket_id) FROM events WHERE stage='terminal'").fetchone()[0]
            resolved_count = db.execute("SELECT COUNT(*) FROM human_resolutions").fetchone()[0]
        items = [TicketResult.model_validate_json(row[0]) for row in rows]
        return {
            "processed": len(items),
            "answered": sum(x.terminal_state == "sent" for x in items),
            "escalated": sum(x.terminal_state == "escalated" for x in items),
            "guardrail_blocked": sum(bool(x.guardrail_findings) for x in items),
            "decisions_logged": event_count,
            "human_resolved": resolved_count,
            "open_handoffs": sum(x.terminal_state == "escalated" for x in items) - resolved_count,
        }

    def add_feedback(self, ticket_id: str, rating: str, comment: str = "") -> None:
        with self._connect() as db:
            db.execute("INSERT INTO feedback(ticket_id,rating,comment) VALUES(?,?,?)", (ticket_id, rating, comment))
