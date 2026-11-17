"""Rule-table validation and conflict detection (Research/02: versioned rules with
priority, effective dates, owner, approval and regression tests; conflicting active
rules are detected before publication).

The algorithm is example-driven because rules mix intent conditions and regular
expressions, whose overlap cannot be decided statically in general:

1. Schema: required fields, known kind/action, regex compiles.
2. Identity: unique rule IDs and unique priorities (a tie gives no deterministic order).
3. Lifecycle: effective_from ≤ effective_to; only `approved` rules inside their window are active.
4. Regression: every positive example must fire its rule; every negative must not.
5. Conflict: for each pair of active rules whose windows overlap and whose actions
   differ, any example from either rule that fires both is a conflict.
6. Shadowing (warning): a rule all of whose positive examples are already caught by a
   higher-priority rule with the same action never changes an outcome.
"""

import re
from datetime import date

KINDS = {"kill_switch", "intent_in", "text_pattern", "intent_and_pattern"}
ACTIONS = {"escalate", "answer"}
REQUIRED = ("rule_id", "priority", "name", "kind", "action", "reason", "evidence", "requirement_ids")


def _day(value):
    return date.fromisoformat(value) if value else None


def matches(rule: dict, text: str, intent: str) -> bool:
    text = text.lower()
    kind = rule["kind"]
    if kind == "intent_in":
        return intent in rule["intents"]
    if kind == "text_pattern":
        return re.search(rule["pattern"], text) is not None
    if kind == "intent_and_pattern":
        return intent in rule["intents"] and re.search(rule["pattern"], text) is not None
    return False


def is_active(rule: dict, policy_from: str | None, on: date | None = None) -> bool:
    on = on or date.today()
    start = _day(rule.get("effective_from") or policy_from)
    end = _day(rule.get("effective_to"))
    return rule.get("approval_status", "approved") == "approved" and (start is None or start <= on) and (end is None or on <= end)


def _windows_overlap(a: dict, b: dict, policy_from: str | None) -> bool:
    a_start, b_start = _day(a.get("effective_from") or policy_from), _day(b.get("effective_from") or policy_from)
    a_end, b_end = _day(a.get("effective_to")), _day(b.get("effective_to"))
    return (a_end is None or b_start is None or b_start <= a_end) and (b_end is None or a_start is None or a_start <= b_end)


def validate(policy: dict) -> dict:
    errors, warnings = [], []
    rules = policy.get("rules", [])
    policy_from = policy.get("effective_from")
    ids, priorities = {}, {}
    for rule in rules:
        rid = rule.get("rule_id", "?")
        missing = [key for key in REQUIRED if key not in rule]
        if missing:
            errors.append(f"{rid}: missing fields {missing}")
            continue
        if rule["kind"] not in KINDS:
            errors.append(f"{rid}: unknown kind {rule['kind']}")
        if rule["action"] not in ACTIONS:
            errors.append(f"{rid}: unknown action {rule['action']}")
        if "pattern" in rule:
            try:
                re.compile(rule["pattern"])
            except re.error as error:
                errors.append(f"{rid}: invalid pattern ({error})")
        if rid in ids:
            errors.append(f"{rid}: duplicate rule_id")
        ids[rid] = rule
        if rule["priority"] in priorities:
            errors.append(f"{rid}: priority {rule['priority']} also used by {priorities[rule['priority']]}")
        priorities[rule["priority"]] = rid
        start, end = _day(rule.get("effective_from") or policy_from), _day(rule.get("effective_to"))
        if start and end and end < start:
            errors.append(f"{rid}: effective_to before effective_from")
        if rule["kind"] != "kill_switch" and not rule.get("examples", {}).get("match"):
            warnings.append(f"{rid}: no positive examples; regression and conflict checks are weaker")
    if errors:
        return {"errors": errors, "warnings": warnings, "conflicts": []}

    checkable = [r for r in rules if r["kind"] != "kill_switch" and r.get("approval_status", "approved") == "approved"]
    for rule in checkable:
        for example in rule.get("examples", {}).get("match", []):
            if not matches(rule, example["text"], example.get("intent", "")):
                errors.append(f"{rule['rule_id']}: positive example does not fire: {example['text']!r}")
        for example in rule.get("examples", {}).get("no_match", []):
            if matches(rule, example["text"], example.get("intent", "")):
                errors.append(f"{rule['rule_id']}: negative example fires: {example['text']!r}")

    conflicts = []
    for i, a in enumerate(checkable):
        for b in checkable[i + 1:]:
            if a["action"] == b["action"] or not _windows_overlap(a, b, policy_from):
                continue
            for example in a.get("examples", {}).get("match", []) + b.get("examples", {}).get("match", []):
                if matches(a, example["text"], example.get("intent", "")) and matches(b, example["text"], example.get("intent", "")):
                    conflicts.append({"rules": [a["rule_id"], b["rule_id"]], "actions": [a["action"], b["action"]],
                                      "example": example["text"]})
                    break
    for c in conflicts:
        errors.append(f"conflict {c['rules'][0]} ({c['actions'][0]}) vs {c['rules'][1]} ({c['actions'][1]}) on {c['example']!r}")

    ordered = sorted(checkable, key=lambda r: r["priority"])
    for i, rule in enumerate(ordered):
        positives = rule.get("examples", {}).get("match", [])
        if positives and all(any(h["action"] == rule["action"] and matches(h, e["text"], e.get("intent", "")) for h in ordered[:i])
                             for e in positives):
            warnings.append(f"{rule['rule_id']}: shadowed by higher-priority rules for all its examples")
    return {"errors": errors, "warnings": warnings, "conflicts": conflicts}
