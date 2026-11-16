"""One ticket use case shared by the API and unattended batch harness."""

import hashlib
import json
import re
import time
import uuid

from cloudserve.agents import AnswerAgent, EvidenceAgent, TriageAgent, VerificationAgent
from cloudserve.classifier import classify
from cloudserve.config import runtime_dir, setting
from cloudserve.contracts import Classification, Decision, EscalationPacket, Ticket, TicketResult, utc_now
from cloudserve.knowledge import resolve
from cloudserve.policy import AUTO_THRESHOLD, ANSWERABILITY_THRESHOLD, protected_reason, route
from cloudserve.storage import Store


class DuplicateConflict(ValueError):
    pass


class TicketService:
    def __init__(self, db_path=None):
        self.store = Store(db_path or runtime_dir() / "cloudserve.sqlite")
        self.triage = TriageAgent()
        self.evidence = EvidenceAgent()
        self.answer = AnswerAgent()
        self.verification = VerificationAgent()

    def process(self, raw: dict, mode: str | None = None) -> TicketResult:
        started = time.perf_counter()
        raw = raw if isinstance(raw, dict) else {"body": str(raw)}
        ticket_id = str(raw.get("ticket_id") or f"CS-{uuid.uuid4().hex[:10].upper()}")
        channel = raw.get("channel", "chat")
        invalid_channel = not isinstance(channel, str) or channel not in {"email", "chat", "docs_comment", "forum"}
        ticket = Ticket(
            ticket_id=ticket_id, channel=channel if not invalid_channel else "chat",
            subject=str(raw.get("subject") or ""), body=str(raw.get("body") or ""),
            received_at=str(raw.get("received_at") or utc_now()),
            customer_id=str(raw.get("customer_id") or "anonymous"),
            customer_tier=str(raw.get("customer_tier") or "unknown"),
            customer_region=str(raw.get("customer_region") or "unknown"),
            language_fluency=str(raw.get("language_fluency") or "unknown"),
        )
        payload_hash = hashlib.sha256(json.dumps(raw, sort_keys=True, default=str).encode()).hexdigest()
        previous = self.store.get(ticket_id)
        if previous:
            if previous[0] != payload_hash:
                raise DuplicateConflict(f"ticket_id {ticket_id} already exists with different input")
            return previous[1]
        trace_id = uuid.uuid4().hex
        steps: list[str] = []
        events: list[tuple[str, dict]] = [("normalized", {"ticket_id": ticket_id, "channel": ticket.channel,
                                                      "subject": ticket.subject, "body": ticket.body,
                                                      "received_at": ticket.received_at, "input_hash": payload_hash})]
        findings: list[str] = []
        citations = []
        answer = ""
        reason_override = ""
        chosen_mode = mode or setting("CLOUDSERVE_MODEL_MODE", "extractive")
        if chosen_mode not in {"extractive", "azure"}:
            chosen_mode = "extractive"
        try:
            classification = classify(ticket)
            events.append(("classified", classification.model_dump()))
            if invalid_channel:
                decision = Decision(action="escalate", reason_codes=["invalid_channel"], reason="Unrecognized ticket channel.", threshold=AUTO_THRESHOLD)
            elif not ticket.subject.strip() and not ticket.body.strip():
                decision = Decision(action="escalate", reason_codes=["empty_ticket"], reason="The request has no usable description.", threshold=AUTO_THRESHOLD)
            elif protected_reason(ticket, classification):
                decision = route(ticket, classification)
            elif classification.intent_confidence < AUTO_THRESHOLD:
                steps.append("Triage Agent")
                assessment = self.triage.assess(ticket, classification)
                events.append(("triage_reviewed", assessment))
                decision = route(ticket, classification)
            elif classification.answerability_confidence < ANSWERABILITY_THRESHOLD:
                decision = route(ticket, classification)
            else:
                steps.append("Evidence Agent")
                passages, searches = self.evidence.gather(ticket, classification)
                events.append(("evidence", {"passage_ids": [p.passage_id for p in passages], "searches": searches}))
                decision = route(ticket, classification, passages[0].score if passages else 0)
                if decision.action == "answer":
                    steps.append("Answer Agent")
                    answer = self.answer.draft(ticket, passages, chosen_mode)
                    events.append(("drafted", {"citation_ids": re.findall(r"\[([A-Z0-9-]+#p\d+)\]", answer), "mode": chosen_mode}))
                    if answer.strip().upper().startswith("ABSTAIN"):
                        reason_override = "answer_abstained"
                    else:
                        steps.append("Verification Agent")
                        verdict = self.verification.verify(answer, passages, chosen_mode)
                        events.append(("verified", verdict))
                        if not verdict["supported"]:
                            findings.append(verdict["reason"])
                        cited_ids = set(verdict["citations"])
                        citations = [p for p in passages if p.passage_id in cited_ids and
                                     (active := resolve(p.passage_id)) and active.source_version == p.source_version]
                        if not citations:
                            findings.append("citation_resolution_failed")
                        if re.search(r"\b(refund (has been|was) issued|fixed on our side|guarantee[sd]? a fix)\b", answer, re.I):
                            findings.append("forbidden_commitment")
                        if re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|(?:sk|api)[-_][A-Za-z0-9]{16,}", answer):
                            findings.append("possible_private_data")
                        if findings:
                            reason_override = "guardrail_blocked"
            events.append(("routed", decision.model_dump()))
        except Exception as error:
            # Fail closed for model, retrieval, verifier, and malformed draft
            # failures. Persistence remains outside this block: a storage
            # failure must be visible rather than pretending a handoff exists.
            classification = locals().get("classification") or Classification(intent="unknown", urgency="medium", intent_confidence=0, urgency_confidence=0)
            decision = Decision(action="escalate", reason_codes=["processing_failure"], reason="A processing dependency was unavailable.", threshold=AUTO_THRESHOLD)
            events.append(("failure", {"type": type(error).__name__}))
        if reason_override:
            decision = Decision(action="escalate", reason_codes=[reason_override], reason="Draft could not pass the answer safety gate.", threshold=AUTO_THRESHOLD)
        sent = decision.action == "answer" and bool(answer) and not findings
        summary = None if sent else f"Review {classification.intent} request. Reason: {decision.reason} Customer said: {(ticket.subject + ' ' + ticket.body)[:400]}"
        packet = None if sent else EscalationPacket(
            ticket_id=ticket_id, trace_id=trace_id, reason_codes=decision.reason_codes,
            summary=summary or "", known=[f"Channel: {ticket.channel}", f"Predicted intent: {classification.intent}", f"Predicted urgency: {classification.urgency}"],
            unknown=["Customer-specific account state and final resolution are unverified."],
            next_step="Review the original request and approved sources; resolve with a support specialist.",
            candidate_passage_ids=[p.passage_id for p in locals().get("passages", [])],
        )
        result = TicketResult(
            ticket_id=ticket_id, trace_id=trace_id, terminal_state="sent" if sent else "escalated",
            customer_message=answer if sent else "A support specialist will review this request. Your ticket has been recorded.",
            classification=classification, decision=decision, citations=citations if sent else [],
            escalation_summary=summary, escalation_packet=packet, guardrail_findings=findings, agent_steps=steps,
            latency_ms=round((time.perf_counter() - started) * 1000),
        )
        events.append(("terminal", {"state": result.terminal_state, "reason_codes": decision.reason_codes, "guardrail_findings": findings}))
        self.store.save(payload_hash, result, events)
        return result
