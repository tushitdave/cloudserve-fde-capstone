"""HTTP lifecycle for governed article publication and source lineage."""

import asyncio
import json

from cloudserve.api.routes import knowledge as knowledge_routes
from cloudserve.config import supplied
from cloudserve.knowledge import resolve
from cloudserve.knowledge_pipeline import KnowledgeService
from cloudserve.main import app


async def request(method: str, path: str, payload=None, query: bytes = b""):
    body = json.dumps(payload).encode() if payload is not None else b""
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method,
             "scheme": "http", "path": path, "raw_path": path.encode(), "query_string": query,
             "root_path": "", "headers": [(b"content-type", b"application/json")],
             "client": ("127.0.0.1", 0), "server": ("test", 80)}
    sent = []
    first = True

    async def receive():
        nonlocal first
        if first:
            first = False
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    await app(scope, receive, send)
    return sent[0]["status"], json.loads(sent[-1]["body"])


def test_knowledge_api_publication_and_versioned_citation(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDSERVE_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(knowledge_routes, "service", KnowledgeService())
    baseline = next(doc for doc in json.loads(supplied("documentation.json").read_text()) if doc["doc_id"] == "DOC-API-002")
    old = resolve("DOC-API-002#p04")
    candidate = {**baseline, "content": baseline["content"] + "\nKnowledge owner checked this procedure update.", "owner": "Knowledge owner"}

    async def scenario():
        status, staged = await request("POST", "/v1/knowledge/jobs", candidate)
        assert status == 200 and staged["status"] == "pending_review"
        job_id = staged["job_id"]
        status, blocked = await request("POST", f"/v1/knowledge/jobs/{job_id}/publish", {"operator": "Publisher"})
        assert status == 409 and "approved" in blocked["detail"]
        status, approved = await request("POST", f"/v1/knowledge/jobs/{job_id}/approve",
                                         {"reviewer": "Knowledge owner", "note": "Verified article source and all resolution steps."})
        assert status == 200 and approved["status"] == "approved"
        status, published = await request("POST", f"/v1/knowledge/jobs/{job_id}/publish", {"operator": "Publisher"})
        assert status == 200 and published["status"] == "published"
        status, active = await request("GET", "/v1/knowledge/indexes/active")
        assert status == 200 and active["snapshot_revision"] == 1 and active["documents"] == 29
        status, lineage = await request("GET", "/v1/knowledge/documents/DOC-API-002/lineage")
        assert status == 200 and lineage["publication"]["authority"] == "human_certified"
        assert len(lineage["passages"]) == 5
        status, versions = await request("GET", "/v1/knowledge/documents/DOC-API-002/versions")
        assert status == 200 and len(versions) == 2
        assert next(version for version in versions if version["active"])["source_hash"] == lineage["source_version"]
        status, old_lineage = await request("GET", "/v1/knowledge/documents/DOC-API-002/lineage",
                                            query=f"source_version={old.source_version}".encode())
        assert status == 200 and old_lineage["source_version"] == old.source_version
        assert old_lineage["publication"]["active"] is False
        assert next(p for p in old_lineage["passages"] if p["passage_id"] == old.passage_id)["text"] == old.text
        # ASGI path is already URL-decoded by the HTTP server.
        status, historical = await request("GET", "/v1/knowledge/passages/DOC-API-002#p04", query=f"source_version={old.source_version}".encode())
        assert status == 200 and historical["text"] == old.text

    asyncio.run(scenario())
