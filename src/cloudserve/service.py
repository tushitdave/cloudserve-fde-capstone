"""One ticket use case shared by the API and unattended batch harness."""

import hashlib
import json
import re
import time
import uuid

from cloudserve.agents import AnswerAgent, EvidenceAgent, TriageAgent, VerificationAgent
from cloudserve.classifier import classify
from cloudserve.config import runtime_dir, setting
from cloudserve.contracts import Classification, EscalationPacket, Ticket, TicketResult, utc_now
from cloudserve.knowledge import resolve
from cloudserve import guardrails, policy
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
        guardrail_results: list[dict] = []
        citations = []
        passages = []
        answer = ""
        reason_override = ""
        evidence_score = 0.0
        chosen_mode = mode or setting("CLOUDSERVE_MODEL_MODE", "extractive")
        if chosen_mode not in {"extractive", "azure"}:
            chosen_mode = "extractive"
        try:
            classification = classify(ticket)
            events.append(("classified", classification.model_dump()))
            if invalid_channel:
                decision = policy.escalate("invalid_channel", "Unrecognized ticket channel.")
            elif not ticket.subject.strip() and not ticket.body.strip():
                decision = policy.escalate("empty_ticket", "The request has no usable description.")
            elif policy.kill_switch_state()["active"] or policy.fired_rules(ticket, classification):
                decision = policy.route(ticket, classification)
            else:
                guardrail_results.extend(guardrails.check_input(ticket.subject, ticket.body))
                findings.extend(guardrails.failures(guardrail_results))
                if findings:
                    decision = policy.escalate("guardrail_blocked", "The ticket text tries to change the system's instructions; it was recorded for review.")
                elif classification.nearest_training_similarity < policy.NOVELTY_THRESHOLD:
                    decision = policy.route(ticket, classification)
                elif classification.intent_confidence < policy.AUTO_THRESHOLD:
                    steps.append("Triage Agent")
                    events.append(("triage_reviewed", self.triage.assess(ticket, classification)))
                    decision = policy.route(ticket, classification)
                else:
                    steps.append("Evidence Agent")
                    bundle = self.evidence.gather(ticket, classification)
                    passages = bundle.passages
                    evidence_score = bundle.top_score
                    events.append(("evidence", {"passage_ids": [p.passage_id for p in passages], "searches": bundle.searches,
                                                "scores": {p.passage_id: p.score for p in passages},
                                                "document_id": bundle.document_id, "document_confidence": bundle.document_confidence,
                                                "snapshot_revision": bundle.snapshot_revision, "sufficient": bundle.sufficient,
                                                "reason": bundle.reason, "queries": bundle.queries}))
                    decision = policy.route(ticket, classification, evidence_score,
                                            has_approved_article=bundle.reason != "no_approved_article")
                    if decision.action == "answer":
                        draft_passages = [passages[0], *bundle.supporting_passages]
                        steps.append("Answer Agent")
                        answer = self.answer.draft(ticket, draft_passages, chosen_mode)
                        if not isinstance(answer, str):
                            raise TypeError("draft must be text")
                        events.append(("drafted", {"citation_ids": re.findall(r"\[([A-Z0-9-]+#p\d+)\]", answer), "mode": chosen_mode,
                                                   "prompt_version": self.answer.PROMPT_VERSION.get(chosen_mode)}))
                        if answer.strip().upper().startswith("ABSTAIN"):
                            reason_override = "answer_abstained"
                        else:
                            steps.append("Verification Agent")
                            verdict = self.verification.verify(answer, draft_passages, chosen_mode)
                            events.append(("verified", verdict))
                            cited_ids = list(dict.fromkeys(verdict["citations"]))
                            guardrail_results.extend(guardrails.check_output(answer, cited_ids, {p.passage_id for p in draft_passages},
                                                                              str(raw.get("customer_name") or "")))
                            # A missing citation is already reported by grounding_citations; avoid a duplicate finding.
                            claim_ok = verdict["supported"] or verdict["reason"] == "missing_or_unretrieved_citation"
                            guardrail_results.append({"check": "claim_support", "result": "pass" if claim_ok else "fail",
                                                      "detail": verdict["reason"]})
                            citations = [p for p in draft_passages if p.passage_id in cited_ids and
                                         (active := resolve(p.passage_id)) and active.source_version == p.source_version]
                            if len(citations) != len(cited_ids):
                                guardrail_results.append({"check": "citation_version", "result": "fail", "detail": "citation_resolution_failed"})
                            findings.extend(f for f in guardrails.failures(guardrail_results) if f not in findings)
                            if "claim_support" in findings:
                                findings[findings.index("claim_support")] = verdict["reason"]
                            if "citation_version" in findings:
                                findings[findings.index("citation_version")] = "citation_resolution_failed"
                            if findings:
                                reason_override = "guardrail_blocked"
                            elif policy.kill_switch_state()["active"]:
                                # Tickets in flight when the switch is thrown are held, not sent.
                                decision = policy.route(ticket, classification)
            events.append(("routed", decision.model_dump()))
        except Exception as error:
            # Fail closed for model, retrieval, verifier, and malformed draft
            # failures. Persistence remains outside this block: a storage
            # failure must be visible rather than pretending a handoff exists.
            classification = locals().get("classification") or Classification(intent="unknown", urgency="medium", intent_confidence=0, urgency_confidence=0)
            decision = policy.escalate("processing_failure", "A processing dependency was unavailable.")
            events.append(("failure", {"type": type(error).__name__}))
        if reason_override:
            decision = policy.escalate(reason_override, "Draft could not pass the answer safety gate." if reason_override == "guardrail_blocked"
                                       else "The answer step declined to answer from the available evidence.")
        sent = decision.action == "answer" and bool(answer) and not findings
        summary = None if sent else (f"Review {classification.intent.replace('_', ' ')} request "
                                     f"(urgency {classification.urgency}). Why escalated: {decision.reason} "
                                     f"Customer said: {(ticket.subject + ' ' + ticket.body).strip()[:400]}")
        unknown = ["Customer-specific account state and final resolution are unverified."]
        if classification.intent_confidence < policy.AUTO_THRESHOLD:
            unknown.insert(0, "Which request type applies: " + ", ".join(
                [classification.intent, *[a["intent"] for a in classification.alternatives[:2]]]))
        if passages and not sent:
            unknown.insert(0, "Whether the candidate passages actually answer this ticket (not validated for release).")
        packet = None if sent else EscalationPacket(
            ticket_id=ticket_id, trace_id=trace_id, reason_codes=decision.reason_codes,
            summary=summary or "",
            known=[f"Channel: {ticket.channel}", f"Customer tier: {ticket.customer_tier}",
                   f"Predicted intent: {classification.intent} ({classification.intent_confidence:.2f})",
                   f"Predicted urgency: {classification.urgency} ({classification.urgency_confidence:.2f})",
                   *[f"Guardrail: {f}" for f in findings]],
            unknown=unknown,
            next_step=_next_step(decision.reason_codes),
            candidate_passage_ids=[p.passage_id for p in passages],
        )
        result = TicketResult(
            ticket_id=ticket_id, trace_id=trace_id, terminal_state="sent" if sent else "escalated",
            customer_message=answer if sent else ("We have passed your request to a support specialist, together with the details you sent. "
                                                  "You do not need to resend anything; the specialist will reply on this ticket."),
            classification=classification, decision=decision, citations=citations if sent else [],
            escalation_summary=summary, escalation_packet=packet, guardrail_findings=findings,
            guardrail_results=guardrail_results, agent_steps=steps,
            latency_ms=round((time.perf_counter() - started) * 1000),
        )
        events.append(("decision", _decision_record(result, ticket, payload_hash, passages, evidence_score, chosen_mode, self)))
        events.append(("terminal", {"state": result.terminal_state, "reason_codes": decision.reason_codes, "guardrail_findings": findings}))
        self.store.save(payload_hash, result, events)
        return result


