"""Conventional supervised ML with a leakage-safe split and post-hoc calibration.

Models are fitted only on the frozen near-duplicate-grouped *train* split
(`data/manifests/development_split_v1.json`). A single temperature per head is
then fitted on the held-out *calibration* split so that the reported confidence
tracks observed accuracy. The 80 visible validation tickets are never used here.
Labels are used only for training/evaluation; they are never inference inputs.
"""

import json
from collections import defaultdict
from functools import lru_cache

import numpy as np
from scipy.optimize import minimize_scalar
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

from cloudserve.config import APP_ROOT, supplied
from cloudserve.domain.models.contracts import Classification, Ticket

MODEL_VERSION = "tfidf-logreg-v2+temperature"
SPLIT_PATH = APP_ROOT / "data" / "manifests" / "development_split_v1.json"


def ticket_text(row: dict | Ticket) -> str:
    subject = row.get("subject", "") if isinstance(row, dict) else row.subject
    body = row.get("body", "") if isinstance(row, dict) else row.body
    return f"{subject or ''} {body or ''}".strip()


@lru_cache(maxsize=1)
def split_rows() -> tuple[list[dict], list[dict]]:
    """Return (train, calibration) development rows from the frozen split manifest."""
    rows = {row["ticket_id"]: row for row in json.loads(supplied("development_tickets.json").read_text())}
    split = json.loads(SPLIT_PATH.read_text())
    return [rows[i] for i in split["train_ids"]], [rows[i] for i in split["calibration_ids"]]


def _pipeline():
    return make_pipeline(
        TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, max_features=25000),
        LogisticRegression(max_iter=2000, class_weight="balanced"),
    )


def _softmax(logits: np.ndarray, temperature: float) -> np.ndarray:
    scaled = logits / temperature
    scaled -= scaled.max(axis=1, keepdims=True)
    exp = np.exp(scaled)
    return exp / exp.sum(axis=1, keepdims=True)


def _fit_temperature(model, texts: list[str], labels: list[str]) -> float:
    """Minimise negative log-likelihood on held-out calibration rows (Guo et al., 2017)."""
    logits = model.decision_function(texts)
    if logits.ndim == 1:
        logits = np.column_stack([-logits, logits])
    index = {label: i for i, label in enumerate(model.classes_)}
    target = np.array([index[label] for label in labels])

    def nll(temperature: float) -> float:
        probs = _softmax(logits, temperature)
        return float(-np.mean(np.log(np.clip(probs[np.arange(len(target)), target], 1e-12, 1))))

    return float(minimize_scalar(nll, bounds=(0.05, 20.0), method="bounded").x)


class CalibratedHead:
    def __init__(self, field: str, train: list[dict], calibration: list[dict]):
        self.field = field
        self.model = _pipeline().fit([ticket_text(r) for r in train], [r["labels"][field] for r in train])
        known = [r for r in calibration if r["labels"][field] in set(self.model.classes_)]
        self.temperature = _fit_temperature(self.model, [ticket_text(r) for r in known], [r["labels"][field] for r in known])

    @property
    def classes(self):
        return self.model.classes_

    def proba(self, texts: list[str]) -> np.ndarray:
        logits = self.model.decision_function(texts)
        if logits.ndim == 1:
            logits = np.column_stack([-logits, logits])
        return _softmax(logits, self.temperature)

    def ranked(self, text: str) -> list[tuple[str, float]]:
        probs = self.proba([text])[0]
        return sorted(((str(c), float(p)) for c, p in zip(self.classes, probs)), key=lambda pair: pair[1], reverse=True)


@lru_cache(maxsize=1)
def models() -> dict[str, CalibratedHead]:
    train, calibration = split_rows()
    return {field: CalibratedHead(field, train, calibration) for field in ("intent", "urgency")}


@lru_cache(maxsize=1)
def novelty_index():
    """TF-IDF index of train-split tickets; low nearest-neighbour similarity marks a novel request."""
    train, _ = split_rows()
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
    matrix = vectorizer.fit_transform([ticket_text(r) for r in train])
    return vectorizer, matrix


