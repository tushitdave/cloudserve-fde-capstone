"""Versioned business-rule engine, data-selected thresholds and the kill switch.

Rules live in `policy_v2.json` (versioned, owned, evidence-linked). Code here only
evaluates them; it never invents a rule. Every decision records the rule IDs that
fired and the exact thresholds applied so it can be reconstructed later.
"""

import json
import os
import re
from functools import lru_cache
from pathlib import Path

from cloudserve.config import runtime_dir
from cloudserve.contracts import Classification, Decision, Ticket, utc_now

POLICY_PATH = Path(__file__).with_name("policy_v2.json")


@lru_cache(maxsize=1)
def load_policy() -> dict:
    policy = json.loads(POLICY_PATH.read_text())
    priorities = [rule["priority"] for rule in policy["rules"]]
    if len(priorities) != len(set(priorities)):
        raise ValueError("Policy rules must have unique priorities (conflict detection)")
    for rule in policy["rules"]:
        if "pattern" in rule:
            re.compile(rule["pattern"])
    return policy


POLICY = load_policy()
POLICY_VERSION = POLICY["policy_version"]
THRESHOLDS = POLICY["thresholds"]
AUTO_THRESHOLD = float(THRESHOLDS["intent_confidence"])
DOCUMENT_THRESHOLD = float(THRESHOLDS["document_confidence"])
EVIDENCE_THRESHOLD = float(THRESHOLDS["evidence_score"])
NOVELTY_THRESHOLD = float(THRESHOLDS["min_training_similarity"])
PROTECTED = set(next(rule["intents"] for rule in POLICY["rules"] if rule["name"] == "protected_intent"))


# ---------------------------------------------------------------- kill switch
def _kill_switch_path() -> Path:
    return runtime_dir() / "kill_switch.json"


def kill_switch_state() -> dict:
    """Read on every ticket, so a change takes effect on the next decision without a deploy."""
    if os.environ.get("CLOUDSERVE_AUTO_SEND_DISABLED", "").strip().lower() in {"1", "true", "yes"}:
        return {"active": True, "source": "environment", "operator": "deployment", "reason": "CLOUDSERVE_AUTO_SEND_DISABLED set"}
    path = _kill_switch_path()
    if path.exists():
        try:
            state = json.loads(path.read_text())
            return {"active": bool(state.get("active")), "source": "runtime_file", **{k: state.get(k) for k in ("operator", "reason", "changed_at")}}
        except (ValueError, OSError):
            # An unreadable switch file fails closed: stop automatic answers.
            return {"active": True, "source": "runtime_file", "operator": None, "reason": "kill switch file unreadable"}
    return {"active": False, "source": "default", "operator": None, "reason": None}


def set_kill_switch(active: bool, operator: str, reason: str) -> dict:
    path = _kill_switch_path()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"active": active, "operator": operator, "reason": reason, "changed_at": utc_now()}))
    temporary.replace(path)
    return kill_switch_state()


# ---------------------------------------------------------------- rules
def _rule_matches(rule: dict, ticket: Ticket, classification: Classification) -> bool:
    text = f"{ticket.subject} {ticket.body}".lower()
    kind = rule["kind"]
    if kind == "intent_in":
        return classification.intent in rule["intents"]
    if kind == "text_pattern":
        return re.search(rule["pattern"], text) is not None
    if kind == "intent_and_pattern":
        return classification.intent in rule["intents"] and re.search(rule["pattern"], text) is not None
    return False


def fired_rules(ticket: Ticket, classification: Classification) -> list[dict]:
    return [rule for rule in sorted(POLICY["rules"], key=lambda r: r["priority"])
            if rule["kind"] != "kill_switch" and _rule_matches(rule, ticket, classification)]


def protected_reason(ticket: Ticket, classification: Classification) -> str | None:
    rules = fired_rules(ticket, classification)
    if not rules:
        return None
    first = rules[0]
    return f"protected_intent:{classification.intent}" if first["name"] == "protected_intent" else first["name"]


def thresholds_applied() -> dict:
    return {"intent_confidence": AUTO_THRESHOLD, "min_training_similarity": NOVELTY_THRESHOLD,
            "document_confidence": DOCUMENT_THRESHOLD, "evidence_score": EVIDENCE_THRESHOLD}


def _decision(action: str, codes: list[str], reason: str, threshold: float, rule_ids: list[str] | None = None) -> Decision:
    return Decision(action=action, reason_codes=codes, reason=reason, policy_version=POLICY_VERSION, threshold=threshold,
                    rule_ids_fired=rule_ids or [], thresholds_applied=thresholds_applied())


def escalate(code: str, reason: str, threshold: float | None = None, rule_ids: list[str] | None = None) -> Decision:
    return _decision("escalate", [code], reason, AUTO_THRESHOLD if threshold is None else threshold, rule_ids)


def route(ticket: Ticket, classification: Classification, evidence_score: float = 0, has_approved_article: bool = True) -> Decision:
    """Deterministic: identical ticket, classification and policy version give an identical decision."""
    if kill_switch_state()["active"]:
        rule = POLICY["rules"][0]
        return escalate("kill_switch_active", rule["reason"], rule_ids=[rule["rule_id"]])
    rules = fired_rules(ticket, classification)
    if rules:
        code = protected_reason(ticket, classification) or rules[0]["name"]
        return escalate(code, rules[0]["reason"], rule_ids=[rule["rule_id"] for rule in rules])
    if not ticket.body.strip() and not ticket.subject.strip():
        return escalate("empty_ticket", "The request has no usable description.")
    if classification.nearest_training_similarity < NOVELTY_THRESHOLD:
        return escalate("novel_request", "The request does not resemble any request type the system has learnt; new issues go to a person.",
                        threshold=NOVELTY_THRESHOLD)
    if classification.intent_confidence < AUTO_THRESHOLD:
        return escalate("low_intent_confidence", f"The ticket type is uncertain (confidence {classification.intent_confidence:.2f} is below {AUTO_THRESHOLD:.2f}).")
    if not has_approved_article:
        return escalate("no_approved_article", "No approved article covers this type of request.")
    if evidence_score < EVIDENCE_THRESHOLD:
        return escalate("insufficient_evidence", f"No approved passage was relevant enough (best score {evidence_score:.2f}, needed {EVIDENCE_THRESHOLD:.2f}).",
                        threshold=EVIDENCE_THRESHOLD)
    return _decision("answer", ["eligible", "evidence_sufficient"],
                     f"No protective rule fired, intent confidence {classification.intent_confidence:.2f} ≥ {AUTO_THRESHOLD:.2f} "
                     f"and approved evidence score {evidence_score:.2f} ≥ {EVIDENCE_THRESHOLD:.2f}.", AUTO_THRESHOLD)
