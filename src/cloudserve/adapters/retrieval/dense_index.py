"""Dense retrieval (Chroma + all-MiniLM-L6-v2), hybrid fusion and cross-encoder reranking.

Research/02 "Retrieval, ML and agent decisions": compare dense retrieval with
all-MiniLM-L6-v2, lexical search and a hybrid candidate union; test a cross-encoder
reranker; filter access before candidate presentation. Chroma is a search index,
not the source of truth: passages, versions and permissions come from the governed
knowledge store, and the collection name is derived from their content hash, so a
changed approved snapshot always builds a new collection.

Every strategy returns real passage IDs and scores. If an optional dependency or
model download is unavailable, callers fall back to lexical retrieval and record
the reason (A11: degrade, never crash).
"""

from __future__ import annotations

import hashlib
import math
import os
from functools import lru_cache
from pathlib import Path

from cloudserve.config import APP_ROOT, setting
from cloudserve.domain.models.contracts import Passage

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")  # keep Chroma telemetry off

DENSE_MODEL = "all-MiniLM-L6-v2 (Chroma ONNX)"
RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"
STRATEGIES = ("lexical", "dense", "hybrid", "hybrid_rerank")


class RetrievalUnavailable(RuntimeError):
    pass


def index_dir() -> Path:
    path = Path(setting("CLOUDSERVE_INDEX_DIR", str(APP_ROOT / "data" / "runtime" / "index")))
    path.mkdir(parents=True, exist_ok=True)
    return path


def snapshot_key(passages: list[Passage]) -> str:
    digest = hashlib.sha256("|".join(f"{p.passage_id}:{p.source_version}" for p in passages).encode()).hexdigest()
    return digest[:16]


def _passage_text(p: Passage) -> str:
    return f"{p.title}\n{p.section}\n{p.text}"


@lru_cache(maxsize=4)
def _collection(key: str):
    try:
        import chromadb
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
    except ImportError as error:  # optional dependency missing
        raise RetrievalUnavailable(f"chromadb not installed: {error}") from error
    from cloudserve.adapters.retrieval.knowledge_index import index

    passages = index()[0]
    if snapshot_key(passages) != key:
        raise RetrievalUnavailable("approved snapshot changed while building the dense index")
    client = chromadb.PersistentClient(path=str(index_dir() / "chroma"))
    collection = client.get_or_create_collection(name=f"passages-{key}", embedding_function=DefaultEmbeddingFunction(),
                                                 metadata={"hnsw:space": "cosine", "embedding_model": DENSE_MODEL})
    if collection.count() != len(passages):
        metadatas = []
        for p in passages:
            meta = {"doc_id": p.doc_id, "section": p.section, "source_version": p.source_version}
            meta.update({f"perm_{role}": True for role in p.permissions})
            metadatas.append(meta)
        collection.upsert(ids=[p.passage_id for p in passages], documents=[_passage_text(p) for p in passages], metadatas=metadatas)
    return collection


def dense_collection():
    from cloudserve.adapters.retrieval.knowledge_index import index

    try:
        return _collection(snapshot_key(index()[0]))
    except RetrievalUnavailable:
        raise
    except Exception as error:  # model download, ONNX runtime or storage failure
        raise RetrievalUnavailable(f"dense index unavailable: {type(error).__name__}") from error


def dense_scores(query: str, allowed_doc_ids: set[str] | None, role: str = "customer_support", k: int = 20) -> dict[str, float]:
    """Cosine similarity per passage ID, permission-filtered inside Chroma before results leave the index."""
    collection = dense_collection()
    where: dict = {f"perm_{role}": True}
    if allowed_doc_ids is not None:
        where = {"$and": [where, {"doc_id": {"$in": sorted(allowed_doc_ids)}}]}
    try:
        result = collection.query(query_texts=[query], n_results=min(k, collection.count()), where=where)
    except Exception as error:
        raise RetrievalUnavailable(f"dense query failed: {type(error).__name__}") from error
    return {pid: max(0.0, 1.0 - float(dist)) for pid, dist in zip(result["ids"][0], result["distances"][0])}


@lru_cache(maxsize=1)
def _cross_encoder():
    try:
        from fastembed.rerank.cross_encoder import TextCrossEncoder
    except ImportError as error:
        raise RetrievalUnavailable(f"fastembed not installed: {error}") from error
    try:
        return TextCrossEncoder(RERANK_MODEL, cache_dir=str(index_dir() / "models"))
    except Exception as error:
        raise RetrievalUnavailable(f"reranker unavailable: {type(error).__name__}") from error


def rerank_scores(query: str, passages: list[Passage]) -> list[float]:
    """Cross-encoder relevance mapped to (0, 1) with a logistic; a ranking score, not a probability."""
    if not passages:
        return []
    try:
        logits = list(_cross_encoder().rerank(query, [_passage_text(p) for p in passages]))
    except RetrievalUnavailable:
        raise
    except Exception as error:
        raise RetrievalUnavailable(f"rerank failed: {type(error).__name__}") from error
    return [1.0 / (1.0 + math.exp(-float(x))) for x in logits]


def warm_up() -> dict:
    """Build the dense index and load both models once (used by scripts and the harness)."""
    status = {"dense": "ready", "reranker": "ready"}
    try:
        dense_collection()
    except RetrievalUnavailable as error:
        status["dense"] = str(error)
    try:
        _cross_encoder()
    except RetrievalUnavailable as error:
        status["reranker"] = str(error)
    return status

