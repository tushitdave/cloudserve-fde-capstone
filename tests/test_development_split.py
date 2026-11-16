import json
from pathlib import Path

from cloudserve.config import supplied
from evaluation.split_builder import build


def test_near_duplicate_split_is_frozen_disjoint_and_stratified():
    frozen = json.loads((Path(__file__).resolve().parents[1] / "data/manifests/development_split_v1.json").read_text())
    assert build() == frozen
    development = {row["ticket_id"] for row in json.loads(supplied("development_tickets.json").read_text())}
    visible = {row["ticket_id"] for row in json.loads(supplied("validation_tickets.json").read_text())}
    train, calibration = set(frozen["train_ids"]), set(frozen["calibration_ids"])
    assert train.isdisjoint(calibration)
    assert train | calibration == development
    assert (train | calibration).isdisjoint(visible)
    assert frozen["max_cross_split_similarity"] < frozen["near_duplicate_cosine_threshold"]
    assert set(frozen["train_intents"]) == set(frozen["calibration_intents"])
