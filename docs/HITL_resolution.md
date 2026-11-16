# Human handoff resolution — local prototype

The initial ticket result stays immutable: `terminal_state` is `sent` or `escalated`. A support reviewer may add one `HumanResolution` to an escalated ticket. The resolution stores reviewer, outcome (`answered_by_human` or `closed_without_answer`), notes and timestamp. A `human_resolved` audit event carries the original trace ID. It does **not** send a customer message or modify the approved knowledge base.

## UI check

1. Restart the backend if it was started without reload, then refresh `http://localhost:5173`.
2. In **Ticket lab**, choose **Protected request** and process it. The result should say **Human review required**.
3. In **Human handoffs**, open that ticket. Enter your name and at least 10 characters of notes, choose the outcome, and press **Record human outcome**.
4. The result should show **Human review completed**. The ticket should leave the open handoff queue; Overview and Metrics should show one human-resolved action. The original decision remains escalated in the ticket and decision trace.

## API contract

`POST /v1/escalations/{ticket_id}/resolve` accepts:

```json
{
  "reviewer": "Support reviewer",
  "resolution_type": "answered_by_human",
  "notes": "Verified the issue and responded through support."
}
```

An identical replay returns the existing resolution. A different second resolution or a non-escalated ticket returns 409; unknown ticket returns 404; missing reviewer or short notes return 422. `GET /v1/escalations` lists open handoffs by default; `?include_resolved=true` includes completed reviews. `GET /v1/tickets/{id}` includes `human_resolution` when present. `GET /v1/tickets/{id}/decision` includes the `human_resolved` event. Metrics add `open_handoffs` and `human_resolved`.

This is a **local demo workflow**. Reviewer identity is a typed name, not authenticated identity. Role/object authorization and a supervised correction-to-KB workflow must be added before production or external access. The `closed_without_answer` outcome is an audit closure, not a resolved customer issue or first-contact resolution.
