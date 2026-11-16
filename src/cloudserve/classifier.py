"""Conventional supervised ML; labels are used only for training/evaluation."""

import json
from collections import defaultdict
from functools import lru_cache

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

from cloudserve.config import supplied
from cloudserve.contracts import Classification, Ticket


def ticket_text(row: dict | Ticket) -> str:
    subject = row.get("subject", "") if isinstance(row, dict) else row.subject
    body = row.get("body", "") if isinstance(row, dict) else row.body
    return f"{subject} {body}".strip()


@lru_cache(maxsize=1)
def models():
    rows = json.loads(supplied("development_tickets.json").read_text())
    x = [ticket_text(row) for row in rows]
    out = {}
    for field in ("intent", "urgency", "answerable_from_docs"):
        model = make_pipeline(
            TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, max_features=25000),
            LogisticRegression(max_iter=1000, class_weight="balanced"),
        )
        model.fit(x, [row["labels"][field] for row in rows])
        out[field] = model
    return out


@lru_cache(maxsize=1)
def approved_docs_by_intent() -> dict[str, set[str]]:
    rows = json.loads(supplied("development_tickets.json").read_text())
    mapping: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        if row["labels"]["answerable_from_docs"] and not row["labels"]["must_not_auto_respond"]:
            mapping[row["labels"]["intent"]].update(row["labels"]["expected_doc_ids"])
    return dict(mapping)


@lru_cache(maxsize=1)
def document_model():
    rows = json.loads(supplied("development_tickets.json").read_text())
    labelled = [row for row in rows if row["labels"]["expected_doc_ids"] and not row["labels"]["must_not_auto_respond"]]
    model = make_pipeline(
        TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, max_features=25000),
        LogisticRegression(max_iter=1000, class_weight="balanced"),
    )
    model.fit([ticket_text(row) for row in labelled], [row["labels"]["expected_doc_ids"][0] for row in labelled])
    return model


def predict_document(ticket: Ticket) -> tuple[str, float]:
    model = document_model()
    probabilities = model.predict_proba([ticket_text(ticket)])[0]
    i = probabilities.argmax()
    return str(model.classes_[i]), float(probabilities[i])


def classify(ticket: Ticket) -> Classification:
    text = ticket_text(ticket)
    if not text:
        return Classification(intent="unknown", urgency="medium", intent_confidence=0, urgency_confidence=0, answerability_confidence=0)
    trained = models()
    choices = {}
    for field, model in trained.items():
        probabilities = model.predict_proba([text])[0]
        classes = model.classes_
        ranked = sorted(zip(classes, probabilities), key=lambda pair: pair[1], reverse=True)
        choices[field] = ranked
    intent, intent_p = choices["intent"][0]
    urgency, urgency_p = choices["urgency"][0]
    answerability = next(float(prob) for label, prob in choices["answerable_from_docs"] if bool(label))
    return Classification(
        intent=str(intent), urgency=str(urgency),
        intent_confidence=float(intent_p), urgency_confidence=float(urgency_p),
        answerability_confidence=answerability,
        alternatives=[{"intent": str(label), "confidence": round(float(prob), 4)} for label, prob in choices["intent"][1:4]],
    )
