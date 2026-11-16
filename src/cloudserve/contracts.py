"""Typed stage handoffs used by the API and batch harness."""

from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Ticket(BaseModel):
    ticket_id: str
    channel: Literal["email", "chat", "docs_comment", "forum"]
    subject: str = ""
    body: str = ""
    received_at: str = Field(default_factory=utc_now)
    customer_id: str = "anonymous"
    customer_tier: str = "unknown"
    customer_region: str = "unknown"
    language_fluency: str = "unknown"


class Classification(BaseModel):
    intent: str
    urgency: str
    intent_confidence: float = Field(ge=0, le=1)
    urgency_confidence: float = Field(ge=0, le=1)
    answerability_confidence: float = Field(default=0, ge=0, le=1)
    alternatives: list[dict] = []
    urgency_alternatives: list[dict] = []
    nearest_training_similarity: float = Field(default=1, ge=0, le=1)
    model_version: str = "tfidf-logreg-v1"
    calibrated: bool = False


class Passage(BaseModel):
    doc_id: str
    passage_id: str
    title: str
    section: str
    text: str
    score: float
    source_version: str
    start_offset: int = 0
    end_offset: int = 0
    permissions: list[str] = ["customer_support"]


class Decision(BaseModel):
    action: Literal["answer", "escalate"]
    reason_codes: list[str]
    reason: str
    policy_version: str = "policy-v1"
    threshold: float
    rule_ids_fired: list[str] = []
    thresholds_applied: dict = {}


class EscalationPacket(BaseModel):
    schema_version: str = "1.0"
    ticket_id: str
    trace_id: str
    reason_codes: list[str]
    summary: str
    known: list[str]
    unknown: list[str]
    next_step: str
    candidate_passage_ids: list[str] = []


class HumanResolution(BaseModel):
    schema_version: str = "1.0"
    ticket_id: str
    reviewer: str
    resolution_type: Literal["answered_by_human", "closed_without_answer"]
    notes: str
    reviewer_key_id: str | None = None
    resolved_at: str = Field(default_factory=utc_now)


class TicketResult(BaseModel):
    ticket_id: str
    trace_id: str
    terminal_state: Literal["sent", "escalated"]
    customer_message: str
    classification: Classification
    decision: Decision
    citations: list[Passage] = []
    escalation_summary: str | None = None
    escalation_packet: EscalationPacket | None = None
    human_resolution: HumanResolution | None = None
    guardrail_findings: list[str] = []
    guardrail_results: list[dict] = []
    agent_steps: list[str] = []
    completed_at: str = Field(default_factory=utc_now)
    latency_ms: int = 0


# Versioned handoff contracts. Existing short names remain as compatibility
# types for the first prototype; these names are exported as JSON Schemas.
class NormalizedTicket(Ticket):
    schema_version: str = "1.0"


class EventEnvelope(BaseModel):
    schema_version: str = "1.0"
    ticket_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    stage: str = Field(min_length=1)
    payload: dict
    created_at: str = Field(default_factory=utc_now)


class ClassificationResult(Classification):
    schema_version: str = "1.0"


class EvidenceBundle(BaseModel):
    schema_version: str = "1.0"
    ticket_id: str = Field(min_length=1)
    snapshot_revision: int = Field(ge=0)
    passages: list[Passage]
    searches: int = Field(ge=0, le=2)
    sufficient: bool
    reason: str = ""
    queries: list[str] = Field(default_factory=list, max_length=2)
    document_id: str | None = None
    retrieval_strategy: str = "lexical"
    fallback_reason: str | None = None
    document_confidence: float = Field(default=0, ge=0, le=1)
    top_score: float = 0
    supporting_passages: list[Passage] = []


class QueryPlan(BaseModel):
    schema_version: str = "1.0"
    ticket_id: str = Field(min_length=1)
    path: Literal["rule", "approved_document", "human"]
    query: str
    allowed_doc_ids: list[str]
    max_searches: int = Field(ge=0, le=2)
    source_revision: int = Field(ge=0)


class RoutingDecision(Decision):
    schema_version: str = "1.0"


class AnswerClaim(BaseModel):
    text: str = Field(min_length=1)
    supporting_passage_ids: list[str] = Field(min_length=1)


class DraftAnswer(BaseModel):
    schema_version: str = "1.0"
    ticket_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    claims: list[AnswerClaim]
    model_version: str = Field(min_length=1)


class VerificationReport(BaseModel):
    schema_version: str = "1.0"
    supported: bool
    citation_ids: list[str]
    unsupported_claims: list[str]
    verifier_version: str = Field(min_length=1)


class ValidationResult(BaseModel):
    schema_version: str = "1.0"
    valid: bool
    findings: list[str]
    validator_version: str = Field(min_length=1)


class FinalResult(TicketResult):
    schema_version: str = "1.0"


class SourceRecord(BaseModel):
    schema_version: str = "1.0"
    doc_id: str = Field(min_length=1)
    source_hash: str = Field(min_length=12)
    owner: str = Field(min_length=1)
    authority: str = Field(min_length=1)
    content: str = Field(min_length=1)


class KnowledgeWorkItem(BaseModel):
    schema_version: str = "1.0"
    job_id: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    status: Literal["pending_review", "approved", "published", "rejected", "quarantined", "unchanged"]
    source_hash: str = Field(min_length=12)


class SourceSpan(BaseModel):
    label: str = Field(min_length=1)
    parent_section: str | None = None
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    text: str = Field(min_length=1)


class CanonicalDocument(BaseModel):
    schema_version: str = "1.0"
    doc_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    source_version: str = Field(min_length=12)
    related_docs: list[str] = []
    sections: list[SourceSpan] = []
    steps: list[SourceSpan] = []
    permissions: list[str] = ["customer_support"]


class KnowledgeChunk(Passage):
    schema_version: str = "1.0"


class IndexManifest(BaseModel):
    schema_version: str = "1.0"
    snapshot_revision: int = Field(ge=0)
    documents: int = Field(ge=0)
    passages: int = Field(ge=0)
    index_version: str = Field(min_length=1)
    approved: bool
    dense_ready: bool


class SourceLineage(BaseModel):
    schema_version: str = "1.0"
    doc_id: str = Field(min_length=1)
    source_version: str = Field(min_length=12)
    passage_ids: list[str]
    job_id: str | None = None
    certified_by: str | None = None


class QuarantineRecord(BaseModel):
    schema_version: str = "1.0"
    job_id: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    reasons: list[str] = Field(min_length=1)
    source_hash: str = Field(min_length=12)
