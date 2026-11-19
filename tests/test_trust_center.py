"""Evaluator-facing graph, retrieval and operational diagnostics."""

import asyncio
import json

from cloudserve.adapters.retrieval.knowledge_graph import snapshot, traverse
from cloudserve.main import app


async def request(path: str, query: bytes = b""):
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET",
             "scheme": "http", "path": path, "raw_path": path.encode(), "query_string": query,
             "root_path": "", "headers": [(b"x-api-key", b"demo-admin-key")],
             "client": ("127.0.0.1", 0), "server": ("test", 80)}
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    await app(scope, receive, send)
    return sent[0]["status"], json.loads(sent[-1]["body"])


def test_graph_snapshot_and_traversal_never_leave_authorised_scope():
    graph = snapshot()
    assert graph["node_count"] == 29 and graph["edge_count"] > 0
    authorised = {"DOC-API-001", "DOC-API-002"}
    result = traverse({"DOC-API-001"}, authorised, max_hops=2)
    assert result["scope_enforced"] is True
    assert set(result["expanded_doc_ids"]).issubset(authorised)
    assert all(edge["source"] in authorised and edge["target"] in authorised for edge in result["edges"])


def test_diagnostics_expose_real_index_scores_and_gold_status():
    async def scenario():
        status, overview = await request("/v1/diagnostics/overview")
        assert status == 200
        assert overview["retrieval"]["selected_strategy"] == "hybrid"
        assert overview["retrieval"]["chroma"]["passages"] == 145
        assert overview["graph"]["node_count"] == 29
        assert overview["gold"]["status"] in {"pending_two_independent_human_reviews", "human_adjudicated"}
        status, comparison = await request("/v1/diagnostics/retrieval", b"q=pagination+duplicate+records")
        assert status == 200 and set(comparison["results"]) == {"lexical", "dense", "hybrid", "hybrid_rerank"}
        assert all("fallback_reason" in result for result in comparison["results"].values())

    asyncio.run(scenario())
