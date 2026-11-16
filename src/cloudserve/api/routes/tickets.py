"""Demo API routes; production identity and tenant authorization remain future gates."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal

from cloudserve.contracts import HumanResolution, TicketResult
from cloudserve.service import DuplicateConflict, TicketService
from cloudserve.storage import NotEscalated, ResolutionConflict

router = APIRouter(prefix="/v1")
service = TicketService()


class FeedbackIn(BaseModel):
    ticket_id: str
    rating: str
    comment: str = ""


class ResolutionIn(BaseModel):
    reviewer: str
    resolution_type: Literal["answered_by_human", "closed_without_answer"]
    notes: str


@router.post("/tickets", response_model=TicketResult)
def submit_ticket(payload: dict) -> TicketResult:
    try:
        return service.process(payload)
    except DuplicateConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/tickets")
def recent_tickets(limit: int = 30):
    return service.store.list_results(max(1, min(limit, 100)))


@router.get("/tickets/{ticket_id}", response_model=TicketResult)
def get_ticket(ticket_id: str) -> TicketResult:
    result = service.store.get(ticket_id)
    if not result:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return result[1]


@router.get("/tickets/{ticket_id}/decision")
def get_decision(ticket_id: str):
    result = service.store.get(ticket_id)
    if not result:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"ticket_id": ticket_id, "trace_id": result[1].trace_id, "events": service.store.events(ticket_id)}


@router.get("/escalations")
def escalations(limit: int = 30, include_resolved: bool = False):
    return service.store.list_results(max(1, min(limit, 100)), state="escalated", pending_only=not include_resolved)


@router.post("/escalations/{ticket_id}/resolve", response_model=HumanResolution)
def resolve_escalation(ticket_id: str, payload: ResolutionIn) -> HumanResolution:
    if not payload.reviewer.strip() or len(payload.notes.strip()) < 10:
        raise HTTPException(status_code=422, detail="Reviewer and at least 10 characters of resolution notes are required")
    resolution = HumanResolution(ticket_id=ticket_id, reviewer=payload.reviewer.strip(),
                                 resolution_type=payload.resolution_type, notes=payload.notes.strip())
    try:
        return service.store.resolve_escalation(resolution)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Ticket not found") from error
    except (NotEscalated, ResolutionConflict) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/feedback")
def feedback(payload: FeedbackIn):
    if not service.store.get(payload.ticket_id):
        raise HTTPException(status_code=404, detail="Ticket not found")
    service.store.add_feedback(payload.ticket_id, payload.rating, payload.comment)
    return {"status": "recorded", "ticket_id": payload.ticket_id}


@router.get("/metrics")
def metrics():
    return service.store.counts()
