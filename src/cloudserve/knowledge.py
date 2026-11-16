"""Approved supplied-article ingestion and passage-level lexical retrieval."""

import json
import re
from functools import lru_cache
from pathlib import Path

import numpy as np

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from cloudserve.azure import ModelUnavailable, embed
from cloudserve.config import runtime_dir
from cloudserve.contracts import CanonicalDocument, Passage, SourceSpan
from cloudserve.knowledge_store import KnowledgeStore, _content_hash


def _sections(content: str):
    current = "Overview"
    start = 0
    position = 0
    for line in content.splitlines(keepends=True):
        if line.startswith("## "):
            raw = content[start:position]
            if raw.strip():
                left = len(raw) - len(raw.lstrip())
                yield current, raw.strip(), start + left, start + len(raw.rstrip())
            current = line[3:].strip()
            start = position + len(line)
        position += len(line)
    raw = content[start:position]
    if raw.strip():
        left = len(raw) - len(raw.lstrip())
        yield current, raw.strip(), start + left, start + len(raw.rstrip())


def passages_from_documents(docs: list[dict]) -> list[Passage]:
    passages = []
    for doc in docs:
        version = _content_hash(doc)
        for number, (section, text, start, end) in enumerate(_sections(doc["content"]), 1):
            if text:
                passages.append(Passage(
                    doc_id=doc["doc_id"], passage_id=f"{doc['doc_id']}#p{number:02d}",
                    title=doc["title"], section=section, text=text, score=0.0,
                    source_version=version,
                    start_offset=start, end_offset=end,
                    permissions=doc.get("permissions", ["customer_support"]),
                ))
    return passages


def canonicalize_documents(docs: list[dict]) -> list[CanonicalDocument]:
    """Retain original article text with exact section and numbered-step spans."""
    canonical = []
    for doc in docs:
        content = doc["content"]
        sections = [SourceSpan(label=label, start_offset=start, end_offset=end, text=text)
                    for label, text, start, end in _sections(content)]
        steps = []
        for match in re.finditer(r"(?m)^([0-9]+)\. [^\n]+", content):
            start, end = match.span()
            parent = next((section.label for section in sections if section.start_offset <= start < section.end_offset), None)
            steps.append(SourceSpan(label=f"Step {match.group(1)}", parent_section=parent,
                                    start_offset=start, end_offset=end, text=match.group()))
        canonical.append(CanonicalDocument(doc_id=doc["doc_id"], title=doc["title"], content=content,
                                           owner=doc.get("owner", "supplied_capstone_pack"),
                                           source_version=_content_hash(doc), related_docs=doc.get("related_docs", []),
                                           sections=sections, steps=steps,
                                           permissions=doc.get("permissions", ["customer_support"])))
    return canonical


@lru_cache(maxsize=8)
def _index_for(db_path: str, revision: int):
    docs = KnowledgeStore(Path(db_path)).active_documents()
    passages = passages_from_documents(docs)
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english")
    matrix = vectorizer.fit_transform([f"{p.title} {p.section} {p.text}" for p in passages])
    return passages, vectorizer, matrix


def index():
    store = KnowledgeStore()
    return _index_for(str(store.path), store.revision())


def retrieve(query: str, limit: int = 3, allowed_doc_ids: set[str] | None = None) -> list[Passage]:
    passages, vectorizer, matrix = index()
    if not query.strip():
        return []
    scores = cosine_similarity(vectorizer.transform([query]), matrix)[0]
    eligible = [i for i, p in enumerate(passages) if allowed_doc_ids is None or p.doc_id in allowed_doc_ids]
    top = sorted(eligible, key=lambda i: scores[i], reverse=True)[:max(limit, 8)]
    dense = _dense_index()
    if dense is not None and top:
        try:
            query_vector = np.asarray(embed([query])[0], dtype=np.float32)
            query_vector /= max(float(np.linalg.norm(query_vector)), 1e-9)
            dense_scores = dense @ query_vector
            # Restrict dense reranking to lexical candidates and preserve lexical
            # relevance as the release score used by policy.
            top = sorted(top, key=lambda i: 0.7 * scores[i] + 0.3 * max(float(dense_scores[i]), 0), reverse=True)
        except ModelUnavailable:
            pass
    top = top[:limit]
    return [passages[i].model_copy(update={"score": round(float(scores[i]), 4)}) for i in top if scores[i] >= 0.06]


