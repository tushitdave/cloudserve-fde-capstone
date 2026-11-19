"""Small governed knowledge graph and bounded graph-assisted retrieval.

The supplied corpus already contains curated ``related_docs`` relationships.  This
module turns those reviewed relationships into an inspectable graph.  Ticket-time
traversal is deliberately constrained to document IDs already authorised by the
intent policy; graph traversal can widen a document-model seed inside that scope,
but can never bypass policy or passage permissions.
"""

from __future__ import annotations

from collections import deque

from cloudserve.adapters.persistence.knowledge_store import KnowledgeStore, _content_hash


def snapshot() -> dict:
    docs = KnowledgeStore().active_documents()
    by_id = {doc["doc_id"]: doc for doc in docs}
    nodes = [
        {
            "id": doc_id,
            "title": doc["title"],
            "category": doc.get("category", "uncategorised"),
            "source_version": _content_hash(doc),
        }
        for doc_id, doc in sorted(by_id.items())
    ]
    seen: set[tuple[str, str]] = set()
    edges = []
    for source, doc in sorted(by_id.items()):
        for target in sorted(set(doc.get("related_docs") or [])):
            if target not in by_id or target == source:
                continue
            key = tuple(sorted((source, target)))
            if key in seen:
                continue
            seen.add(key)
            edges.append({"source": key[0], "target": key[1], "relation": "related_support_topic"})
    return {
        "schema_version": "1.0",
        "graph_type": "curated_document_relationship_graph",
        "execution_mode": "bounded_policy_scoped_graph_rag",
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "limitations": "Document-level curated relationships; not an auto-generated entity ontology.",
    }


def traverse(seed_doc_ids: set[str], authorised_doc_ids: set[str], max_hops: int = 1) -> dict:
    """Breadth-first traversal, never leaving the policy-authorised document set."""
    graph = snapshot()
    adjacency: dict[str, set[str]] = {node["id"]: set() for node in graph["nodes"]}
    for edge in graph["edges"]:
        adjacency[edge["source"]].add(edge["target"])
        adjacency[edge["target"]].add(edge["source"])
    seeds = sorted(seed_doc_ids & authorised_doc_ids)
    visited = set(seeds)
    queue = deque((seed, 0) for seed in seeds)
    traversed = []
    while queue:
        source, depth = queue.popleft()
        if depth >= max_hops:
            continue
        for target in sorted(adjacency.get(source, set()) & authorised_doc_ids):
            traversed.append({"source": source, "target": target, "hop": depth + 1})
            if target not in visited:
                visited.add(target)
                queue.append((target, depth + 1))
    return {
        "seed_doc_ids": seeds,
        "authorised_doc_ids": sorted(authorised_doc_ids),
        "expanded_doc_ids": sorted(visited),
        "edges": traversed,
        "max_hops": max_hops,
        "scope_enforced": True,
    }
