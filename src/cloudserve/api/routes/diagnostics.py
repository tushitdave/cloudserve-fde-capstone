"""Evaluator-facing operational, retrieval, graph and gold diagnostics."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from fastapi import APIRouter, Depends, Query

from cloudserve.adapters.azure.openai_client import usage_snapshot
from cloudserve.adapters.persistence.knowledge_store import KnowledgeStore
from cloudserve.adapters.persistence.ticket_store import Store
from cloudserve.adapters.retrieval.dense_index import DENSE_MODEL, RERANK_MODEL, dense_collection, warm_up
from cloudserve.adapters.retrieval.knowledge_graph import snapshot as graph_snapshot, traverse
from cloudserve.adapters.retrieval.knowledge_index import retrieve_with_strategy
from cloudserve.api.security import require
from cloudserve.config import APP_ROOT, runtime_dir
from cloudserve.domain.policies import policy

router = APIRouter(prefix="/v1/diagnostics", tags=["diagnostics"])


def _json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _jsonl(path: Path) -> list[dict]:
    try:
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError):
        return []


def _latest_metrics(name: str) -> dict:
    preferred = {
        "development": APP_ROOT / "evaluation/reports/development-hex/metrics.json",
        "validation": APP_ROOT / "evaluation/reports/validation-policy-v3/metrics.json",
    }[name]
    live = _json(preferred)
    if live:
        return live
    return _json(APP_ROOT / "data/manifests/offline_evaluation_v1.json").get(name, {})


def _gold_summary() -> dict:
    root = APP_ROOT / "evaluation/gold"
    manifest = _json(root / "manifest_v1.json")
    queue = _jsonl(root / "review_queue_v1.jsonl")
    reviewer_a = _jsonl(root / "reviewer_a_completed_v1.jsonl")
    reviewer_b = _jsonl(root / "reviewer_b_completed_v1.jsonl")
    adjudicated = _jsonl(root / "adjudicated_v2.jsonl")
    agreement = _json(root / "reviewer_agreement_v1.json")
    approved = [row for row in adjudicated if row.get("review_status") == "approved"]
    no_answer = sum(row.get("answerable_from_frozen_kb") is False for row in approved)
    return {
        "gold_version": manifest.get("gold_version", "unavailable"),
        "queue_total": len(queue) or manifest.get("review_queue_count", 0),
        "reviewer_a_completed": sum(bool(row.get("reviewer_name") and row.get("route")) for row in reviewer_a),
        "reviewer_b_completed": sum(bool(row.get("reviewer_name") and row.get("route")) for row in reviewer_b),
        "adjudicated": len(approved),
        "passage_relevance_labelled": sum(bool(row.get("passage_labels") or row.get("gold_passage_ids")) for row in approved),
        "explicit_no_answer": no_answer,
        "required_claim_annotations": sum(bool(row.get("required_claims")) for row in approved),
        "forbidden_claim_annotations": sum(bool(row.get("forbidden_claims")) for row in approved),
        "claim_support_adjudicated": sum(row.get("claim_support_reviewed") is True for row in approved),
        "escalation_quality_reviewed": sum(row.get("escalation_quality") is not None for row in approved),
        "hallucination_reviewed": sum(row.get("hallucination_reviewed") is True for row in approved),
        "agreement": agreement or None,
        "status": "human_adjudicated" if approved else "pending_two_independent_human_reviews",
        "warning": "Candidate passages and supplied labels are seeds, not human-approved gold." if not approved else None,
    }


@router.get("/overview")
def overview(_principal=Depends(require("support_agent", "operator", "knowledge_owner"))):
    store = Store(runtime_dir() / "cloudserve.sqlite")
    knowledge_jobs = KnowledgeStore().list_jobs(10000)
    job_counts = Counter(job["status"] for job in knowledge_jobs)
    try:
        collection = dense_collection()
        chroma = {"status": "ready", "collection": collection.name, "passages": collection.count(),
                  "dimension": 384, "embedding_model": DENSE_MODEL, "metadata": collection.metadata}
    except Exception as error:
        chroma = {"status": "unavailable", "reason": type(error).__name__, "embedding_model": DENSE_MODEL}
    return {
        "retrieval": {"selected_strategy": policy.RETRIEVAL_STRATEGY, "available_strategies": ["lexical", "dense", "hybrid", "hybrid_rerank"],
                      "reranker_model": RERANK_MODEL, "warm_up": warm_up(), "chroma": chroma},
        "graph": graph_snapshot(),
        "outbox": store.outbox_health(),
        "model_usage": usage_snapshot(),
        "gold": _gold_summary(),
        "closed_loop": {"knowledge_jobs_by_status": dict(job_counts), "human_resolutions": store.counts()["human_resolved"],
                        "approval_boundary": "human approval required before KB publication"},
        "offline": {"development": _latest_metrics("development"), "validation": _latest_metrics("validation")},
    }


@router.get("/retrieval")
def retrieval_comparison(q: str = Query(min_length=2, max_length=1000), limit: int = Query(5, ge=1, le=10),
                         _principal=Depends(require("support_agent", "operator", "knowledge_owner"))):
    results = {}
    for strategy in ("lexical", "dense", "hybrid", "hybrid_rerank"):
        passages, used, fallback = retrieve_with_strategy(q, limit=limit, strategy=strategy)
        results[strategy] = {"strategy_used": used, "fallback_reason": fallback,
                             "candidates": [{"passage_id": p.passage_id, "doc_id": p.doc_id, "title": p.title,
                                             "section": p.section, "score": p.score} for p in passages]}
    return {"query": q, "score_warning": "Ranking scores are strategy-specific and are not calibrated probabilities.", "results": results}


@router.get("/graph/traverse")
def graph_traverse(seed_doc_id: list[str] = Query(default=[]), max_hops: int = Query(1, ge=1, le=2),
                   _principal=Depends(require("support_agent", "operator", "knowledge_owner"))):
    graph = graph_snapshot()
    all_ids = {node["id"] for node in graph["nodes"]}
    seeds = set(seed_doc_id) or set(sorted(all_ids)[:1])
    return traverse(seeds, all_ids, max_hops=max_hops)