NEXT_STEPS = {
    "protected": "A specialist must handle this category directly; check the customer's account and policy before replying.",
    "low_intent_confidence": "Confirm which request type applies (options listed under Unknown), then answer or route.",
    "insufficient_evidence": "No approved passage clearly answers this; check the candidate passages and, if none fit, flag a documentation gap to the knowledge owner.",
    "no_approved_article": "There is no approved article for this request type; answer from specialist knowledge and consider a new article.",
    "guardrail_blocked": "A safety check blocked the automatic reply; read the guardrail finding before reusing any drafted text.",
    "processing_failure": "A dependency failed; handle manually. The ticket is safe to answer from the approved sources.",
    "kill_switch_active": "Automatic answers are switched off; handle as a normal manual ticket.",
    "novel_request": "This looks unlike known request types; it may be a new incident or out of scope. Investigate before answering.",
}

REQUIREMENTS_BY_CODE = {
    "eligible": ["FR05", "FR07"], "insufficient_evidence": ["FR06"], "no_approved_article": ["FR06"],
    "low_intent_confidence": ["FR03"], "guardrail_blocked": ["FR07", "NFR05"], "processing_failure": ["FR02", "FR06"],
    "kill_switch_active": ["NFR05"], "empty_ticket": ["FR01"], "invalid_channel": ["FR01"],
}


