import numpy as np
import pytest

from cloudserve import knowledge
from cloudserve.azure import ModelUnavailable


def test_lexical_candidates_are_real_approved_passages(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDSERVE_RUNTIME_DIR", str(tmp_path))
    hits = knowledge.search_candidates("API pagination duplicate records", strategy="lexical")
    assert hits and all(knowledge.resolve(hit.passage_id, hit.source_version) for hit in hits)
    assert all(hit.start_offset < hit.end_offset and hit.score > 0 for hit in hits)
    with pytest.raises(ModelUnavailable, match="dense index is not ready"):
        knowledge.search_candidates("API pagination", strategy="dense")


def test_dense_and_hybrid_candidates_obey_approved_doc_filter(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDSERVE_RUNTIME_DIR", str(tmp_path))
    passages = knowledge.index()[0]
    selected = next(i for i, passage in enumerate(passages) if passage.doc_id == "DOC-API-002")
    vectors = np.zeros((len(passages), 1536), dtype=np.float32)
    vectors[selected, 0] = 1
    monkeypatch.setattr(knowledge, "_dense_index", lambda: vectors)
    monkeypatch.setattr(knowledge, "embed", lambda _texts: [[1.0] + [0.0] * 1535])
    dense = knowledge.search_candidates("unrelated query", strategy="dense", limit=1)
    assert dense[0].passage_id == passages[selected].passage_id
    hybrid = knowledge.search_candidates("API pagination", strategy="hybrid", allowed_doc_ids={"DOC-API-002"})
    assert hybrid and all(hit.doc_id == "DOC-API-002" for hit in hybrid)
    assert all(knowledge.resolve(hit.passage_id, hit.source_version) for hit in hybrid)
