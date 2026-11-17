"""Governed support-article intake; agents recommend, a human certifies, code publishes."""

import hashlib
import re
import time
import uuid

from cloudserve.orchestration.agents.roles import KnowledgeStewardAgent, SourceIntakeAgent
from cloudserve.config import setting
from cloudserve.adapters.persistence.knowledge_store import KnowledgeStore, _content_hash
from cloudserve.application.reliability import RETRYABLE, failure_category, with_retries

DOC_ID = re.compile(r"^DOC-[A-Z]+-[0-9]{3}$")
SECRET = re.compile(r"(?:sk|api)[-_][A-Za-z0-9]{16,}|(?:password|api[_ -]?key)\s*[:=]\s*[^\s]{8,}", re.I)
PROMPT_INJECTION = re.compile(r"ignore (all |the )?(previous|system) instructions|reveal (the )?system prompt|do not tell (the )?user", re.I)


class KnowledgeService:
    def __init__(self, db_path=None, mode: str | None = None, max_attempts: int = 3, sleep=time.sleep):
        self.store = KnowledgeStore(db_path)
        self.intake = SourceIntakeAgent()
        self.steward = KnowledgeStewardAgent()
        self.mode = mode or setting("CLOUDSERVE_MODEL_MODE", "extractive")
        self.max_attempts = max_attempts
        self.sleep = sleep

    def retry(self, job_id: str) -> dict:
        """Operator re-runs a dead-letter work item; the original item is kept and marked superseded."""
        job = self.store.get_job(job_id)
        if not job:
            raise KeyError(job_id)
        if job["status"] != "dead_letter":
            raise ValueError("Only dead-letter work items can be retried")
        raw = job["document"].get("_raw") or {k: v for k, v in job["document"].items() if not k.startswith("_")}
        fresh = self.stage(raw)
        self.store.mark_superseded(job_id, fresh["job_id"])
        return fresh

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
               "permissions": (current or {}).get("permissions", ["customer_support"]),
               "base_hash": _content_hash(current) if current else None}
        source_format = str(raw.get("source_format") or "json").strip().lower()
        complete = all(doc[key] for key in ("doc_id", "title", "content", "owner"))
        intake = ({"action": "use_approved_json_parser", "reason": "Known support-article JSON format", "agent_invoked": False}
                  if source_format == "json" and complete else self.intake.assess({**doc, "source_format": source_format}))
        retry_log = []
        try:
            steward, attempts = with_retries(lambda: self.steward.review(doc, current, list(active.values()), mode=self.mode),
                                             max_attempts=self.max_attempts, sleep=self.sleep,
                                             on_retry=lambda n, e: retry_log.append({"attempt": n, "failure_category": failure_category(e)}))
        except RETRYABLE as error:
            # Exhausted transient failures: park the work item in the dead-letter state for operator review.
            steward = {"warnings": [], "quarantine_reasons": ["review_dependency_unavailable"], "attempts": self.max_attempts,
                       "failure_category": failure_category(error), "retry_log": retry_log, "requires_human_review": True}
            source_hash = _content_hash(doc)
            return self.store.stage(uuid.uuid4().hex, {**doc, "_raw": raw}, source_hash, "dead_letter", intake, steward)
        steward["attempts"] = attempts
        steward["retry_log"] = retry_log
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
        if raw.get("permissions") is not None and raw["permissions"] != doc["permissions"]:
            reasons.append("permission_change_requires_authorization")
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
