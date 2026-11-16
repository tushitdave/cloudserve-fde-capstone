"""Chroma/MiniLM hybrid retrieval, reranker, LangGraph orchestration, ML registry and drift."""

import json

import pytest

from cloudserve import policy, retrieval
from cloudserve.config import supplied
from cloudserve.knowledge import retrieve_with_strategy
from cloudserve.ml_registry import REGISTRY_PATH, build_registry, drift_report, promotion_check
from cloudserve.orchestration.ticket_graph import ticket_graph
from cloudserve.service import TicketService


def documented_ticket():
    row = next(r for r in json.loads(supplied("development_tickets.json").read_text()) if r["ticket_id"] == "DEV-0026")
    return {k: v for k, v in row.items() if k not in ("labels", "history")}


def test_policy_selects_hybrid_with_lexical_fallback_threshold():
    assert policy.RETRIEVAL_STRATEGY == "hybrid"
    assert set(policy.EVIDENCE_BY_STRATEGY) >= {"hybrid", "lexical"}


def test_dense_retrieval_bridges_vocabulary_gap_and_respects_permissions():
    # Ines's example: customer wording does not share terms with the article title.
    query = "my deployment keeps dying and restarting"
    lexical, _, _ = retrieve_with_strategy(query, 3, None, "lexical")
    dense, used, fallback = retrieve_with_strategy(query, 3, None, "dense")
    assert used == "dense" and fallback is None
    assert dense[0].doc_id == "DOC-DEPLOY-001" and lexical[0].doc_id != "DOC-DEPLOY-001"
    assert retrieval.dense_scores("my deployment keeps dying", None, role="no_such_role") == {}


def test_reranker_returns_bounded_scores():
    passages, used, _ = retrieve_with_strategy("rotate an api key", 3, None, "hybrid_rerank")
    assert used == "hybrid_rerank" and all(0 < p.score < 1 for p in passages)


def test_dense_outage_falls_back_to_lexical_and_is_logged(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDSERVE_RUNTIME_DIR", str(tmp_path / "runtime"))

    def down(*_args, **_kwargs):
        raise retrieval.RetrievalUnavailable("dense index unavailable: test outage")

    monkeypatch.setattr(retrieval, "dense_scores", down)
    service = TicketService(tmp_path / "t.sqlite")
    result = service.process(documented_ticket())
    evidence = next(e for e in service.store.events(result.ticket_id) if e["stage"] == "evidence")["payload"]
    assert evidence["retrieval_strategy"] == "lexical" and "test outage" in evidence["fallback_reason"]
    assert result.terminal_state in {"sent", "escalated"}


def test_ticket_graph_has_architecture_nodes_and_no_cycles():
    graph = ticket_graph().get_graph()
    nodes = set(graph.nodes)
    assert {"classify", "policy_gate", "triage", "evidence", "answer", "verify_validate"} <= nodes
    edges = {(e.source, e.target) for e in graph.edges}
    assert ("evidence", "classify") not in edges and ("verify_validate", "answer") not in edges


def test_registry_matches_running_models_and_records_lineage():
    stored = json.loads(REGISTRY_PATH.read_text())
    current = build_registry()
    assert [m["artifact_sha256"] for m in stored["models"]] == [m["artifact_sha256"] for m in current["models"]]
    entry = stored["models"][0]
    assert entry["dataset"]["visible_validation_used"] is False and entry["promotion"]["status"] == "promoted"
    assert stored["retraining_criteria"] and stored["drift_thresholds"]


def test_drift_monitor_flags_out_of_distribution_batch():
    texts = ["Please write me a poem about clouds"] * 250
    report = drift_report(texts, ["unclear_request"] * 250, [0.4] * 250, [0.05] * 250, 0.35)
    assert {"novel_share", "intent_psi"} <= set(report["alerts"]) and report["retrain_recommended"]


def test_promotion_check_blocks_regressions():
    base = {"per_class_precision": {"a": 0.9}, "protected_false_auto": 0, "fluency_gap_points": 3.0, "p95_ms": 100}
    worse = {"per_class_precision": {"a": 0.8}, "protected_false_auto": 1, "fluency_gap_points": 9.0, "p95_ms": 400}
    result = promotion_check(worse, base)
    assert not result["promote"] and len(result["reasons"]) == 4
    assert promotion_check(base, base)["promote"]
