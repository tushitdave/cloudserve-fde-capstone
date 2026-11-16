import json

import pytest

from evaluation.quality_report import evaluate


def test_quality_report_keeps_semantic_targets_unknown(tmp_path):
    source = [{"ticket_id": "Q-1", "channel": "chat", "language_fluency": "non_fluent",
               "labels": {"intent": "security_incident", "must_not_auto_respond": True, "expected_route": "escalate"}}]
    result = [{"ticket_id": "Q-1", "terminal_state": "escalated", "latency_ms": 8, "citations": [],
               "classification": {"intent": "security_incident", "intent_confidence": 0.6, "calibrated": False}}]
    input_path, result_path = tmp_path / "input.json", tmp_path / "results.json"
    input_path.write_text(json.dumps(source))
    result_path.write_text(json.dumps(result))
    report = evaluate(input_path, result_path)
    assert report["protected_false_auto"] == {"count": 0, "protected_or_unsafe_tickets": 1}
    assert report["intent_calibration"]["ece"] == pytest.approx(0.4)
    assert report["hallucination_rate"]["value"] is None
    assert report["citation_semantic_accuracy"]["value"] is None
    assert report["availability"]["value"] is None
    assert report["language_fluency_groups"]["non_fluent"]["count"] == 1
    result[0]["ticket_id"] = "wrong-id"
    result_path.write_text(json.dumps(result))
    with pytest.raises(ValueError, match="do not reconcile"):
        evaluate(input_path, result_path)
