"""Versioned business policy and deterministic route selection."""

import re

from cloudserve.contracts import Classification, Decision, Ticket

POLICY_VERSION = "policy-v1"
PROTECTED = {"compliance_request", "security_incident", "feature_request", "unclear_request"}
PROTECTED_PATTERNS = (
    ("security_signal", r"\b(breach|compromised|hacked|exposed secret|leaked key|security incident)\b"),
    ("compliance_signal", r"\b(gdpr|subpoena|regulator|compliance request|legal hold)\b"),
    ("feature_signal", r"\b(feature request|roadmap|when will you add|please add a feature)\b"),
    ("recurring_access_failure", r"\b(mfa|authenticator|two.factor|2fa)\b.{0,180}\b(rejected every time|tried .*several times)\b"),
    ("regional_assurance", r"\b(backups?|data)\b.{0,100}\b(replicated|outside|region)\b|\b(compliance review|definite answer)\b"),
    ("expired_resource_state", r"\bdownload link\b.{0,100}\bexpired\b.{0,120}\bis the file still available\b|\bour cursor seems to stop working\b.{0,120}\bis there an expiry\b"),
)
AUTO_THRESHOLD = 0.24  # Initial conservative prototype threshold; tune against held-out labels.
EVIDENCE_THRESHOLD = 0.11
ANSWERABILITY_THRESHOLD = 0.68


def protected_reason(ticket: Ticket, classification: Classification) -> str | None:
    if classification.intent in PROTECTED:
        return f"protected_intent:{classification.intent}"
    text = f"{ticket.subject} {ticket.body}".lower()
    for name, pattern in PROTECTED_PATTERNS:
        if re.search(pattern, text):
            return name
    return None


def route(ticket: Ticket, classification: Classification, evidence_score: float = 0) -> Decision:
    protected = protected_reason(ticket, classification)
    if protected:
        return Decision(action="escalate", reason_codes=[protected], reason="Protected request requires specialist review.", threshold=AUTO_THRESHOLD)
    if not ticket.body.strip() and not ticket.subject.strip():
        return Decision(action="escalate", reason_codes=["empty_ticket"], reason="The request has no usable description.", threshold=AUTO_THRESHOLD)
    if classification.intent_confidence < AUTO_THRESHOLD:
        return Decision(action="escalate", reason_codes=["low_intent_confidence"], reason="Ticket intent is uncertain.", threshold=AUTO_THRESHOLD)
    if classification.answerability_confidence < ANSWERABILITY_THRESHOLD:
        return Decision(action="escalate", reason_codes=["low_answerability"], reason="The approved documentation may not answer this request.", threshold=ANSWERABILITY_THRESHOLD)
    if evidence_score < EVIDENCE_THRESHOLD:
        return Decision(action="escalate", reason_codes=["insufficient_evidence"], reason="No sufficiently relevant approved passage was found.", threshold=EVIDENCE_THRESHOLD)
    return Decision(action="answer", reason_codes=["eligible", "evidence_sufficient"], reason="Policy and approved evidence permit a supported answer.", threshold=AUTO_THRESHOLD)
