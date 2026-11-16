"""Freeze supplied ticket labels and prepare a stratified human-review queue.

No model predictions are consulted. Seed labels retain their supplied-data provenance;
passage and claim labels remain pending until independent review.
"""

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

from cloudserve.config import supplied
from cloudserve.knowledge import passages_from_documents

GOLD_VERSION = "gold-seed-v1"
REVIEW_SIZE = 120


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_jsonl(path: Path, rows: list[dict]) -> None:
    content = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    if path.exists() and path.read_text() != content:
        raise FileExistsError(f"Frozen artifact differs: {path}; choose a new version directory")
    path.write_text(content)


def normalized_hash(row: dict) -> str:
    text = re.sub(r"\s+", " ", f"{row.get('subject', '')} {row.get('body', '')}".strip().lower())
    return hashlib.sha256(text.encode()).hexdigest()


def select_review(dev_rows: list[dict], references: dict[str, dict]) -> list[dict]:
    # One example per exact normalized customer question. The greedy score
    # favors rare intents/routes and channel/language diversity.
    unique = {}
    for row in sorted(dev_rows, key=lambda item: item["ticket_id"]):
        unique.setdefault(normalized_hash(row), row)
    remaining = list(unique.values())
    picked = []
    counts = Counter()
    while remaining and len(picked) < REVIEW_SIZE:
        def rank(row):
            labels = row["labels"]
            intent, route = labels["intent"], labels["expected_route"]
            score = (12 / (counts[("intent", intent)] + 1)
                     + 5 / (counts[("intent_route", intent, route)] + 1)
                     + 4 / (counts[("channel", row["channel"])] + 1)
                     + 3 / (counts[("fluency", row["language_fluency"])] + 1)
                     + 2 / (counts[("route", route)] + 1)
                     + (0.4 if row["ticket_id"] in references else 0))
            tie = hashlib.sha256(row["ticket_id"].encode()).hexdigest()
            return score, tie
        chosen = max(remaining, key=rank)
        remaining.remove(chosen)
        picked.append(chosen)
        labels = chosen["labels"]
        for key in (("intent", labels["intent"]), ("intent_route", labels["intent"], labels["expected_route"]),
                    ("channel", chosen["channel"]), ("fluency", chosen["language_fluency"]),
                    ("route", labels["expected_route"])):
            counts[key] += 1
    return sorted(picked, key=lambda row: row["ticket_id"])


def build(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    files = {name: supplied(name) for name in ("development_tickets.json", "validation_tickets.json", "documentation.json", "ground_truth_responses.json")}
    dev = json.loads(files["development_tickets.json"].read_text())
    validation = json.loads(files["validation_tickets.json"].read_text())
    references = {row["ticket_id"]: row for row in json.loads(files["ground_truth_responses.json"].read_text())}
    passages = passages_from_documents(json.loads(files["documentation.json"].read_text()))
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english")
    matrix = vectorizer.fit_transform([f"{p.title} {p.section} {p.text}" for p in passages])
    passage_map = {}
    for passage in passages:
        passage_map.setdefault(passage.doc_id, []).append(passage)
    doc_ids = set(passage_map)
    labels = []
    for split, rows in (("development", dev), ("visible_validation", validation)):
        for row in rows:
            source_labels = row["labels"]
            if not set(source_labels["expected_doc_ids"]).issubset(doc_ids):
                raise ValueError(f"Unknown expected document for {row['ticket_id']}")
            labels.append({"ticket_id": row["ticket_id"], "split": split, "label_provenance": "supplied_capstone_dataset",
                           "channel": row["channel"], "language_fluency": row["language_fluency"],
                           "customer_tier": row["customer_tier"], "customer_region": row["customer_region"],
                           "intent": source_labels["intent"], "urgency": source_labels["urgency"],
                           "expected_route": source_labels["expected_route"], "answerable_from_docs": source_labels["answerable_from_docs"],
                           "expected_doc_ids": source_labels["expected_doc_ids"], "must_not_auto_respond": source_labels["must_not_auto_respond"]})
    selected = select_review(dev, references)
    queue = []
    reviewer_templates = []
    for row in selected:
        ref = references.get(row["ticket_id"], {})
        query = f"{row['subject']} {row['body']}".strip()
        scores = cosine_similarity(vectorizer.transform([query]), matrix)[0]
        candidate_ids = [passages[i].passage_id for i in sorted(range(len(passages)), key=lambda i: scores[i], reverse=True)[:4]]
        for doc_id in row["labels"]["expected_doc_ids"]:
            for passage in passage_map[doc_id]:
                if passage.section == "Resolution":
                    candidate_ids.append(passage.passage_id)
        candidate_ids = sorted(set(candidate_ids))
        candidates = [{"passage_id": passage.passage_id, "source_version": passage.source_version,
                       "section": passage.section, "text": passage.text}
                      for passage in passages if passage.passage_id in candidate_ids]
        queue.append({"ticket_id": row["ticket_id"], "split": "development", "channel": row["channel"],
                      "language_fluency": row["language_fluency"], "subject": row["subject"], "body": row["body"],
                      "seed_labels": row["labels"], "candidate_passages_not_gold": candidates,
                      "reference_seed": {"must_mention": ref.get("must_mention", []), "must_not_claim": ref.get("must_not_claim", [])},
                      "review_status": "pending", "gold_passage_ids": [], "supporting_spans": [],
                      "required_claims": [], "forbidden_claims": [], "reviewer_1": None, "reviewer_2": None,
                      "adjudication_note": None})
        reviewer_templates.append({"ticket_id": row["ticket_id"], "subject": row["subject"], "body": row["body"],
                                   "candidate_passages": candidates, "reviewer_name": None, "reviewed_at": None,
                                   "route": None, "answerable_from_frozen_kb": None,
                                   "passage_labels": {}, "supporting_spans": [], "required_claims": [],
                                   "forbidden_claims": [], "notes": ""})
    write_jsonl(output / "supplied_labels_v1.jsonl", labels)
    write_jsonl(output / "review_queue_v1.jsonl", queue)
    write_jsonl(output / "reviewer_a_template_v1.jsonl", reviewer_templates)
    write_jsonl(output / "reviewer_b_template_v1.jsonl", reviewer_templates)
    manifest = {"gold_version": GOLD_VERSION, "source_sha256": {name: digest(path) for name, path in files.items()},
                "artifact_sha256": {name: digest(output / name) for name in ("supplied_labels_v1.jsonl", "review_queue_v1.jsonl", "reviewer_a_template_v1.jsonl", "reviewer_b_template_v1.jsonl")},
                "corpus": {doc_id: passages[0].source_version for doc_id, passages in sorted(passage_map.items())},
                "passage_count": len(passages), "supplied_label_count": len(labels), "review_queue_count": len(queue),
                "review_queue_ticket_ids_sha256": hashlib.sha256("\n".join(row["ticket_id"] for row in queue).encode()).hexdigest(),
                "review_status": "pending_human_adjudication", "independent_holdout": False,
                "selection": "deterministic stratified development sample; exact normalized question deduplicated",
                "limitations": ["Development tickets trained the classifier.", "Visible validation labels informed policy tuning.",
                                "Candidate passages and reference-response phrases are seeds, not adjudicated claim or passage gold."]}
    manifest_path = output / "manifest_v1.json"
    manifest_content = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    if manifest_path.exists() and manifest_path.read_text() != manifest_content:
        raise FileExistsError(f"Frozen manifest differs: {manifest_path}; choose a new version directory")
    manifest_path.write_text(manifest_content)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("evaluation/gold"))
    args = parser.parse_args()
    print(json.dumps(build(args.output), indent=2))
