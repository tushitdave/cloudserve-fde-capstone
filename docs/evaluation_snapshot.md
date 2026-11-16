# Offline evaluation snapshot — policy v2

Generated on 16 November 2026 in extractive mode (no model provider) from:

- `evaluation/reports/development-policy-v2/` (500 development tickets)
- `evaluation/reports/validation-policy-v2/` (80 visible validation tickets)
- `evaluation/quality_report.py`
- the held-out calibration record `data/manifests/calibration_report_v1.json` and `threshold_selection_v1.json`

Policy v1 figures are kept for comparison. The reason for the change is recorded in [PRD revision R1](PRD_revision_log.md).

**How the data was used.** The classifier was fitted on the 397-ticket train split. Calibration and thresholds were fitted on the 103-ticket calibration split. Development figures are therefore partly in-sample. The visible validation set was not used to choose any v2 threshold or rule. However, 62 of its 80 ticket bodies also occur in development, so it overstates performance on genuinely new wording. Neither set is the hidden assessment set.

## Business outcomes (offline proxies)

| Measure | CloudServe baseline | Target | v1 dev | v2 dev | v2 validation |
|---|---:|---:|---:|---:|---:|
| First-contact resolution proxy (answered automatically / all) | 42% | ≥60% | 9.2% | **72.8%** | **68.8%** |
| Escalation rate | 58% | ≤30% | 90.8% | **27.2%** | **31.3%** |
| Time to first reply, automatic answers (median, local) | 8–12 h | <5 min | 4 ms | 5 ms | 5 ms |

An automatic answer is not a confirmed resolution. No customer confirmed any of these. Repeat contacts and CSAT cannot be observed offline. Escalated tickets still wait for a person, so the time-to-reply figure covers only the automated share.

## Technical performance

| Measure | Target | v2 dev | v2 validation | Notes |
|---|---:|---:|---:|---|
| Intent macro precision | ≥85% | 1.00 | 1.00 | Held-out calibration split accuracy is also 1.00. The synthetic tickets are templated, so expect lower on new wording. |
| Urgency accuracy | — | 0.65 | 0.43 | 0.50 on the held-out split; labels conflict on identical text. Used for priority only. |
| Intent calibration ECE | ≤0.05 | 0.0003 | 0.002 | 0.002 on calibration. The temperature hit its lower bound because the calibration split contains no errors, so the high band is verified only on in-distribution text. |
| Route agreement with supplied labels | — | 74.6% | 71.3% | v1: 47.0% / 43.8%. |
| Safe-auto recall (labelled auto, answered with the expected article) | — | 86.5% | 81.3% | v1: 14.8% / 6.3%. |
| Answer cites an expected article | — | 98.1% of sent | 98.2% of sent | 7 and 1 wrong-article answers. |
| Exact citation resolvability | — | 100% | 100% (165/165) | ID, version and text match. This is not semantic citation accuracy. |
| Hallucination rate | ≤5% | unknown | unknown | Needs two-person review of ≥50 answers; none done yet. |
| Semantic citation accuracy | ≥95% | unknown | unknown | Every extractive line is verified as an exact span of its cited passage, but relevance to the ticket needs human review. |
| p95 latency, local | <3 s | 8 ms | 10 ms | Excludes network and Azure. |

## Governance conditions

| Condition | Result | Notes |
|---|---|---|
| Protected tickets answered automatically | **0/87 dev, 0/14 validation** | Rules R-01–R-07 fire before any drafting. |
| Out-of-scope fixture answered automatically | 0/12 | Hard constraint in threshold selection; regression test. |
| Private data in outbound text | 0 detections | `private_data` check ran on all 364 + 55 answers. |
| Decision-log coverage | 100% | Every ticket has `decision` and `terminal` events with the Governance Framework fields; IDs reconcile. |
| Guardrail runs | 5 checks on every answer; instruction integrity on every eligible ticket | A ticket with an instruction-override attempt is blocked (`tests/test_policy_v2.py`). |
| Kill switch | Implemented and tested | API, UI and environment variable; takes effect on the next ticket. |
| Confidence calibration | Intent within 5 points | Urgency ECE 0.055 on calibration, just outside. |
| Quality across groups (<5 points) | **Not met** | See below. |

**Label disagreement, reported rather than hidden.** 90 development and 15 validation answers went to tickets labelled `escalate` that are not protected. In 40 of 191 duplicate-text groups of non-protected tickets, the supplied labels give opposite routes to identical words, so no text-based system can match them. These answers still need human review before any claim that they were safe.

## Fairness (safe-auto recall by segment, development)

| Segment | Tickets | Auto rate | Safe-auto recall |
|---|---:|---:|---:|
| Fluent English | 380 | 74.2% | 88.3% |
| Non-fluent English | 120 | 68.3% | 81.3% |
| Enterprise | 83 | 79.5% | 90.2% |
| Business | 164 | 69.5% | 85.9% |
| Standard | 253 | 72.7% | 85.7% |

The largest development gaps are language fluency (7.1 points) and region (12.7 points; Latin America 79.5% versus Asia-Pacific 92.2%, n=60). Validation groups are too small for a stable comparison: 8 enterprise and 7 Latin America tickets. The fluency gap is the one the Governance Framework predicts. Lexical retrieval misses non-fluent phrasing more often (10 of 80 labelled-auto non-fluent development tickets escalate on insufficient evidence, against 19 of 231 fluent). The planned mitigation is dense retrieval; it is not yet measured.

## The figures above should be treated with caution because

The tickets are synthetic and heavily templated. The development figures are partly in-sample. Validation shares most of its text with development. The route labels themselves disagree on identical text. No human has yet reviewed answer quality or claim support. Business outcomes are offline proxies with no customer confirmation.

## Reproduce

```bash
PYTHONPATH=src:. python -m cloudserve.classifier > data/manifests/calibration_report_v1.json
PYTHONPATH=src:. python -m evaluation.threshold_selection
./scripts/batch.sh data/supplied/development_tickets.json evaluation/reports/development-policy-v2
./scripts/batch.sh data/supplied/validation_tickets.json evaluation/reports/validation-policy-v2
PYTHONPATH=src:. python -m evaluation.quality_report --input data/supplied/validation_tickets.json --results evaluation/reports/validation-policy-v2/results.json --output evaluation/reports/quality-validation-v2.json
```
