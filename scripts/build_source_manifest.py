"""Freeze the supplied approved article inventory without indexing reference answers."""

import hashlib
import json
from pathlib import Path

from cloudserve.config import supplied
from cloudserve.knowledge import passages_from_documents
from cloudserve.knowledge_store import _content_hash


def build() -> dict:
    docs = json.loads(supplied("documentation.json").read_text())
    passages = passages_from_documents(docs)
    items = []
    for doc in sorted(docs, key=lambda item: item["doc_id"]):
        items.append({"doc_id": doc["doc_id"], "title": doc["title"], "owner": "supplied_capstone_pack",
                      "authority": "approved_supplied_article", "source_version": _content_hash(doc),
                      "content_sha256": hashlib.sha256(doc["content"].encode()).hexdigest(),
                      "category": doc.get("category", ""), "related_docs": doc.get("related_docs", []),
                      "permissions": doc.get("permissions", ["customer_support"]),
                      "passage_count": sum(p.doc_id == doc["doc_id"] for p in passages)})
    return {"schema_version": "1.0", "source": "data/supplied/documentation.json",
            "document_count": len(items), "passage_count": len(passages), "documents": items,
            "excluded_authority": "data/supplied/ground_truth_responses.json"}


if __name__ == "__main__":
    output = Path(__file__).resolve().parents[1] / "data" / "manifests" / "source_manifest_v1.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(build(), indent=2) + "\n")
    print(f"Wrote {output}")
