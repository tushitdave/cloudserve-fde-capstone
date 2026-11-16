import hashlib
import json
from pathlib import Path

from cloudserve.config import supplied
from cloudserve.knowledge import canonicalize_documents, index, passages_from_documents
from scripts.build_source_manifest import build


def test_source_inventory_and_section_offsets_cover_approved_corpus():
    docs = json.loads(supplied("documentation.json").read_text())
    inventory = build()
    committed = json.loads((Path(__file__).resolve().parents[1] / "data/manifests/source_manifest_v1.json").read_text())
    assert inventory == committed
    assert inventory["document_count"] == 29 and inventory["passage_count"] == 145
    assert len({item["doc_id"] for item in inventory["documents"]}) == 29
    assert "ground_truth_responses" not in inventory["source"]
    assert {passage.doc_id for passage in index()[0]} == {doc["doc_id"] for doc in docs}
    for doc in docs:
        item = next(row for row in inventory["documents"] if row["doc_id"] == doc["doc_id"])
        assert item["content_sha256"] == hashlib.sha256(doc["content"].encode()).hexdigest()
        assert item["authority"] == "approved_supplied_article"
        passages = passages_from_documents([doc])
        assert len(passages) == item["passage_count"]
        for passage in passages:
            assert doc["content"][passage.start_offset:passage.end_offset] == passage.text
            assert passage.source_version == item["source_version"]
        # Canonical source text is retained verbatim alongside passage spans.
        assert doc["content"].startswith("# ")
    canonical = canonicalize_documents(docs)
    assert len(canonical) == 29
    assert sum(len(doc.sections) for doc in canonical) == 145
    assert sum(len(doc.steps) for doc in canonical) == 116
    for doc in canonical:
        original = next(item for item in docs if item["doc_id"] == doc.doc_id)
        assert doc.content == original["content"]
        for span in [*doc.sections, *doc.steps]:
            assert doc.content[span.start_offset:span.end_offset] == span.text
        assert all(step.parent_section == "Resolution" for step in doc.steps)
        resolution = next(p for p in passages_from_documents([original]) if p.section == "Resolution")
        assert all(step.text in resolution.text for step in doc.steps)
        assert resolution.permissions == doc.permissions == ["customer_support"]


def test_chunk_inherits_explicit_source_permissions():
    doc = json.loads(supplied("documentation.json").read_text())[0]
    restricted = {**doc, "permissions": ["support_agent"]}
    assert all(p.permissions == ["support_agent"] for p in passages_from_documents([restricted]))
