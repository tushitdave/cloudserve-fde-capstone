"""LangGraph orchestration of the ticket-serving pipeline (Research/11 canonical architecture).

Nodes map one-to-one to the architecture's ticket path:

    classify → policy_gate ─┬─ escalate (protected rule / kill switch / invalid / empty /
                            │            instruction-override guardrail / novel request)
                            ├─ triage ──► escalate (low calibrated intent confidence)
                            └─ evidence ─┬─ escalate (no approved article / insufficient evidence)
                                         └─ answer ─┬─ escalate (abstained)
                                                    └─ verify_validate ──► release | escalate

Agents only propose; every routing decision is taken in code (`cloudserve.policy`).
The graph mutates one `TicketRun` context object so that, if a node raises, the
events recorded before the failure are kept and the service can fail closed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from cloudserve import guardrails, policy
from cloudserve.classifier import classify
from cloudserve.contracts import Ticket
from cloudserve.knowledge import resolve
from cloudserve.observability.tracing import traced_stage, tracer


@dataclass
class TicketRun:
    ticket: Ticket
    raw: dict
    invalid_channel: bool
    mode: str
    service: Any
    events: list = field(default_factory=list)
    steps: list = field(default_factory=list)
    findings: list = field(default_factory=list)
    guardrail_results: list = field(default_factory=list)
    passages: list = field(default_factory=list)
    draft_passages: list = field(default_factory=list)
    citations: list = field(default_factory=list)
    classification: Any = None
    decision: Any = None
    bundle: Any = None
    answer: str = ""
    reason_override: str = ""
    evidence_score: float = 0.0
    next: str = ""
    trace_id: str = ""
    stage_timings_ms: dict = field(default_factory=dict)


class GraphState(TypedDict):
    run: TicketRun


# ------------------------------------------------------------------ nodes
def classify_node(state: GraphState) -> GraphState:
    run = state["run"]
    run.classification = classify(run.ticket)
    run.events.append(("classified", run.classification.model_dump()))
    return state


def policy_gate_node(state: GraphState) -> GraphState:
    run, ticket, c = state["run"], state["run"].ticket, state["run"].classification
    if run.invalid_channel:
        run.decision, run.next = policy.escalate("invalid_channel", "Unrecognized ticket channel."), "escalate"
    elif not ticket.subject.strip() and not ticket.body.strip():
        run.decision, run.next = policy.escalate("empty_ticket", "The request has no usable description."), "escalate"
    elif policy.kill_switch_state()["active"] or policy.fired_rules(ticket, c):
        run.decision, run.next = policy.route(ticket, c), "escalate"
    else:
        run.guardrail_results.extend(guardrails.check_input(ticket.subject, ticket.body))
        run.findings.extend(guardrails.failures(run.guardrail_results))
        if run.findings:
            run.decision = policy.escalate("guardrail_blocked", "The ticket text tries to change the system's instructions; it was recorded for review.")
            run.next = "escalate"
        elif c.nearest_training_similarity < policy.NOVELTY_THRESHOLD:
            run.decision, run.next = policy.route(ticket, c), "escalate"
        elif c.intent_confidence < policy.AUTO_THRESHOLD:
            run.next = "triage"
        else:
            run.next = "evidence"
    return state


def triage_node(state: GraphState) -> GraphState:
    run = state["run"]
    run.steps.append("Triage Agent")
    run.events.append(("triage_reviewed", run.service.triage.assess(run.ticket, run.classification, run.mode)))
    run.decision, run.next = policy.route(run.ticket, run.classification), "escalate"
    return state


def evidence_node(state: GraphState) -> GraphState:
    run = state["run"]
    run.steps.append("Evidence Agent")
    bundle = run.service.evidence.gather(run.ticket, run.classification, mode=run.mode)
    run.bundle, run.passages, run.evidence_score = bundle, bundle.passages, bundle.top_score
    run.events.append(("evidence", {"passage_ids": [p.passage_id for p in bundle.passages], "searches": bundle.searches,
                                    "scores": {p.passage_id: p.score for p in bundle.passages},
                                    "retrieval_strategy": bundle.retrieval_strategy, "fallback_reason": bundle.fallback_reason,
                                    "document_id": bundle.document_id, "document_confidence": bundle.document_confidence,
                                    "snapshot_revision": bundle.snapshot_revision, "sufficient": bundle.sufficient,
                                    "reason": bundle.reason, "queries": bundle.queries}))
    run.decision = policy.route(run.ticket, run.classification, run.evidence_score,
                                has_approved_article=bundle.reason != "no_approved_article",
                                retrieval_strategy=bundle.retrieval_strategy)
    run.next = "answer" if run.decision.action == "answer" else "escalate"
    return state


def answer_node(state: GraphState) -> GraphState:
    run = state["run"]
    run.draft_passages = [run.passages[0], *run.bundle.supporting_passages]
    run.steps.append("Answer Agent")
    run.answer = run.service.answer.draft(run.ticket, run.draft_passages, run.mode)
    if not isinstance(run.answer, str):
        raise TypeError("draft must be text")
    run.events.append(("drafted", {"citation_ids": re.findall(r"\[([A-Z0-9-]+#p\d+)\]", run.answer), "mode": run.mode,
                                   "prompt_version": run.service.answer.PROMPT_VERSION.get(run.mode)}))
    if run.answer.strip().upper().startswith("ABSTAIN"):
        run.reason_override, run.next = "answer_abstained", "escalate"
    else:
        run.next = "verify"
    return state


def verify_validate_node(state: GraphState) -> GraphState:
    run = state["run"]
    run.steps.append("Verification Agent")
    verdict = run.service.verification.verify(run.answer, run.draft_passages, run.mode)
    run.events.append(("verified", verdict))
    cited_ids = list(dict.fromkeys(verdict["citations"]))
    run.guardrail_results.extend(guardrails.check_output(run.answer, cited_ids, {p.passage_id for p in run.draft_passages},
                                                         str(run.raw.get("customer_name") or "")))
    # A missing citation is already reported by grounding_citations; avoid a duplicate finding.
    claim_ok = verdict["supported"] or verdict["reason"] == "missing_or_unretrieved_citation"
    run.guardrail_results.append({"check": "claim_support", "result": "pass" if claim_ok else "fail", "detail": verdict["reason"]})
    run.citations = [p for p in run.draft_passages if p.passage_id in cited_ids and
                     (active := resolve(p.passage_id)) and active.source_version == p.source_version]
    if len(run.citations) != len(cited_ids):
        run.guardrail_results.append({"check": "citation_version", "result": "fail", "detail": "citation_resolution_failed"})
    run.findings.extend(f for f in guardrails.failures(run.guardrail_results) if f not in run.findings)
    if "claim_support" in run.findings:
        run.findings[run.findings.index("claim_support")] = verdict["reason"]
    if "citation_version" in run.findings:
        run.findings[run.findings.index("citation_version")] = "citation_resolution_failed"
    if run.findings:
        run.reason_override, run.next = "guardrail_blocked", "escalate"
    elif policy.kill_switch_state()["active"]:
        # Tickets in flight when the switch is thrown are held, not sent.
        run.decision, run.next = policy.route(run.ticket, run.classification), "escalate"
    else:
        run.next = "release"
    return state


# ------------------------------------------------------------------ graph
def _next(state: GraphState) -> str:
    return state["run"].next


AGENTS = {"classify": "classifier", "policy_gate": "policy_engine", "triage": "triage_agent", "evidence": "evidence_agent",
          "answer": "answer_agent", "verify_validate": "verification_agent+validator"}
NODES = {"classify": classify_node, "policy_gate": policy_gate_node, "triage": triage_node, "evidence": evidence_node,
         "answer": answer_node, "verify_validate": verify_validate_node}


def _instrumented(name: str):
    node = NODES[name]

    def wrapper(state: GraphState) -> GraphState:
        budget = int(policy.POLICY.get("agent_budgets_ms", {}).get(name, 20000))
        return traced_stage(name, AGENTS[name], budget, lambda: node(state), state["run"])

    return wrapper


@lru_cache(maxsize=1)
def ticket_graph():
    graph = StateGraph(GraphState)
    for name in NODES:
        graph.add_node(name, _instrumented(name))
    graph.add_edge(START, "classify")
    graph.add_edge("classify", "policy_gate")
    graph.add_conditional_edges("policy_gate", _next, {"escalate": END, "triage": "triage", "evidence": "evidence"})
    graph.add_conditional_edges("triage", _next, {"escalate": END, "evidence": "evidence"})
    graph.add_conditional_edges("evidence", _next, {"escalate": END, "answer": "answer"})
    graph.add_conditional_edges("answer", _next, {"escalate": END, "verify": "verify_validate"})
    graph.add_conditional_edges("verify_validate", _next, {"escalate": END, "release": END})
    return graph.compile()


def run_ticket_graph(run: TicketRun) -> TicketRun:
    """Execute the bounded graph inside one ticket span; at most one pass per node, no cycles."""
    with tracer().start_as_current_span("cloudserve.ticket") as span:
        span.set_attribute("cloudserve.ticket_id", run.ticket.ticket_id)
        span.set_attribute("cloudserve.trace_id", run.trace_id)
        span.set_attribute("cloudserve.channel", run.ticket.channel)
        ticket_graph().invoke({"run": run})
        span.set_attribute("cloudserve.decision", run.decision.action if run.decision else "none")
    return run
