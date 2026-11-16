import json

from cloudserve.agents import EvidenceAgent
from cloudserve.classifier import classify
from cloudserve.config import supplied
from cloudserve.contracts import EvidenceBundle, Ticket
from evaluation.query_rewrite_eval import evaluate


def test_evidence_agent_emits_bounded_typed_bundle(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDSERVE_RUNTIME_DIR", str(tmp_path))
    row = next(item for item in json.loads(supplied("development_tickets.json").read_text()) if item["ticket_id"] == "DEV-0026")
    ticket = Ticket.model_validate(row)
    agent = EvidenceAgent()
    plan = agent.plan(ticket, classify(ticket))
    bundle = agent.gather(ticket, classify(ticket))
    assert plan.max_searches <= 2 and bundle.searches <= 2
    assert isinstance(bundle, EvidenceBundle)
    assert bundle.ticket_id == ticket.ticket_id and bundle.snapshot_revision == plan.source_revision
    assert len(bundle.queries) == bundle.searches
    assert all(p.doc_id in plan.allowed_doc_ids for p in bundle.passages)
    assert EvidenceBundle.model_validate_json(bundle.model_dump_json()) == bundle


def test_rewrite_diagnostic_reports_gain_harm_and_budget(tmp_path):
    rows = json.loads(supplied("development_tickets.json").read_text())[:10]
    path = tmp_path / "sample.json"
    path.write_text(json.dumps(rows))
    report = evaluate(path)
    assert report["tickets"] == 10
    assert report["bounded_search_violations"] == 0
    assert report["rewrite_gain"] >= 0 and report["rewrite_harm"] >= 0
