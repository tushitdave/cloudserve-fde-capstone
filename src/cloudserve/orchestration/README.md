# Orchestration

- `ticket_graph.py`: LangGraph state graph of the ticket pipeline, with OpenTelemetry spans and per-node time budgets.
- `agents/roles.py`: the six bounded agent roles (Source Intake, Knowledge Steward, Triage, Evidence, Answer, Verification).

Agents propose; the domain policy decides. Must not import the API layer.
