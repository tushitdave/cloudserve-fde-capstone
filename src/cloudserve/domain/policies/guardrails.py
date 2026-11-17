"""Deterministic guardrails that run on every ticket and every draft.

Each check returns a record whether it passes or fails, so the decision log shows
what was checked (Build Specification, Validate). A failed check blocks release;
nothing here redacts-and-sends.
"""

import re

GUARDRAIL_VERSION = "guardrails-v2"

INSTRUCTION_INJECTION = re.compile(
    r"ignore (all |any |the |your )?(previous|prior|above|earlier|system) (instructions|prompts?|rules)"
    r"|disregard (all |any |the |your )?(previous|prior|system )?(instructions|rules|policy)"
    r"|(reveal|print|show) (me )?(the |your )?(system|hidden) prompt"
    r"|you are now (a|an|in) |act as (an? )?(admin|administrator|developer mode)"
    r"|override (the )?(safety|policy|guardrails?)",
    re.I,
)
FORBIDDEN_COMMITMENTS = re.compile(
    r"\b(refund (has been|was|will be) (issued|processed|approved)|credit (has been|was|will be) (applied|issued)"
    r"|(issue|problem|bug) (has been|was|is now) fixed on our side|fixed on our side|guarantee[sd]? (a |that |the )?(fix|resolution|uptime)"
    r"|will be (fixed|resolved|released|deployed) (by|on|within) |we will (refund|credit|compensate))",
    re.I,
)
PRIVATE_DATA = (
    ("email_address", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("api_key_or_secret", re.compile(r"\b(?:sk|api|key|tok)[-_][A-Za-z0-9]{16,}\b|\bAKIA[0-9A-Z]{16}\b")),
    ("payment_card", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    ("phone_number", re.compile(r"\+\d{1,3}[ -]?\(?\d{2,4}\)?[ -]?\d{3,4}[ -]?\d{3,4}\b")),
    ("customer_identifier", re.compile(r"\bCUST-\d{3,}\b")),
)


def check_input(subject: str, body: str) -> list[dict]:
    """Instruction-integrity check on untrusted customer text before any drafting."""
    match = INSTRUCTION_INJECTION.search(f"{subject} {body}")
    return [{"check": "instruction_integrity", "result": "fail" if match else "pass",
             "detail": f"matched: {match.group(0)[:80]}" if match else "no instruction-override pattern in ticket text"}]


def check_output(answer: str, cited_ids: list[str], retrieved_ids: set[str], customer_name: str = "") -> list[dict]:
    """Release checks on a draft. All results are returned; any `fail` blocks release."""
    results = []
    grounded = bool(cited_ids) and set(cited_ids).issubset(retrieved_ids)
    results.append({"check": "grounding_citations", "result": "pass" if grounded else "fail",
                    "detail": "every citation resolves to a retrieved approved passage" if grounded
                    else "missing_or_unretrieved_citation"})
    commitment = FORBIDDEN_COMMITMENTS.search(answer)
    results.append({"check": "tone_and_scope", "result": "fail" if commitment else "pass",
                    "detail": f"forbidden_commitment: {commitment.group(0)[:60]}" if commitment else "no refund, fix or timeline commitment"})
    found = [name for name, pattern in PRIVATE_DATA if pattern.search(answer)]
    if customer_name and len(customer_name) > 3 and customer_name.lower() in answer.lower():
        found.append("customer_name")
    results.append({"check": "private_data", "result": "fail" if found else "pass",
                    "detail": "possible_private_data: " + ", ".join(found) if found else "no private-data pattern in outbound text"})
    return results


def failures(results: list[dict]) -> list[str]:
    """Stable finding codes for failed checks (used in metrics and the UI)."""
    codes = []
    for item in results:
        if item["result"] != "fail":
            continue
        codes.append({"grounding_citations": "missing_or_unretrieved_citation", "tone_and_scope": "forbidden_commitment",
                      "private_data": "possible_private_data", "instruction_integrity": "instruction_integrity"}.get(item["check"], item["check"]))
    return codes
