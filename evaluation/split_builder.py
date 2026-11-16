"""Near-duplicate-grouped development split; visible validation is never used."""

import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from cloudserve.config import supplied


def build(threshold: float = 0.90, seed: int = 42) -> dict:
    source = supplied("development_tickets.json")
    rows = json.loads(source.read_text())
    texts = [re.sub(r"\d+", "0", f"{row.get('subject', '')} {row.get('body', '')}").lower() for row in rows]
    matrix = TfidfVectorizer(ngram_range=(1, 2)).fit_transform(texts)
    similarities = cosine_similarity(matrix)
    parents = list(range(len(rows)))

    def find(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            if similarities[i, j] >= threshold:
                root_a, root_b = find(i), find(j)
                if root_a != root_b:
                    parents[root_b] = root_a
    groups = defaultdict(list)
    for i, row in enumerate(rows):
        groups[find(i)].append(row)
    by_intent = defaultdict(list)
    for group in groups.values():
        label = Counter(row["labels"]["intent"] for row in group).most_common(1)[0][0]
        by_intent[label].append(group)
    rng = random.Random(seed)
    train, calibration = [], []
    for intent, group_list in sorted(by_intent.items()):
        rng.shuffle(group_list)
        target = max(1, round(len(group_list) * 0.2)) if len(group_list) > 1 else 0
        for number, group in enumerate(group_list):
            (calibration if number < target else train).extend(group)
    train_ids = sorted(row["ticket_id"] for row in train)
    calibration_ids = sorted(row["ticket_id"] for row in calibration)
    indexes = {row["ticket_id"]: i for i, row in enumerate(rows)}
    cross_max = max(float(similarities[indexes[a], indexes[b]]) for a in train_ids for b in calibration_ids)
    return {"schema_version": "1.0", "source": "data/supplied/development_tickets.json",
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "method": "TF-IDF word unigram/bigram connected components after digit normalization",
            "near_duplicate_cosine_threshold": threshold, "random_seed": seed,
            "group_count": len(groups), "train_ids": train_ids, "calibration_ids": calibration_ids,
            "train_count": len(train_ids), "calibration_count": len(calibration_ids),
            "train_intents": dict(Counter(row["labels"]["intent"] for row in train)),
            "calibration_intents": dict(Counter(row["labels"]["intent"] for row in calibration)),
            "max_cross_split_similarity": cross_max,
            "visible_validation_used": False}


if __name__ == "__main__":
    output = Path(__file__).resolve().parents[1] / "data" / "manifests" / "development_split_v1.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    result = build()
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("group_count", "train_count", "calibration_count", "max_cross_split_similarity")}))
