from cloudserve.contracts import HumanResolution
from cloudserve.service import TicketService
from cloudserve.storage import NotEscalated, ResolutionConflict


def protected_ticket():
    return {"ticket_id": "HITL-1", "channel": "chat", "subject": "Possible incident",
            "body": "A production key was exposed in a security incident."}


def test_human_resolution_preserves_terminal_result_and_audit(tmp_path):
    service = TicketService(tmp_path / "tickets.sqlite")
    original = service.process(protected_ticket())
    assert original.terminal_state == "escalated"
    assert [item.ticket_id for item in service.store.list_results(state="escalated", pending_only=True)] == [original.ticket_id]
    resolution = HumanResolution(ticket_id=original.ticket_id, reviewer="Support reviewer",
                                 resolution_type="answered_by_human", notes="Reviewed account and sent verified guidance.")
    saved = service.store.resolve_escalation(resolution)
    assert saved == service.store.resolve_escalation(HumanResolution(**resolution.model_dump(exclude={"resolved_at"})))
    assert service.store.get(original.ticket_id)[1].human_resolution == saved
    assert service.store.get(original.ticket_id)[1].terminal_state == "escalated"
    assert service.store.list_results(state="escalated", pending_only=True) == []
    events = service.store.events(original.ticket_id)
    assert [event["stage"] for event in events].count("human_resolved") == 1
    assert events[-1]["trace_id"] == original.trace_id
    assert service.store.counts()["open_handoffs"] == 0
    assert service.store.counts()["human_resolved"] == 1


def test_resolution_conflict_and_non_escalated_ticket(tmp_path):
    service = TicketService(tmp_path / "tickets.sqlite")
    service.process(protected_ticket())
    service.store.resolve_escalation(HumanResolution(ticket_id="HITL-1", reviewer="A",
                                                      resolution_type="closed_without_answer", notes="No approved answer was available."))
    try:
        service.store.resolve_escalation(HumanResolution(ticket_id="HITL-1", reviewer="B",
                                                          resolution_type="answered_by_human", notes="Different decision."))
    except ResolutionConflict:
        pass
    else:
        raise AssertionError("Expected conflict")
    assert len([event for event in service.store.events("HITL-1") if event["stage"] == "human_resolved"]) == 1
    # A documented question follows the automatic answer path and cannot be resolved again.
    service.process({"ticket_id": "AUTO-1", "channel": "chat", "subject": "Pagination returns duplicate records",
                     "body": "When I page through results I am seeing some records twice and missing others entirely. The collection does change while I iterate. Am I doing this the wrong way?"})
    assert service.store.get("AUTO-1")[1].terminal_state == "sent"
    try:
        service.store.resolve_escalation(HumanResolution(ticket_id="AUTO-1", reviewer="A",
                                                          resolution_type="answered_by_human", notes="Not applicable to an automatic answer."))
    except NotEscalated:
        pass
    else:
        raise AssertionError("Expected non-escalated rejection")
