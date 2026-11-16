import json

import pytest
from pydantic import ValidationError

from cloudserve.contracts import (AnswerClaim, CanonicalDocument, ClassificationResult, DraftAnswer,
                                  EscalationPacket, EventEnvelope, EvidenceBundle, IndexManifest,
                                  KnowledgeChunk, KnowledgeWorkItem, NormalizedTicket, QuarantineRecord,
                                  RoutingDecision, SourceLineage, SourceRecord, ValidationResult,
                                  VerificationReport)
from cloudserve.knowledge import resolve
from scripts.export_schemas import NAMES, export


def test_ticket_handoffs_export_and_reject_invalid_values(tmp_path):
    paths = export(tmp_path)
    assert len(paths) == len(NAMES) == 17
    assert all(json.loads(path.read_text())["title"] == path.name.split(".v1.")[0] for path in paths)
    passage = resolve("DOC-API-002#p04")
    assert passage
    bundle = EvidenceBundle(ticket_id="T-1", snapshot_revision=0, passages=[passage], searches=1, sufficient=True)
    assert EvidenceBundle.model_validate_json(bundle.model_dump_json()) == bundle
    with pytest.raises(ValidationError):
        EvidenceBundle(ticket_id="T-1", snapshot_revision=0, passages=[passage], searches=3, sufficient=True)
    with pytest.raises(ValidationError):
        DraftAnswer(ticket_id="T-1", text="Unsupported", claims=[AnswerClaim(text="Claim", supporting_passage_ids=[])], model_version="extractive-v1")
    fixtures = [
        NormalizedTicket(ticket_id="T-1", channel="chat", body="Question"),
        EventEnvelope(ticket_id="T-1", trace_id="trace", stage="classified", payload={}),
        ClassificationResult(intent="api_question", urgency="low", intent_confidence=0.8, urgency_confidence=0.7),
        RoutingDecision(action="escalate", reason_codes=["low_confidence"], reason="Review", threshold=0.9),
        DraftAnswer(ticket_id="T-1", text="Read the guide", claims=[AnswerClaim(text="Read the guide", supporting_passage_ids=[passage.passage_id])], model_version="extractive-v1"),
        VerificationReport(supported=True, citation_ids=[passage.passage_id], unsupported_claims=[], verifier_version="v1"),
        ValidationResult(valid=True, findings=[], validator_version="v1"),
        EscalationPacket(ticket_id="T-1", trace_id="trace", reason_codes=["review"], summary="Review", known=[], unknown=[], next_step="Inspect source"),
    ]
    for fixture in fixtures:
        assert type(fixture).model_validate_json(fixture.model_dump_json()) == fixture
    with pytest.raises(ValidationError):
        ClassificationResult(intent="x", urgency="low", intent_confidence=1.1, urgency_confidence=0.5)


def test_source_handoffs_roundtrip_and_quarantine_contract():
    record = SourceRecord(doc_id="DOC-API-002", source_hash="123456789abc", owner="Owner", authority="approved", content="Source text")
    assert SourceRecord.model_validate_json(record.model_dump_json()) == record
    doc = CanonicalDocument(doc_id=record.doc_id, title="API guide", content=record.content,
                            owner=record.owner, source_version=record.source_hash)
    assert CanonicalDocument.model_validate_json(doc.model_dump_json()) == doc
    passage = resolve("DOC-API-002#p04")
    assert passage
    chunk = KnowledgeChunk(**passage.model_dump(), permissions=["support"])
    assert KnowledgeChunk.model_validate_json(chunk.model_dump_json()) == chunk
    with pytest.raises(ValidationError):
        KnowledgeWorkItem(job_id="J-1", doc_id=record.doc_id, status="published_without_review", source_hash=record.source_hash)
    with pytest.raises(ValidationError):
        QuarantineRecord(job_id="J-1", doc_id=record.doc_id, reasons=[], source_hash=record.source_hash)
    fixtures = [
        KnowledgeWorkItem(job_id="J-1", doc_id=record.doc_id, status="pending_review", source_hash=record.source_hash),
        IndexManifest(snapshot_revision=1, documents=29, passages=145, index_version="lexical-v1", approved=True, dense_ready=False),
        SourceLineage(doc_id=record.doc_id, source_version=record.source_hash, passage_ids=[chunk.passage_id]),
        QuarantineRecord(job_id="J-2", doc_id=record.doc_id, reasons=["unsafe_source"], source_hash=record.source_hash),
    ]
    for fixture in fixtures:
        assert type(fixture).model_validate_json(fixture.model_dump_json()) == fixture
