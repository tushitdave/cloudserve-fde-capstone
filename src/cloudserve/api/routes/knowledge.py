"""Local-demo knowledge intake, human review, publication and lineage API."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from cloudserve.knowledge import index, manifest, passages_from_documents, resolve
from cloudserve.knowledge_pipeline import KnowledgeService
from cloudserve.knowledge_store import KnowledgeConflict, _content_hash
from cloudserve.storage import Store
from cloudserve.config import runtime_dir

router = APIRouter(prefix="/v1/knowledge", tags=["knowledge"])
service = KnowledgeService()


class DocumentIn(BaseModel):
    doc_id: str
    title: str
    content: str
    owner: str
    category: str = ""
    applies_to: str = ""
    related_docs: list[str] = []


class ReviewIn(BaseModel):
    reviewer: str
    note: str


class PublishIn(BaseModel):
    operator: str


@router.post("/jobs")
def stage_document(payload: DocumentIn):
    return service.stage(payload.model_dump())


@router.get("/jobs")
def jobs(limit: int = 50):
    return service.store.list_jobs(max(1, min(limit, 100)))


@router.get("/jobs/{job_id}")
def job(job_id: str):
    found = service.store.get_job(job_id)
    if not found:
        raise HTTPException(status_code=404, detail="Knowledge job not found")
    return {**found, "events": service.store.events(job_id)}


@router.post("/jobs/{job_id}/approve")
def approve(job_id: str, payload: ReviewIn):
    try:
        return service.review(job_id, payload.reviewer, payload.note, True)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Knowledge job not found") from error
    except (ValueError, KnowledgeConflict) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/jobs/{job_id}/reject")
def reject(job_id: str, payload: ReviewIn):
    try:
        return service.review(job_id, payload.reviewer, payload.note, False)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Knowledge job not found") from error
    except (ValueError, KnowledgeConflict) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/jobs/{job_id}/publish")
def publish(job_id: str, payload: PublishIn):
    try:
        return service.publish(job_id, payload.operator)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Knowledge job not found") from error
    except (ValueError, KnowledgeConflict) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/indexes/active")
def active_index():
    return manifest()


@router.get("/passages/{passage_id:path}")
def passage(passage_id: str, source_version: str | None = None):
    found = resolve(passage_id, source_version)
    if not found:
        raise HTTPException(status_code=404, detail="Passage or source version not found")
    return found


@router.get("/documents")
def documents():
    passages, _, _ = index()
    return list({p.doc_id: {"doc_id": p.doc_id, "title": p.title, "source_version": p.source_version,
                            "passage_count": sum(1 for candidate in passages if candidate.doc_id == p.doc_id)} for p in passages}.values())


@router.get("/documents/{doc_id}")
def document(doc_id: str):
    found = next((doc for doc in service.store.active_documents() if doc["doc_id"] == doc_id), None)
    if not found:
        raise HTTPException(status_code=404, detail="Document not found")
    return {**found, "source_version": _content_hash(found), "publication": service.store.active_metadata(doc_id)}


@router.get("/documents/{doc_id}/versions")
def versions(doc_id: str):
    found = service.store.versions(doc_id)
    if not found:
        raise HTTPException(status_code=404, detail="Document not found")
    return found


@router.get("/documents/{doc_id}/lineage")
def lineage(doc_id: str, source_version: str | None = None):
    found = (service.store.source_version(doc_id, source_version) if source_version else
             next((doc for doc in service.store.active_documents() if doc["doc_id"] == doc_id), None))
    if not found:
        raise HTTPException(status_code=404, detail="Document or source version not found")
    passages = passages_from_documents([found])
    tickets = Store(runtime_dir() / "cloudserve.sqlite").list_results(limit=100000)
    cited_by = {p.passage_id: [ticket.ticket_id for ticket in tickets if any(c.passage_id == p.passage_id and c.source_version == p.source_version for c in ticket.citations)] for p in passages}
    publication = next((item for item in service.store.versions(doc_id) if item["source_hash"] == _content_hash(found)), None)
    return {"doc_id": doc_id, "title": found["title"], "owner": found.get("owner", "unknown"), "source_version": _content_hash(found),
            "publication": publication, "related_docs": found.get("related_docs", []),
            "passages": [{"passage_id": p.passage_id, "section": p.section, "source_version": p.source_version,
                          "start_offset": p.start_offset, "end_offset": p.end_offset,
                          "text": p.text, "cited_by_ticket_ids": cited_by[p.passage_id]} for p in passages]}
