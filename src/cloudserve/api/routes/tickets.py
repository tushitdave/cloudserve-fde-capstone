"""Ticket, decision, handoff, feedback, metrics and data-retention routes.

Every route except /health requires an API key (`X-API-Key`). Customers act only
inside their own tenant; an object outside it is reported as not found so its
existence is not revealed (OWASP API1, broken object-level authorization).
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from cloudserve.contracts import HumanResolution, TicketResult
from cloudserve.security import Principal, require
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


class PurgeIn(BaseModel):
    days: int = Field(ge=1, le=3650)


def _visible(principal: Principal, ticket_id: str) -> TicketResult:
    found = service.store.get(ticket_id)
    if not found or not principal.can_see_tenant(service.store.tenant_of(ticket_id)):
        raise HTTPException(status_code=404, detail="Ticket not found")
    return found[1]


@router.post("/tickets", response_model=TicketResult)
def submit_ticket(payload: dict, principal: Principal = Depends(require("customer", "support_agent"))) -> TicketResult:
    if principal.tenant != "*":
        if payload.get("customer_id") not in (None, "", principal.tenant):
            raise HTTPException(status_code=403, detail="A customer may only raise tickets for its own account")
        payload = {**payload, "customer_id": principal.tenant}
    try:
        return service.process(payload)
    except DuplicateConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/tickets")
def recent_tickets(limit: int = 30, principal: Principal = Depends(require("customer", "support_agent"))):
    tenant = None if principal.tenant == "*" else principal.tenant
    return service.store.list_results(max(1, min(limit, 100)), tenant_id=tenant)


@router.get("/tickets/{ticket_id}", response_model=TicketResult)
def get_ticket(ticket_id: str, principal: Principal = Depends(require("customer", "support_agent"))) -> TicketResult:
    return _visible(principal, ticket_id)


@router.get("/tickets/{ticket_id}/decision")
def get_decision(ticket_id: str, principal: Principal = Depends(require("support_agent"))):
    result = _visible(principal, ticket_id)
    return {"ticket_id": ticket_id, "trace_id": result.trace_id, "events": service.store.events(ticket_id)}


@router.get("/escalations")
def escalations(limit: int = 30, include_resolved: bool = False, principal: Principal = Depends(require("support_agent"))):
    return service.store.list_results(max(1, min(limit, 100)), state="escalated", pending_only=not include_resolved)


@router.post("/escalations/{ticket_id}/resolve", response_model=HumanResolution)
def resolve_escalation(ticket_id: str, payload: ResolutionIn, principal: Principal = Depends(require("support_agent"))) -> HumanResolution:
    if not payload.reviewer.strip() or len(payload.notes.strip()) < 10:
        raise HTTPException(status_code=422, detail="Reviewer and at least 10 characters of resolution notes are required")
    resolution = HumanResolution(ticket_id=ticket_id, reviewer=payload.reviewer.strip(), resolution_type=payload.resolution_type,
                                 notes=payload.notes.strip(), reviewer_key_id=principal.key_id)
    try:
        return service.store.resolve_escalation(resolution)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Ticket not found") from error
    except (NotEscalated, ResolutionConflict) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/feedback")
def feedback(payload: FeedbackIn, principal: Principal = Depends(require("customer", "support_agent"))):
    _visible(principal, payload.ticket_id)
    service.store.add_feedback(payload.ticket_id, payload.rating, payload.comment)
    return {"status": "recorded", "ticket_id": payload.ticket_id}


@router.get("/metrics")
def metrics(principal: Principal = Depends(require("support_agent", "operator", "knowledge_owner"))):
    return service.store.counts()


@router.delete("/customers/{customer_id}/data")
def erase_customer_data(customer_id: str, principal: Principal = Depends(require())):
    """Admin only: erase raw customer text; decision records without raw text are kept for audit."""
    return {"customer_id": customer_id, "tickets_erased": service.store.erase_customer(customer_id), "by": principal.key_id}


@router.post("/admin/retention/purge")
def purge(payload: PurgeIn, principal: Principal = Depends(require())):
    return {"days": payload.days, "tickets_erased": service.store.purge_older_than(payload.days), "by": principal.key_id}
