"""ML registry, drift monitors and retraining criteria (Research/02 "Rules and ML lifecycle").

The registry records, for each classifier head: dataset snapshot, feature definition,
train/calibration split, artifact hash, hyperparameters, calibration artifact,
held-out validation report and promotion status. A replacement must beat the
promoted baseline on per-class quality and safety without a larger subgroup gap or a
latency increase; promotion also needs a named human approval.

Drift monitors cover intent mix, text length, out-of-vocabulary terms, novelty and
confidence. Retraining is triggered by measured drift, never by a schedule, and a
retrained model goes through the same promotion check.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from collections import Counter
from pathlib import Path

import numpy as np

from cloudserve.classifier import (MODEL_VERSION, SPLIT_PATH, calibration_report, models, nearest_training_similarity,
                                   split_rows, ticket_text)
from cloudserve.config import APP_ROOT, supplied

REGISTRY_PATH = APP_ROOT / "data" / "manifests" / "model_registry.json"

DRIFT_THRESHOLDS = {
    "intent_psi": 0.25,               # population stability index of predicted intents vs training labels
    "length_ratio_change": 0.5,       # |median words / reference median − 1|
    "oov_rate_ratio": 2.0,            # batch OOV rate / reference OOV rate
    "novel_share": 0.10,              # share of tickets below the novelty threshold
    "mean_confidence_drop": 0.10,     # reference mean intent confidence − batch mean
}
RETRAINING_CRITERIA = [
    "Any drift monitor above its threshold on a production window of at least 200 tickets.",
    "Held-out intent ECE above 0.05 or per-class precision below 0.85 on newly labelled tickets.",
    "A new intent or approved article is introduced.",
    "Retraining uses a new frozen split; the candidate must pass promotion_check against the promoted model and be approved by the policy owner.",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_hash(head) -> str:
    lr = head.model.named_steps["logisticregression"]
    vec = head.model.named_steps["tfidfvectorizer"]
    digest = hashlib.sha256()
    # Rounded so the fingerprint is stable across BLAS/OS float noise (~1e-12) yet changes with any real retrain.
    digest.update(np.ascontiguousarray(np.round(lr.coef_, 4) + 0.0).tobytes())
    digest.update(np.ascontiguousarray(np.round(lr.intercept_, 4) + 0.0).tobytes())
    digest.update(json.dumps(sorted((k, int(v)) for k, v in vec.vocabulary_.items())).encode())
    digest.update(f"{head.temperature:.3f}".encode())
    return digest.hexdigest()


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def reference_profile() -> dict:
    train, calibration = split_rows()
    vocab = set(models()["intent"].model.named_steps["tfidfvectorizer"].vocabulary_)
    intents = Counter(r["labels"]["intent"] for r in train)
    cal_tokens = [t for r in calibration for t in _tokens(ticket_text(r))]
    heads = models()
    cal_conf = [float(heads["intent"].proba([ticket_text(r)])[0].max()) for r in calibration]
    return {"intent_distribution": {k: v / len(train) for k, v in sorted(intents.items())},
            "median_words": statistics.median(len(ticket_text(r).split()) for r in train),
            "oov_rate": sum(t not in vocab for t in cal_tokens) / max(1, len(cal_tokens)),
            "mean_intent_confidence": statistics.mean(cal_conf),
            "novel_share": sum(nearest_training_similarity(ticket_text(r)) < 0.35 for r in calibration) / len(calibration)}


def build_registry() -> dict:
    train, calibration = split_rows()
    cal = calibration_report()
    entries = []
    for field, head in models().items():
        lr = head.model.named_steps["logisticregression"]
        entries.append({
            "model_id": f"{field}-{MODEL_VERSION}",
            "head": field,
            "version": MODEL_VERSION,
            "dataset": {"source": "data/supplied/development_tickets.json", "sha256": _sha256(supplied("development_tickets.json")),
                        "split_manifest": "data/manifests/development_split_v1.json", "split_sha256": _sha256(SPLIT_PATH),
                        "train_rows": len(train), "calibration_rows": len(calibration), "visible_validation_used": False},
            "features": {"input": "subject + body text only (no customer identity, tier, region or history)",
                         "vectorizer": "TF-IDF word 1-2 grams, sublinear tf, max 25000 features",
                         "vocabulary_size": len(head.model.named_steps["tfidfvectorizer"].vocabulary_)},
            "hyperparameters": {"estimator": "LogisticRegression", "class_weight": "balanced", "max_iter": lr.max_iter, "C": lr.C},
            "artifact_sha256": _artifact_hash(head),
            "calibration": {"method": "temperature scaling (NLL on calibration split)", "temperature": round(head.temperature, 4)},
            "validation_report": {k: cal["heads"][field][k] for k in ("accuracy", "ece", "brier_top_label")},
            "promotion": {"status": "promoted", "promoted_on": "2026-11-16",
                          "approved_by": "Student acting as policy owner (capstone)",
                          "replaces": "tfidf-logreg-v1 (trained on all 500 tickets, uncalibrated; ECE 0.456)",
                          "evidence": "PRD revision R1; data/manifests/calibration_report_v1.json"},
        })
    registry = {"schema_version": "1.0", "models": entries, "drift_thresholds": DRIFT_THRESHOLDS,
                "retraining_criteria": RETRAINING_CRITERIA, "reference_profile": reference_profile()}
    return registry


def write_registry(path: Path = REGISTRY_PATH) -> dict:
    registry = build_registry()
    path.write_text(json.dumps(registry, indent=2) + "\n")
    return registry


def promotion_check(candidate: dict, baseline: dict, max_latency_increase_ms: float = 50.0) -> dict:
    """Candidate/baseline: {'per_class_precision': {...}, 'protected_false_auto': int, 'fluency_gap_points': float, 'p95_ms': float}."""
    reasons = []
    for name, base in baseline["per_class_precision"].items():
        if candidate["per_class_precision"].get(name, 0.0) + 1e-9 < base:
            reasons.append(f"precision dropped for {name}")
    if candidate["protected_false_auto"] > baseline["protected_false_auto"]:
        reasons.append("more protected false-auto")
    if candidate["fluency_gap_points"] > baseline["fluency_gap_points"]:
        reasons.append("larger subgroup gap")
    if candidate["p95_ms"] - baseline["p95_ms"] > max_latency_increase_ms:
        reasons.append("latency increase above budget")
    return {"promote": not reasons, "reasons": reasons, "requires_human_approval": True}


def _psi(expected: dict, actual: dict) -> float:
    keys = set(expected) | set(actual)
    total = 0.0
    for key in keys:
        e, a = max(expected.get(key, 0.0), 1e-4), max(actual.get(key, 0.0), 1e-4)
        total += (a - e) * math.log(a / e)
    return total


def drift_report(texts: list[str], predicted_intents: list[str], confidences: list[float], similarities: list[float],
                 novelty_threshold: float, reference: dict | None = None) -> dict:
    """Compare a batch with the training reference; flags drive the retraining criteria, not automatic retraining."""
    reference = reference or json.loads(REGISTRY_PATH.read_text())["reference_profile"]
    if not texts:
        return {"tickets": 0, "alerts": [], "retrain_recommended": False}
    vocab = set(models()["intent"].model.named_steps["tfidfvectorizer"].vocabulary_)
    tokens = [t for text in texts for t in _tokens(text)]
    counts = Counter(predicted_intents)
    metrics = {
        "intent_psi": round(_psi(reference["intent_distribution"], {k: v / len(texts) for k, v in counts.items()}), 4),
        "length_ratio_change": round(abs(statistics.median(len(t.split()) for t in texts) / reference["median_words"] - 1), 4),
        "oov_rate_ratio": round((sum(t not in vocab for t in tokens) / max(1, len(tokens))) / max(reference["oov_rate"], 1e-4), 4),
        "novel_share": round(sum(s < novelty_threshold for s in similarities) / len(texts), 4),
        "mean_confidence_drop": round(reference["mean_intent_confidence"] - statistics.mean(confidences), 4),
    }
    alerts = [name for name, value in metrics.items() if value > DRIFT_THRESHOLDS[name]]
    return {"tickets": len(texts), "metrics": metrics, "thresholds": DRIFT_THRESHOLDS, "alerts": alerts,
            "retrain_recommended": bool(alerts) and len(texts) >= 200,
            "note": "A recommendation only: retraining needs a new frozen split, promotion_check and human approval."}


if __name__ == "__main__":
    reg = write_registry()
    print(json.dumps([{k: m[k] for k in ("model_id", "artifact_sha256")} for m in reg["models"]], indent=2))
