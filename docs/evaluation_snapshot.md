# Offline evaluation snapshot

Generated on 16 November 2026 from `evaluation/reports/dev-kb-v1/results.json` (500 development tickets) and `evaluation/reports/validation-kb-v1/results.json` (80 visible validation tickets) with `evaluation/quality_report.py`. These are diagnostic runs of local extractive mode. Development tickets trained the classifier; visible validation labels informed earlier policy tuning. Neither is an untouched final test set. The per-ticket result files stay under ignored `evaluation/reports/`; commands to regenerate the summary are below.

| Measure | Development | Visible validation | Interpretation |
|---|---:|---:|---|
| Processed | 500/500 | 80/80 | All have a terminal decision log. |
| Automatic answers | 46/500 (9.2%) | 3/80 (3.75%) | Conservative coverage; not observed first-contact resolution. |
| Escalations | 454/500 (90.8%) | 77/80 (96.25%) | Higher than the 58% company baseline; route labels and risks require review. |
| Intent macro precision | 1.00 over 22 predicted classes | 1.00 over 22 predicted classes | Development value is in-sample; visible set was used during tuning. This does not establish independent ≥85% performance. |
| Intent confidence ECE | 0.456 over 500 | 0.501 over 80 | Model declares `calibrated=false`; both miss the ≤0.05 target badly. Numeric score must not be presented as calibrated correctness probability. |
| Protected/unsafe false automatic answers | 0/189 | 0/32 | Uses supplied route, answerability and protected labels; independent test still required. |
| Exact citation resolvability | 46/46 | 3/3 | IDs, versions and passage text match the approved corpus. This is not semantic citation accuracy. |
| p95 local processing latency | 4 ms over 500 | 5 ms over 80 | Excludes Azure network and customer delivery; cannot prove production <3 seconds. |
| Human-reviewed hallucination rate | unavailable, 0 reviewed responses | unavailable, 0 reviewed responses | No claim-support verdict can be made until the two-reviewer queue is adjudicated. |
| Human-reviewed semantic citation accuracy | unavailable, 0 reviewed claims | unavailable, 0 reviewed claims | Exact citation resolution is a different metric. |
| Availability | unavailable, 0 live observation hours | unavailable, 0 live observation hours | 99.5% target needs a production-like observation period. |

Language-fluency diagnostic: development auto coverage is 12/120 (10.0%) for non-fluent and 34/380 (8.95%) for fluent tickets, a 1.05-point gap. Visible validation auto coverage is 0/19 (0%) versus 3/61 (4.92%), a 4.92-point gap; the answered sample is only three tickets. Intent accuracy is 120/120 and 380/380 in development and 19/19 and 61/61 in visible validation, but these labels are synthetic and the model is uncalibrated. Do not infer equal customer experience from these counts.

```bash
PYTHONPATH=src:. .venv/bin/python -m evaluation.quality_report --input data/supplied/development_tickets.json --results evaluation/reports/dev-kb-v1/results.json --output evaluation/reports/quality-dev.json
PYTHONPATH=src:. .venv/bin/python -m evaluation.quality_report --input data/supplied/validation_tickets.json --results evaluation/reports/validation-kb-v1/results.json --output evaluation/reports/quality-validation.json
```

The next quality gate is two independent passage/claim reviews, adjudication, a leakage-safe calibration split and a frozen untouched holdout. The current 120-item review queue is a seed, not completed gold.
