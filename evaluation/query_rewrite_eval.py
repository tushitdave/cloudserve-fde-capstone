"""Document-label diagnostic for the Evidence Agent's single query rewrite."""

import argparse
import json
from pathlib import Path

from cloudserve.agents import EvidenceAgent
from cloudserve.classifier import classify
from cloudserve.contracts import Ticket
from cloudserve.knowledge import retrieve


def evaluate(input_path: Path) -> dict:
    rows = json.loads(input_path.read_text())
    agent = EvidenceAgent()
    report = {"tickets": len(rows), "eligible_plans": 0, "rewrite_invocations": 0,
              "first_doc_hits": 0, "rewrite_doc_hits": 0, "rewrite_gain": 0, "rewrite_harm": 0,
              "final_doc_hits": 0, "bounded_search_violations": 0}
    for row in rows:
        if not isinstance(row, dict) or not row.get("ticket_id"):
            continue
        ticket = Ticket.model_validate(row)
        classification = classify(ticket)
        plan = agent.plan(ticket, classification)
        if plan.path != "approved_document":
            continue
        report["eligible_plans"] += 1
        allowed = set(plan.allowed_doc_ids)
        expected = set(row.get("labels", {}).get("expected_doc_ids", []))
        first = [p for p in retrieve(plan.query, limit=5, allowed_doc_ids=allowed) if p.section == "Resolution"]
        rewritten = f"{classification.intent.replace('_', ' ')} {plan.query}"
        second = [p for p in retrieve(rewritten, limit=5, allowed_doc_ids=allowed) if p.section == "Resolution"]
        first_ok = bool(first and first[0].score >= 0.11 and first[0].doc_id in expected)
        second_ok = bool(second and second[0].score >= 0.11 and second[0].doc_id in expected)
        report["first_doc_hits"] += int(first_ok)
        report["rewrite_doc_hits"] += int(second_ok)
        report["rewrite_gain"] += int(not first_ok and second_ok)
        report["rewrite_harm"] += int(first_ok and not second_ok)
        bundle = agent.gather(ticket, classification)
        report["rewrite_invocations"] += int(bundle.searches == 2)
        report["bounded_search_violations"] += int(bundle.searches > 2 or len(bundle.queries) > 2)
        report["final_doc_hits"] += int(bool(bundle.sufficient and bundle.passages and bundle.passages[0].doc_id in expected))
    report["limitations"] = ["Development tickets trained the intent and document predictors.",
                             "Expected document IDs are supplied labels, not human-adjudicated passage relevance.",
                             "Candidate rewrite harm compares a hypothetical second query; the agent only uses a rewrite when the first evidence is weak and retains the better score."]
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "limitations"}))
