"""Compare chunking strategies (Research/02 "Adaptive chunking"; ADR-004).

Strategies, all over the same 29 approved articles:
  section       — one chunk per `##` section (current production chunker)
  fixed_80_20   — sliding windows of 80 words with 20-word overlap (short-overlap baseline)
  parent_child  — child chunks are single lines (steps, bullets); search runs on children,
                  evidence is the full parent section

Each strategy is searched with the production hybrid scorer (0.5 TF-IDF + 0.5 all-MiniLM-L6-v2
cosine via an in-memory Chroma collection) on the held-out calibration split. Metrics:
document Hit@1, Resolution Hit@1 (the top evidence unit lies in an expected article's
Resolution section), procedure integrity (the evidence unit contains every numbered step of
that Resolution), chunk count and mean chunk length.

    PYTHONPATH=src:. python -m evaluation.chunking_comparison
"""

import argparse
import json
import re
import statistics
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from cloudserve.classifier import split_rows
from cloudserve.config import supplied
from cloudserve.knowledge import _sections

OUTPUT = Path(__file__).resolve().parents[1] / "data" / "manifests" / "chunking_comparison_v1.json"


def _resolution_span(content: str):
    for label, _text, start, end in _sections(content):
        if label == "Resolution":
            return start, end
    return None


def chunk(docs: list[dict], strategy: str) -> list[dict]:
    """Each unit: {doc_id, search_text, evidence_start, evidence_end} (evidence span in the original article)."""
    units = []
    for doc in docs:
        content = doc["content"]
        sections = list(_sections(content))
        if strategy == "section":
            units += [{"doc_id": doc["doc_id"], "search_text": f"{doc['title']} {label} {text}", "evidence": (start, end)}
                      for label, text, start, end in sections]
        elif strategy == "fixed_80_20":
            words = [(m.start(), m.end()) for m in re.finditer(r"\S+", content)]
            for i in range(0, max(1, len(words) - 20), 60):
                window = words[i:i + 80]
                start, end = window[0][0], window[-1][1]
                units.append({"doc_id": doc["doc_id"], "search_text": f"{doc['title']} {content[start:end]}", "evidence": (start, end)})
        elif strategy == "parent_child":
            for label, text, start, end in sections:
                offset = start
                for line in text.splitlines():
                    if line.strip():
                        units.append({"doc_id": doc["doc_id"], "search_text": f"{doc['title']} {label} {line.strip()}",
                                      "evidence": (start, end)})  # child searched, parent section returned
                    offset += len(line) + 1
        else:
            raise ValueError(strategy)
    return units


def evaluate(strategy: str, docs: list[dict], rows: list[dict], resolution_only: bool = False) -> dict:
    units = chunk(docs, strategy)
    texts = [u["search_text"] for u in units]
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english")
    matrix = vectorizer.fit_transform(texts)
    collection = chromadb.EphemeralClient().get_or_create_collection(f"chunks-{strategy}", embedding_function=DefaultEmbeddingFunction(),
                                                              metadata={"hnsw:space": "cosine"})
    if collection.count() != len(units):
        collection.add(ids=[str(i) for i in range(len(units))], documents=texts)
    by_doc = {d["doc_id"]: d for d in docs}
    spans = {d["doc_id"]: _resolution_span(d["content"]) for d in docs}

    def allowed(i: int) -> bool:
        # Production rule: only units overlapping an article's Resolution section can be primary evidence.
        span, (start, end) = spans[units[i]["doc_id"]], units[i]["evidence"]
        return not resolution_only or bool(span and start < span[1] and end > span[0])
    hit = res_hit = intact = 0
    for row in rows:
        query = f"{row.get('subject') or ''} {row.get('body') or ''}".strip()
        lexical = cosine_similarity(vectorizer.transform([query]), matrix)[0]
        dense = collection.query(query_texts=[query], n_results=min(20, len(units)))
        dense_scores = {int(i): 1 - d for i, d in zip(dense["ids"][0], dense["distances"][0])}
        dense = collection.query(query_texts=[query], n_results=len(units)) if resolution_only else dense
        dense_scores = {int(i): 1 - d for i, d in zip(dense["ids"][0], dense["distances"][0])}
        pool = [i for i in range(len(units)) if allowed(i)]
        candidates = set(sorted(pool, key=lambda i: lexical[i], reverse=True)[:20]) | {i for i in dense_scores if allowed(i)}
        best = max(candidates, key=lambda i: 0.5 * lexical[i] + 0.5 * dense_scores.get(i, 0.0))
        unit, expected = units[best], set(row["labels"]["expected_doc_ids"])
        hit += unit["doc_id"] in expected
        if unit["doc_id"] in expected:
            span = _resolution_span(by_doc[unit["doc_id"]]["content"])
            start, end = unit["evidence"]
            if span and start < span[1] and end > span[0]:
                res_hit += 1
                intact += start <= span[0] and end >= span[1]
    n = len(rows)
    lengths = [len(u["search_text"].split()) for u in units]
    return {"chunks": len(units), "mean_chunk_words": round(statistics.mean(lengths), 1),
            "doc_hit_at_1": round(hit / n, 4), "resolution_hit_at_1": round(res_hit / n, 4),
            "procedure_intact_given_resolution_hit": round(intact / res_hit, 4) if res_hit else None,
            "procedure_intact_overall": round(intact / n, 4)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    docs = json.loads(supplied("documentation.json").read_text())
    _, calibration = split_rows()
    rows = [r for r in calibration if r["labels"]["answerable_from_docs"] and r["labels"]["expected_doc_ids"]
            and not r["labels"]["must_not_auto_respond"]]
    report = {"schema_version": "1.0", "selection_set": "development calibration split (answerable)", "tickets": len(rows),
              "scorer": "hybrid 0.5 TF-IDF + 0.5 all-MiniLM-L6-v2", "strategies": {}}
    for strategy in ("section", "fixed_80_20", "parent_child"):
        report["strategies"][strategy] = {"any_unit": evaluate(strategy, docs, rows),
                                          "resolution_units_only (production rule)": evaluate(strategy, docs, rows, True)}
        print(strategy, json.dumps(report["strategies"][strategy]))
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