def nearest_training_similarity(text: str) -> float:
    vectorizer, matrix = novelty_index()
    return float((matrix @ vectorizer.transform([text]).T).toarray().max()) if text else 0.0


@lru_cache(maxsize=1)
def approved_docs_by_intent() -> dict[str, set[str]]:
    """Intent → approved article map learnt from train-split labels only."""
    train, _ = split_rows()
    mapping: dict[str, set[str]] = defaultdict(set)
    for row in train:
        if row["labels"]["answerable_from_docs"] and not row["labels"]["must_not_auto_respond"]:
            mapping[row["labels"]["intent"]].update(row["labels"]["expected_doc_ids"])
    return dict(mapping)


@lru_cache(maxsize=1)
def document_model():
    train, _ = split_rows()
    labelled = [row for row in train if row["labels"]["expected_doc_ids"] and not row["labels"]["must_not_auto_respond"]]
    return _pipeline().fit([ticket_text(row) for row in labelled], [row["labels"]["expected_doc_ids"][0] for row in labelled])


def predict_document(ticket: Ticket) -> tuple[str, float]:
    model = document_model()
    probabilities = model.predict_proba([ticket_text(ticket)])[0]
    i = probabilities.argmax()
    return str(model.classes_[i]), float(probabilities[i])


def classify(ticket: Ticket) -> Classification:
    """Always returns a result; an empty or unusable text yields the `unknown` fallback."""
    text = ticket_text(ticket)
    if not text:
        return Classification(intent="unknown", urgency="medium", intent_confidence=0, urgency_confidence=0,
                              model_version=MODEL_VERSION, calibrated=True)
    heads = models()
    intents = heads["intent"].ranked(text)
    urgencies = heads["urgency"].ranked(text)
    return Classification(
        intent=intents[0][0], urgency=urgencies[0][0],
        intent_confidence=round(intents[0][1], 6), urgency_confidence=round(urgencies[0][1], 6),
        alternatives=[{"intent": label, "confidence": round(prob, 4)} for label, prob in intents[1:4]],
        urgency_alternatives=[{"urgency": label, "confidence": round(prob, 4)} for label, prob in urgencies[1:3]],
        nearest_training_similarity=round(nearest_training_similarity(text), 6),
        model_version=MODEL_VERSION, calibrated=True,
    )


def calibration_report(bins: int = 10) -> dict:
    """ECE/Brier/accuracy of each calibrated head on the held-out calibration split."""
    _, calibration = split_rows()
    texts = [ticket_text(r) for r in calibration]
    report = {"model_version": MODEL_VERSION, "calibration_rows": len(calibration), "heads": {}}
    for field, head in models().items():
        probs = head.proba(texts)
        predicted = [str(head.classes[i]) for i in probs.argmax(axis=1)]
        confidence = probs.max(axis=1)
        correct = np.array([p == r["labels"][field] for p, r in zip(predicted, calibration)], dtype=float)
        ece = 0.0
        table = []
        for b in range(bins):
            low, high = b / bins, (b + 1) / bins
            mask = (confidence >= low) & ((confidence < high) if b < bins - 1 else (confidence <= high))
            if mask.any():
                gap = float(confidence[mask].mean() - correct[mask].mean())
                ece += mask.mean() * abs(gap)
                table.append({"band": [low, high], "count": int(mask.sum()), "stated": round(float(confidence[mask].mean()), 4),
                              "observed": round(float(correct[mask].mean()), 4)})
        report["heads"][field] = {"temperature": round(head.temperature, 4), "accuracy": round(float(correct.mean()), 4),
                                  "ece": round(float(ece), 4), "brier_top_label": round(float(np.mean((confidence - correct) ** 2)), 4),
                                  "bands": table}
    return report


if __name__ == "__main__":
    print(json.dumps(calibration_report(), indent=2))