def _next_step(codes: list[str]) -> str:
    code = codes[0] if codes else ""
    if code.startswith("protected_intent") or code.endswith("_signal") or code in {"data_location_assurance"}:
        return NEXT_STEPS["protected"]
    return NEXT_STEPS.get(code, "Review the original request and approved sources; resolve with a support specialist.")


def _decision_record(result: TicketResult, ticket: Ticket, input_hash: str, passages: list, evidence_score: float,
                     mode: str, service: "TicketService") -> dict:
    """Governance Framework minimum decision record, written for every ticket."""
    code = result.decision.reason_codes[0] if result.decision.reason_codes else ""
    if result.terminal_state == "sent":
        action = "auto_respond"
    elif "guardrail_blocked" in result.decision.reason_codes:
        action = "block"
    else:
        action = "escalate"
    requirement_ids = REQUIREMENTS_BY_CODE.get(code, ["FR04"] if result.decision.rule_ids_fired else ["FR02"])
    return {
        "decision_id": f"{result.ticket_id}:{result.trace_id[:12]}",
        "timestamp": result.completed_at,
        "ticket_id": result.ticket_id,
        "stage": "validation" if result.guardrail_results else "routing",
        "input_summary": {"channel": ticket.channel, "chars": len(ticket.subject) + len(ticket.body), "input_sha256": input_hash},
        "model": {"name": "classifier", "version": result.classification.model_version, "calibrated": result.classification.calibrated},
        "prediction": {"intent": result.classification.intent, "confidence": result.classification.intent_confidence,
                       "urgency": result.classification.urgency, "urgency_confidence": result.classification.urgency_confidence},
        "alternatives": result.classification.alternatives,
        "sources_used": [{"doc_id": p.doc_id, "passage_id": p.passage_id, "score": p.score, "source_version": p.source_version} for p in passages],
        "evidence_score": evidence_score,
        "threshold_applied": result.decision.thresholds_applied,
        "rule_ids_fired": result.decision.rule_ids_fired,
        "policy_version": result.decision.policy_version,
        "action_taken": action,
        "reason": result.decision.reason,
        "guardrail_results": {item["check"]: item["result"] for item in result.guardrail_results},
        "guardrail_version": guardrails.GUARDRAIL_VERSION,
        "prompt_version": service.answer.PROMPT_VERSION.get(mode) if result.terminal_state == "sent" or result.guardrail_results else None,
        "verifier_version": service.verification.VERSION.get(mode) if result.guardrail_results else None,
        "requirement_ids": requirement_ids,
    }
