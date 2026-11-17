"""Persistent ticket and decision log.

Results, events and human resolutions are encrypted at rest (`cloudserve.encryption`).
Each ticket carries its tenant (the customer account) so the API can enforce
object-level authorization. Retention: raw customer text can be erased per customer
or after a retention period while decision records (no raw text) are kept for audit.
"""

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cloudserve.contracts import HumanResolution, TicketResult
from cloudserve.encryption import decrypt, encrypt

ERASED = "[erased under retention policy]"
RAW_TEXT_KEYS = ("subject", "body", "queries")


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
            db.execute("CREATE TABLE IF NOT EXISTS outbox (delivery_id TEXT PRIMARY KEY, ticket_id TEXT NOT NULL, channel TEXT NOT NULL, kind TEXT NOT NULL, payload_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0, next_attempt_at REAL NOT NULL DEFAULT 0, last_error TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, delivered_at TEXT)")
            columns = {row[1] for row in db.execute("PRAGMA table_info(tickets)")}
            if "tenant_id" not in columns:
                db.execute("ALTER TABLE tickets ADD COLUMN tenant_id TEXT")
            if "created_at" not in columns:
                db.execute("ALTER TABLE tickets ADD COLUMN created_at TEXT")
            if "erased_at" not in columns:
                db.execute("ALTER TABLE tickets ADD COLUMN erased_at TEXT")

    def _connect(self):
        return sqlite3.connect(self.path, timeout=30)

    @staticmethod
    def _result(result_json: str, resolution_json: str | None = None) -> TicketResult:
        result = TicketResult.model_validate_json(decrypt(result_json))
        if resolution_json:
            result = result.model_copy(update={"human_resolution": HumanResolution.model_validate_json(decrypt(resolution_json))})
        return result

    def get(self, ticket_id: str) -> tuple[str, TicketResult] | None:
        with self._connect() as db:
            row = db.execute("SELECT t.input_hash, t.result_json, h.payload_json FROM tickets t LEFT JOIN human_resolutions h ON t.ticket_id=h.ticket_id WHERE t.ticket_id=?", (ticket_id,)).fetchone()
        if not row:
            return None
        return row[0], self._result(row[1], row[2])

    def tenant_of(self, ticket_id: str) -> str | None:
        with self._connect() as db:
            row = db.execute("SELECT tenant_id FROM tickets WHERE ticket_id=?", (ticket_id,)).fetchone()
        return row[0] if row else None

    def save(self, input_hash: str, result: TicketResult, events: list[tuple[str, dict]], tenant_id: str = "anonymous",
             channel: str = "chat") -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            db.execute("INSERT INTO tickets(ticket_id,input_hash,result_json,tenant_id,created_at) VALUES(?,?,?,?,?)",
                       (result.ticket_id, input_hash, encrypt(result.model_dump_json()), tenant_id, now))
            db.executemany("INSERT INTO events(ticket_id,trace_id,stage,payload_json) VALUES(?,?,?,?)", [
                (result.ticket_id, result.trace_id, stage, encrypt(json.dumps(payload, default=str))) for stage, payload in events
            ])
            # Transactional outbox: the delivery intent commits with the decision, so a crash can
            # neither send without a logged decision nor lose a decided message.
            kind = "answer" if result.terminal_state == "sent" else "handoff_acknowledgement"
            db.execute("INSERT OR IGNORE INTO outbox(delivery_id,ticket_id,channel,kind,payload_json) VALUES(?,?,?,?,?)",
                       (f"{result.ticket_id}:customer_message", result.ticket_id, channel, kind,
                        encrypt(json.dumps({"ticket_id": result.ticket_id, "trace_id": result.trace_id,
                                            "message": result.customer_message,
                                            "citations": [c.passage_id for c in result.citations]}))))

    # ------------------------------------------------------------ outbox
    def due_deliveries(self, now: float, limit: int = 100) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("SELECT delivery_id,ticket_id,channel,kind,payload_json,attempts FROM outbox WHERE status='pending' AND next_attempt_at<=? ORDER BY rowid LIMIT ?", (now, limit)).fetchall()
        return [{"delivery_id": r[0], "ticket_id": r[1], "channel": r[2], "kind": r[3], "payload": json.loads(decrypt(r[4])), "attempts": r[5]} for r in rows]

    def mark_delivered(self, delivery_id: str) -> bool:
        """Idempotent: returns False if it was already delivered (no second send is recorded)."""
        with self._connect() as db:
            cur = db.execute("UPDATE outbox SET status='delivered', attempts=attempts+1, delivered_at=? WHERE delivery_id=? AND status='pending'",
                             (datetime.now(timezone.utc).isoformat(), delivery_id))
            return cur.rowcount == 1

    def mark_failed(self, delivery_id: str, error: str, next_attempt_at: float, dead: bool) -> None:
        with self._connect() as db:
            db.execute("UPDATE outbox SET attempts=attempts+1, last_error=?, next_attempt_at=?, status=? WHERE delivery_id=? AND status='pending'",
                       (error[:200], next_attempt_at, "dead_letter" if dead else "pending", delivery_id))

    def outbox_counts(self) -> dict:
        with self._connect() as db:
            rows = db.execute("SELECT status, COUNT(*) FROM outbox GROUP BY status").fetchall()
        return {status: count for status, count in rows}

    def list_results(self, limit: int = 100, state: str | None = None, pending_only: bool = False,
                     tenant_id: str | None = None) -> list[TicketResult]:
        query = "SELECT t.result_json, h.payload_json FROM tickets t LEFT JOIN human_resolutions h ON t.ticket_id=h.ticket_id"
        params: tuple = ()
        if tenant_id is not None:
            query += " WHERE t.tenant_id=?"
            params = (tenant_id,)
        with self._connect() as db:
            rows = db.execute(query + " ORDER BY t.rowid DESC", params).fetchall()
        items = []
        for result_json, resolution_json in rows:
            result = self._result(result_json, resolution_json)
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
            result = self._result(row[0])
            if result.terminal_state != "escalated":
                raise NotEscalated("Only escalated tickets can receive a human resolution")
            existing = db.execute("SELECT payload_json FROM human_resolutions WHERE ticket_id=?", (resolution.ticket_id,)).fetchone()
            if existing:
                previous = HumanResolution.model_validate_json(decrypt(existing[0]))
                same = all(getattr(previous, field) == getattr(resolution, field) for field in ("reviewer", "resolution_type", "notes"))
                if same:
                    return previous
                raise ResolutionConflict("Ticket already has a different human resolution")
            db.execute("INSERT INTO human_resolutions(ticket_id,payload_json) VALUES(?,?)", (resolution.ticket_id, encrypt(resolution.model_dump_json())))
            db.execute("INSERT INTO events(ticket_id,trace_id,stage,payload_json) VALUES(?,?,?,?)", (
                resolution.ticket_id, result.trace_id, "human_resolved", encrypt(resolution.model_dump_json())))
        return resolution

    def events(self, ticket_id: str) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("SELECT stage,payload_json,created_at,trace_id FROM events WHERE ticket_id=? ORDER BY event_id", (ticket_id,)).fetchall()
        return [{"stage": stage, "payload": json.loads(decrypt(payload)), "created_at": created, "trace_id": trace_id} for stage, payload, created, trace_id in rows]

    def counts(self, tenant_id: str | None = None) -> dict:
        items = self.list_results(limit=10 ** 9, tenant_id=tenant_id)
        with self._connect() as db:
            event_count = db.execute("SELECT COUNT(DISTINCT ticket_id) FROM events WHERE stage='terminal'").fetchone()[0]
            resolved_count = db.execute("SELECT COUNT(*) FROM human_resolutions").fetchone()[0]
        return {
            "processed": len(items),
            "answered": sum(x.terminal_state == "sent" for x in items),
            "escalated": sum(x.terminal_state == "escalated" for x in items),
            "guardrail_blocked": sum(bool(x.guardrail_findings) for x in items),
            "decisions_logged": event_count,
            "human_resolved": resolved_count,
            "open_handoffs": sum(x.terminal_state == "escalated" and x.human_resolution is None for x in items),
        }

    def add_feedback(self, ticket_id: str, rating: str, comment: str = "") -> None:
        with self._connect() as db:
            db.execute("INSERT INTO feedback(ticket_id,rating,comment) VALUES(?,?,?)", (ticket_id, rating, comment))

    # ------------------------------------------------------------ retention and deletion
    def _erase(self, db, ticket_ids: list[str], reason: str) -> int:
        now = datetime.now(timezone.utc).isoformat()
        erased = 0
        for ticket_id in ticket_ids:
            row = db.execute("SELECT result_json, erased_at FROM tickets WHERE ticket_id=?", (ticket_id,)).fetchone()
            if not row or row[1]:
                continue
            result = self._result(row[0])
            packet = result.escalation_packet.model_copy(update={"summary": ERASED}) if result.escalation_packet else None
            result = result.model_copy(update={"escalation_summary": ERASED if result.escalation_summary else None,
                                               "escalation_packet": packet})
            db.execute("UPDATE tickets SET result_json=?, erased_at=? WHERE ticket_id=?", (encrypt(result.model_dump_json()), now, ticket_id))
            for event_id, payload in db.execute("SELECT event_id,payload_json FROM events WHERE ticket_id=?", (ticket_id,)).fetchall():
                data = json.loads(decrypt(payload))
                if isinstance(data, dict) and any(key in data for key in RAW_TEXT_KEYS):
                    data.update({key: ERASED for key in RAW_TEXT_KEYS if key in data})
                    db.execute("UPDATE events SET payload_json=? WHERE event_id=?", (encrypt(json.dumps(data)), event_id))
            db.execute("UPDATE feedback SET comment=? WHERE ticket_id=?", (ERASED, ticket_id))
            db.execute("INSERT INTO events(ticket_id,trace_id,stage,payload_json) VALUES(?,?,?,?)",
                       (ticket_id, result.trace_id, "raw_text_erased", encrypt(json.dumps({"reason": reason, "at": now}))))
            erased += 1
        return erased

    def erase_customer(self, customer_id: str, reason: str = "customer deletion request") -> int:
        """Erase raw customer text for one tenant; decisions, reasons and citations stay for audit."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            ids = [r[0] for r in db.execute("SELECT ticket_id FROM tickets WHERE tenant_id=?", (customer_id,)).fetchall()]
            return self._erase(db, ids, reason)

    def purge_older_than(self, days: int, now: datetime | None = None) -> int:
        cutoff = ((now or datetime.now(timezone.utc)) - timedelta(days=days)).isoformat()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            ids = [r[0] for r in db.execute("SELECT ticket_id FROM tickets WHERE created_at IS NOT NULL AND created_at < ?", (cutoff,)).fetchall()]
            return self._erase(db, ids, f"retention period of {days} days")