def document_passages(doc_id: str) -> list[Passage]:
    """All active approved passages of one document, in source order."""
    return [p for p in index()[0] if p.doc_id == doc_id]


def search_candidates(query: str, strategy: str = "lexical", limit: int = 5,
                      allowed_doc_ids: set[str] | None = None) -> list[Passage]:
    """Compare lexical, dense and hybrid candidates over one active approved snapshot.

    Candidate scores are ranking similarities, not calibrated answer probabilities.
    The release path remains `retrieve`, with its independent lexical evidence gate.
    """
    if strategy not in {"lexical", "dense", "hybrid"}:
        raise ValueError("strategy must be lexical, dense or hybrid")
    if not query.strip() or limit <= 0:
        return []
    passages, vectorizer, matrix = index()
    lexical = cosine_similarity(vectorizer.transform([query]), matrix)[0]
    dense_scores = None
    if strategy != "lexical":
        dense = _dense_index()
        if dense is None:
            raise ModelUnavailable("approved dense index is not ready for this source revision")
        vector = np.asarray(embed([query])[0], dtype=np.float32)
        if vector.shape != (1536,):
            raise ModelUnavailable("query embedding has wrong dimensions")
        vector /= max(float(np.linalg.norm(vector)), 1e-9)
        dense_scores = np.maximum(dense @ vector, 0)
    eligible = [i for i, passage in enumerate(passages) if allowed_doc_ids is None or passage.doc_id in allowed_doc_ids]
    if strategy == "lexical":
        scores = lexical
    elif strategy == "dense":
        scores = dense_scores
    else:
        scores = 0.5 * lexical + 0.5 * dense_scores
    top = sorted(eligible, key=lambda i: (-float(scores[i]), passages[i].passage_id))[:limit]
    return [passages[i].model_copy(update={"score": round(float(scores[i]), 4)}) for i in top if scores[i] > 0]


@lru_cache(maxsize=8)
def _dense_index_for(path_string: str, revision: int):
    path = Path(path_string)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
        passages = index()[0]
        if payload["passage_ids"] != [p.passage_id for p in passages] or payload["source_versions"] != [p.source_version for p in passages]:
            return None
        matrix = np.asarray(payload["vectors"], dtype=np.float32)
        if matrix.shape != (len(passages), 1536):
            return None
        matrix /= np.maximum(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-9)
        return matrix
    except (ValueError, KeyError, TypeError):
        return None


def _dense_index():
    return _dense_index_for(str(runtime_dir() / "dense_index.json"), KnowledgeStore().revision())


def build_dense_index() -> dict:
    """Opt-in publication of an immutable index for the supplied approved passages."""
    passages = index()[0]
    vectors = []
    for start in range(0, len(passages), 16):
        vectors.extend(embed([f"{p.title}\n{p.section}\n{p.text}" for p in passages[start:start + 16]]))
    payload = {"passage_ids": [p.passage_id for p in passages],
               "source_versions": [p.source_version for p in passages], "vectors": vectors}
    target = runtime_dir() / "dense_index.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload))
    temporary.replace(target)
    _dense_index_for.cache_clear()
    return manifest()


def resolve(passage_id: str, source_version: str | None = None) -> Passage | None:
    current = next((p for p in index()[0] if p.passage_id == passage_id), None)
    if current and (source_version is None or current.source_version == source_version):
        return current
    if source_version is None or "#p" not in passage_id:
        return None
    doc_id = passage_id.split("#p", 1)[0]
    historical = KnowledgeStore().source_version(doc_id, source_version)
    if historical:
        return next((p for p in passages_from_documents([historical]) if p.passage_id == passage_id and p.source_version == source_version), None)
    return None


def manifest() -> dict:
    passages, _, _ = index()
    docs = {p.doc_id for p in passages}
    return {"documents": len(docs), "passages": len(passages), "index_version": "hybrid-v1" if _dense_index() is not None else "lexical-v1", "snapshot_revision": KnowledgeStore().revision(), "approved": True, "dense_ready": _dense_index() is not None}
