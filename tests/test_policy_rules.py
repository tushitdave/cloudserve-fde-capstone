"""Rule-table conflict detection and lifecycle checks."""

import copy
import json
from datetime import date

from cloudserve import policy, policy_rules


def base():
    return copy.deepcopy(json.loads(policy.POLICY_PATH.read_text()))


def test_shipped_policy_has_no_errors_or_conflicts():
    report = policy_rules.validate(base())
    assert report["errors"] == [] and report["conflicts"] == []


def test_conflicting_actions_on_same_example_are_detected():
    p = base()
    p["rules"].append({"rule_id": "R-90", "priority": 90, "name": "auto_refund", "kind": "text_pattern",
                       "pattern": r"\brefund\b", "action": "answer", "reason": "x", "evidence": "x", "requirement_ids": ["FR04"],
                       "examples": {"match": [{"text": "I want a refund for last month", "intent": "billing_query"}]}})
    report = policy_rules.validate(p)
    assert report["conflicts"] and {"R-06", "R-90"} == set(report["conflicts"][0]["rules"])


def test_non_overlapping_windows_do_not_conflict():
    p = base()
    p["rules"].append({"rule_id": "R-91", "priority": 91, "name": "old_refund", "kind": "text_pattern", "pattern": r"\brefund\b",
                       "action": "answer", "reason": "x", "evidence": "x", "requirement_ids": ["FR04"],
                       "effective_from": "2020-01-01", "effective_to": "2020-12-31",
                       "examples": {"match": [{"text": "refund please", "intent": "billing_query"}]}})
    assert policy_rules.validate(p)["conflicts"] == []


def test_duplicate_priority_bad_regex_inverted_dates_and_failing_examples_are_errors():
    p = base()
    p["rules"][2]["priority"] = p["rules"][1]["priority"]
    assert any("priority" in e for e in policy_rules.validate(p)["errors"])
    p = base(); p["rules"][2]["pattern"] = "(unclosed"
    assert any("invalid pattern" in e for e in policy_rules.validate(p)["errors"])
    p = base(); p["rules"][2]["effective_from"], p["rules"][2]["effective_to"] = "2026-12-01", "2026-01-01"
    assert any("effective_to before" in e for e in policy_rules.validate(p)["errors"])
    p = base(); p["rules"][6]["examples"]["no_match"].append({"text": "please refund me", "intent": "billing_query"})
    assert any("negative example fires" in e for e in policy_rules.validate(p)["errors"])


def test_shadowed_rule_is_warned_and_unapproved_rule_is_inactive():
    p = base()
    p["rules"].append({"rule_id": "R-92", "priority": 92, "name": "dup_security", "kind": "text_pattern", "pattern": r"\bhacked\b",
                       "action": "escalate", "reason": "x", "evidence": "x", "requirement_ids": ["FR04"],
                       "examples": {"match": [{"text": "Our account was hacked last night", "intent": "account_access"}]}})
    assert any("R-92: shadowed" in w for w in policy_rules.validate(p)["warnings"])
    draft = {**p["rules"][-1], "approval_status": "draft"}
    assert not policy_rules.is_active(draft, p["effective_from"], date(2026, 12, 1))
    assert policy_rules.is_active(p["rules"][1], p["effective_from"], date(2026, 12, 1))
