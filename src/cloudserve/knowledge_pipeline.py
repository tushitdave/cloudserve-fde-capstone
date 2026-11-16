"""Governed support-article intake; agents recommend, a human certifies, code publishes."""

import hashlib
import re
import uuid

from cloudserve.agents import KnowledgeStewardAgent, SourceIntakeAgent
from cloudserve.knowledge_store import KnowledgeStore, _content_hash

DOC_ID = re.compile(r"^DOC-[A-Z]+-[0-9]{3}$")
SECRET = re.compile(r"(?:sk|api)[-_][A-Za-z0-9]{16,}|(?:password|api[_ -]?key)\s*[:=]\s*[^\s]{8,}", re.I)
PROMPT_INJECTION = re.compile(r"ignore (all |the )?(previous|system) instructions|reveal (the )?system prompt|do not tell (the )?user", re.I)


class KnowledgeService:
    def __init__(self, db_path=None):
        self.store = KnowledgeStore(db_path)
        self.intake = SourceIntakeAgent()
        self.steward = KnowledgeStewardAgent()

    def stage(self, raw: dict) -> dict:
        raw = raw if isinstance(raw, dict) else {}
        doc_id = str(raw.get("doc_id") or f"QUARANTINE-{uuid.uuid4().hex[:8].upper()}").strip()
        active = {doc["doc_id"]: doc for doc in self.store.active_documents()}
        current = active.get(doc_id)
        doc = {"doc_id": doc_id, "title": str(raw.get("title") or "").strip(),
               "content": str(raw.get("content") or "").strip(), "owner": str(raw.get("owner") or "").strip(),
               "category": str(raw.get("category") or (current or {}).get("category") or "").strip(),
               "applies_to": str(raw.get("applies_to") or (current or {}).get("applies_to") or "").strip(),
               "related_docs": raw.get("related_docs") if isinstance(raw.get("related_docs"), list) else (current or {}).get("related_docs", []),
               "base_hash": _content_hash(current) if current else None}
        intake = self.intake.assess(doc)
        steward = self.steward.review(doc, current)
        reasons = []
        if intake["action"] == "quarantine":
            reasons.append("incomplete_source_format")
        if not DOC_ID.fullmatch(doc_id) or current is None:
            reasons.append("unknown_doc_id_requires_intent_mapping")
        if len(doc["content"]) < 80 or len(doc["content"]) > 25000:
            reasons.append("content_length_out_of_bounds")
        if "## Resolution" not in doc["content"]:
            reasons.append("missing_resolution_section")
        if SECRET.search(doc["content"]):
            reasons.append("possible_secret_in_source")
        if PROMPT_INJECTION.search(doc["content"]):
            reasons.append("instruction_like_source_text")
        if current and _content_hash(current) == _content_hash(doc) and current["title"] != doc["title"]:
            reasons.append("metadata_change_requires_content_version")
        steward["quarantine_reasons"] = reasons
        source_hash = _content_hash(doc)
        status = "quarantined" if reasons else "unchanged" if current and source_hash == _content_hash(current) else "pending_review"
        return self.store.stage(uuid.uuid4().hex, doc, source_hash, status, intake, steward)

    def review(self, job_id: str, reviewer: str, note: str, approve: bool) -> dict:
        if not reviewer.strip() or len(note.strip()) < 10:
            raise ValueError("Reviewer and at least 10 characters of review notes are required")
        return self.store.review(job_id, reviewer.strip(), note.strip(), approve)

    def publish(self, job_id: str, operator: str) -> dict:
        if not operator.strip():
            raise ValueError("Publisher name is required")
        # SQLite publication is atomic. Readers see a revisioned index on the next request.
        return self.store.publish(job_id, operator.strip())
