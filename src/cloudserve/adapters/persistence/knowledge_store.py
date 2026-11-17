"""Transactional staging, certification, publication and source history."""

import json
import sqlite3
from pathlib import Path

from cloudserve.config import runtime_dir, supplied


class KnowledgeConflict(ValueError):
    pass


class KnowledgeStore:
    def __init__(self, path: Path | None = None):
        self.path = path or runtime_dir() / "knowledge.sqlite"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS jobs (job_id TEXT PRIMARY KEY, doc_id TEXT NOT NULL, source_hash TEXT NOT NULL, payload_json TEXT NOT NULL, status TEXT NOT NULL, intake_json TEXT NOT NULL, steward_json TEXT NOT NULL, reviewer TEXT, review_note TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            db.execute("CREATE TABLE IF NOT EXISTS active_overrides (doc_id TEXT PRIMARY KEY, source_hash TEXT NOT NULL, doc_json TEXT NOT NULL, job_id TEXT NOT NULL, published_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            db.execute("CREATE TABLE IF NOT EXISTS source_versions (doc_id TEXT NOT NULL, source_hash TEXT NOT NULL, doc_json TEXT NOT NULL, PRIMARY KEY(doc_id,source_hash))")
            db.execute("CREATE TABLE IF NOT EXISTS knowledge_events (event_id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL, stage TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('revision','0')")

    def _connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def revision(self) -> int:
        with self._connect() as db:
            return int(db.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0])

    def active_documents(self) -> list[dict]:
        docs = {doc["doc_id"]: {**doc, "owner": "supplied_capstone_pack", "permissions": ["customer_support"]}
                for doc in json.loads(supplied("documentation.json").read_text())}
        with self._connect() as db:
            rows = db.execute("SELECT doc_id,doc_json FROM active_overrides").fetchall()
        docs.update({doc_id: json.loads(value) for doc_id, value in rows})
        return [docs[key] for key in sorted(docs)]

    def source_version(self, doc_id: str, source_hash: str) -> dict | None:
        with self._connect() as db:
            row = db.execute("SELECT doc_json FROM source_versions WHERE doc_id=? AND source_hash=?", (doc_id, source_hash)).fetchone()
        if row:
            return json.loads(row[0])
        return next(({**doc, "owner": "supplied_capstone_pack"} for doc in json.loads(supplied("documentation.json").read_text())
                     if doc["doc_id"] == doc_id and _content_hash(doc) == source_hash), None)

    def active_metadata(self, doc_id: str) -> dict:
        with self._connect() as db:
            row = db.execute("SELECT a.source_hash,a.job_id,a.published_at,j.reviewer,j.review_note FROM active_overrides a JOIN jobs j ON a.job_id=j.job_id WHERE a.doc_id=?", (doc_id,)).fetchone()
        if row:
            return {"source_hash": row[0], "job_id": row[1], "published_at": row[2], "certified_by": row[3],
                    "review_note": row[4], "authority": "human_certified", "active": True}
        baseline = next((doc for doc in json.loads(supplied("documentation.json").read_text()) if doc["doc_id"] == doc_id), None)
        return {"source_hash": _content_hash(baseline) if baseline else None, "authority": "supplied_capstone_pack",
                "job_id": None, "published_at": None, "certified_by": "capstone_pack",
                "review_note": "Supplied approved article", "active": True}

    def versions(self, doc_id: str) -> list[dict]:
        baseline = next((doc for doc in json.loads(supplied("documentation.json").read_text()) if doc["doc_id"] == doc_id), None)
        if baseline is None:
            return []
        versions = {_content_hash(baseline): {"source_hash": _content_hash(baseline), "owner": "supplied_capstone_pack",
                                             "authority": "supplied_capstone_pack", "certified_by": "capstone_pack", "job_id": None,
                                             "published_at": None, "review_note": "Supplied approved article"}}
        with self._connect() as db:
            rows = db.execute("SELECT s.source_hash,s.doc_json,j.job_id,j.reviewer,j.review_note,j.updated_at FROM source_versions s LEFT JOIN jobs j ON j.doc_id=s.doc_id AND j.source_hash=s.source_hash AND j.status='published' WHERE s.doc_id=? ORDER BY j.rowid DESC", (doc_id,)).fetchall()
            active = db.execute("SELECT source_hash FROM active_overrides WHERE doc_id=?", (doc_id,)).fetchone()
        for source_hash, doc_json, job_id, reviewer, review_note, published_at in rows:
            if source_hash not in versions or (job_id and versions[source_hash].get("job_id") is None):
                versions[source_hash] = {"source_hash": source_hash, "owner": json.loads(doc_json).get("owner", "unknown"),
                                         "authority": "human_certified" if job_id else "supplied_capstone_pack",
                                         "certified_by": reviewer or "capstone_pack", "job_id": job_id,
                                         "published_at": published_at, "review_note": review_note}
        active_hash = active[0] if active else _content_hash(baseline)
        return [{**item, "active": source_hash == active_hash} for source_hash, item in sorted(versions.items())]

    def get_job(self, job_id: str) -> dict | None:
        with self._connect() as db:
            row = db.execute("SELECT job_id,doc_id,source_hash,payload_json,status,intake_json,steward_json,reviewer,review_note,created_at,updated_at FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        return _job(row) if row else None

    def list_jobs(self, limit: int = 50) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("SELECT job_id,doc_id,source_hash,payload_json,status,intake_json,steward_json,reviewer,review_note,created_at,updated_at FROM jobs ORDER BY rowid DESC LIMIT ?", (limit,)).fetchall()
        return [_job(row) for row in rows]

    def stage(self, job_id: str, doc: dict, source_hash: str, status: str, intake: dict, steward: dict) -> dict:
        with self._connect() as db:
            existing = db.execute("SELECT job_id,payload_json FROM jobs WHERE doc_id=? AND source_hash=? AND status IN ('pending_review','approved','published','unchanged') ORDER BY rowid DESC", (doc["doc_id"], source_hash)).fetchall()
            for existing_id, existing_payload in existing:
                if json.loads(existing_payload).get("base_hash") == doc.get("base_hash"):
                    return self.get_job(existing_id)
            db.execute("INSERT INTO jobs(job_id,doc_id,source_hash,payload_json,status,intake_json,steward_json) VALUES(?,?,?,?,?,?,?)",
                       (job_id, doc["doc_id"], source_hash, json.dumps(doc), status, json.dumps(intake), json.dumps(steward)))
            db.execute("INSERT INTO knowledge_events(job_id,stage,payload_json) VALUES(?,?,?)", (job_id, "staged", json.dumps({"status": status, "source_hash": source_hash})))
        return self.get_job(job_id)

    def review(self, job_id: str, reviewer: str, note: str, approve: bool) -> dict:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if not row:
                raise KeyError(job_id)
            if row[0] != "pending_review":
                raise KnowledgeConflict(f"Job status is {row[0]}; only pending review can be decided")
            status = "approved" if approve else "rejected"
            db.execute("UPDATE jobs SET status=?,reviewer=?,review_note=?,updated_at=CURRENT_TIMESTAMP WHERE job_id=?", (status, reviewer, note, job_id))
            db.execute("INSERT INTO knowledge_events(job_id,stage,payload_json) VALUES(?,?,?)", (job_id, status, json.dumps({"reviewer": reviewer, "note": note})))
        return self.get_job(job_id)

    def publish(self, job_id: str, operator: str) -> dict:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT doc_id,source_hash,payload_json,status,reviewer FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if not row:
                raise KeyError(job_id)
            doc_id, source_hash, payload_json, status, reviewer = row
            if status != "approved" or not reviewer:
                raise KnowledgeConflict("Only a human-approved candidate can be published")
            current = next((doc for doc in self.active_documents() if doc["doc_id"] == doc_id), None)
            candidate = json.loads(payload_json)
            if current and candidate.get("base_hash") != _content_hash(current):
                raise KnowledgeConflict("Active source changed after candidate review; restage and recertify")
            if current:
                current_hash = _content_hash(current)
                db.execute("INSERT OR IGNORE INTO source_versions(doc_id,source_hash,doc_json) VALUES(?,?,?)", (doc_id, current_hash, json.dumps(current)))
            db.execute("INSERT OR IGNORE INTO source_versions(doc_id,source_hash,doc_json) VALUES(?,?,?)", (doc_id, source_hash, payload_json))
            db.execute("INSERT INTO active_overrides(doc_id,source_hash,doc_json,job_id) VALUES(?,?,?,?) ON CONFLICT(doc_id) DO UPDATE SET source_hash=excluded.source_hash,doc_json=excluded.doc_json,job_id=excluded.job_id,published_at=CURRENT_TIMESTAMP", (doc_id, source_hash, payload_json, job_id))
            db.execute("UPDATE meta SET value=CAST(value AS INTEGER)+1 WHERE key='revision'")
            db.execute("UPDATE jobs SET status='published',updated_at=CURRENT_TIMESTAMP WHERE job_id=?", (job_id,))
            db.execute("INSERT INTO knowledge_events(job_id,stage,payload_json) VALUES(?,?,?)", (job_id, "published", json.dumps({"operator": operator, "source_hash": source_hash})))
        return self.get_job(job_id)

    def mark_superseded(self, job_id: str, new_job_id: str) -> None:
        with self._connect() as db:
            db.execute("UPDATE jobs SET status='superseded',updated_at=CURRENT_TIMESTAMP WHERE job_id=? AND status='dead_letter'", (job_id,))
            db.execute("INSERT INTO knowledge_events(job_id,stage,payload_json) VALUES(?,?,?)", (job_id, "retried", json.dumps({"new_job_id": new_job_id})))

    def events(self, job_id: str) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("SELECT stage,payload_json,created_at FROM knowledge_events WHERE job_id=? ORDER BY event_id", (job_id,)).fetchall()
        return [{"stage": stage, "payload": json.loads(payload), "created_at": created} for stage, payload, created in rows]


def _content_hash(doc: dict) -> str:
    import hashlib
    return hashlib.sha256(doc["content"].encode()).hexdigest()[:12]


def _job(row) -> dict:
    keys = ("job_id", "doc_id", "source_hash", "document", "status", "intake", "steward", "reviewer", "review_note", "created_at", "updated_at")
    item = dict(zip(keys, row))
    for name in ("document", "intake", "steward"):
        item[name] = json.loads(item[name])
    return item
