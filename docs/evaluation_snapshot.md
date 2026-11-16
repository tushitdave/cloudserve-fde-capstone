# Offline evaluation snapshot — policy v3

Generated on 16 November 2026 in extractive mode (no generative model). Sources:

- `evaluation/reports/development-policy-v3/` (500 development tickets)
- `evaluation/reports/validation-policy-v3/` (80 visible validation tickets)
- `evaluation/reports/development-lexical-fallback/` (the same 500 with dense retrieval forced off)
- `data/manifests/retrieval_comparison_v1.json`
- `data/manifests/threshold_selection_v1.json`
- `data/manifests/calibration_report_v1.json`

The v1 → v2 change is recorded in [PRD revision R1](PRD_revision_log.md) and v2 → v3 in revision R2.

**How the data was used.** The classifier was fitted on the 397-ticket train split. Calibration, the retrieval-strategy choice and every threshold were fitted on the 103-ticket calibration split. Development figures are therefore partly in-sample. Visible validation was not used to choose any v2 or v3 setting, but 62 of its 80 bodies also occur in development, so it overstates performance on new wording. Neither set is the hidden assessment set.

## Retrieval comparison (calibration split, answerable tickets, document level)

| Strategy | Hit@1 | Recall@3 | MRR@5 | Non-fluent Hit@1 | p95 latency |
|---|---:|---:|---:|---:|---:|
| Lexical TF-IDF | 0.918 | 0.973 | 0.948 | 0.667 | 5 ms |
| Dense (Chroma + all-MiniLM-L6-v2) | 0.931 | 0.959 | 0.951 | 0.800 | 98 ms |
| **Hybrid (0.5 lexical + 0.5 dense)** | **0.959** | **0.973** | **0.964** | **0.800** | 112 ms |
| Hybrid + cross-encoder rerank (ms-marco-MiniLM-L-6-v2) | 0.945 | 0.973 | 0.957 | 0.800 | 230 ms |

These scores are unscoped, over all 29 articles. Within the intent scope used at run time, dense, hybrid and rerank all reach Hit@1 0.959 and Recall@3 1.000. On visible validation (for information only), lexical Hit@1 is 0.837 and hybrid 0.939. The reranker did not beat hybrid and doubled latency, so per ADR-004 it is implemented and measured but not selected. In the threshold selection, hybrid gave the highest coverage at the same safety constraints (table below), with tie-breaks on recall and then cost.

| Strategy (best eligible configuration, calibration split) | Coverage | Safe-auto recall | Wrong article | Fluency gap |
|---|---:|---:|---:|---:|
| Lexical | 79.6% | 90.1% | 2.4% | 23.3 pts |
| Dense | 83.5% | 91.6% | 4.7% | 25.1 pts |
| **Hybrid (chosen)** | **84.5%** | **95.8%** | 2.3% | **3.6 pts** |
| Hybrid + rerank | 84.5% | 95.8% | 2.3% | 21.4 pts |

## Business outcomes (offline proxies)

| Measure | CloudServe baseline | Target | v1 dev | v2 dev | **v3 dev** | **v3 validation** |
|---|---:|---:|---:|---:|---:|---:|
| First-contact resolution proxy | 42% | ≥60% | 9.2% | 72.8% | **80.4%** | **76.3%** |
| Escalation rate | 58% | ≤30% | 90.8% | 27.2% | **19.6%** | **23.8%** |
| Time to first reply, automatic answers (median, local) | 8–12 h | <5 min | 4 ms | 5 ms | 106 ms | 108 ms |

An automatic answer is not a confirmed resolution, and escalated tickets still wait for a person.

## Technical performance

| Measure | Target | v3 dev | v3 validation | Notes |
|---|---:|---:|---:|---|
| Intent macro precision | ≥85% | 1.00 | 1.00 | Templated data; expect lower on new wording |
| Urgency accuracy | — | 0.65 | 0.43 | 0.50 held-out; used for priority only |
| Intent calibration ECE | ≤0.05 | 0.0003 | 0.002 | Temperature at lower bound; see limits |
| Route agreement with labels | — | 78.2% | 76.2% | v2: 74.6% / 71.3% |
| Safe-auto recall | — | **96.8%** | **93.8%** | v2: 86.5% / 81.3% |
| Answers citing an expected article | — | 99.5% (2 wrong of 402) | 100% (0 of 61) | v2: 98.1% / 98.2% |
| Hallucination rate / semantic citation accuracy | ≤5% / ≥95% | unknown | unknown | Needs two-person review |
| p95 latency, local | <3 s | 206 ms | 204 ms | Includes dense query embedding; excludes network |

## Governance conditions

| Condition | Result |
|---|---|
| Protected tickets answered | **0/87 dev, 0/14 validation** |
| Out-of-scope fixture answered | 0/12 |
| Private data in outbound text | 0 detections (402 + 61 answers scanned) |
| Decision-log coverage | 100%; input = terminal = decision IDs |
| Confidence calibration (intent) | Within 5 points |
| Quality across groups (<5 points) | **Language fluency met on dev (2.4 pts)**; tier 4.6 pts met; region 10.3 pts **not met** (Latin America 89.7%, n=39) |
| Lexical fallback (dense forced off) | 359/500 sent, protected 0, wrong article 0.6%: degrades safely |
| Drift monitors | Development: no alerts. Validation: intent PSI 0.41 alert on 80 tickets, below the 200-ticket minimum for a retraining recommendation |

**Label disagreement.** 100 development and 16 validation answers went to non-protected tickets labelled `escalate`. The supplied labels give opposite routes to identical text in 40 of 191 duplicate-text groups of non-protected tickets. These are reported for human review, not as safety failures.

## Fairness (safe-auto recall by segment, development, v3)

| Segment | Tickets | Auto rate | Safe-auto recall |
|---|---:|---:|---:|
| Fluent English | 380 | 80.5% | 97.4% |
| Non-fluent English | 120 | 80.0% | 95.0% |
| Enterprise | 83 | 85.5% | 100.0% |
| Business | 164 | 78.7% | 97.2% |
| Standard | 253 | 79.8% | 95.5% |
| Short (≤28 words) | 273 | 75.8% | 94.7% |
| Long (>28 words) | 227 | 85.9% | 99.3% |
| Asia-Pacific | 119 | 78.2% | 100.0% |
| Europe | 151 | 82.1% | 98.1% |
| North America | 170 | 79.4% | 96.2% |
| Latin America | 60 | 83.3% | 89.7% |

Dense retrieval closed most of the fluency gap: 7.1 points under lexical v2, 2.4 points now. Only 3 of 80 labelled-auto non-fluent tickets escalate, two of them by the data-location rule. The remaining regional gap has no regional model input. With 39 labelled tickets it is likely sampling noise, but it is reported.

## The figures above should be treated with caution because

The tickets are synthetic and templated. Development figures are partly in-sample. Validation shares most of its text with development. The route labels contradict themselves on identical text. Retrieval was compared at document level, not on human-adjudicated passages. No human has yet reviewed answer relevance. Business outcomes are proxies.

## Reproduce

```bash
PYTHONPATH=src:. python -m cloudserve.classifier > data/manifests/calibration_report_v1.json
PYTHONPATH=src:. python -m evaluation.retrieval_comparison
PYTHONPATH=src:. python -m evaluation.threshold_selection          # ≈5 minutes
PYTHONPATH=src:. python -m cloudserve.ml_registry
./scripts/batch.sh data/supplied/development_tickets.json evaluation/reports/development-policy-v3
./scripts/batch.sh data/supplied/validation_tickets.json evaluation/reports/validation-policy-v3
CLOUDSERVE_RETRIEVAL_STRATEGY=lexical ./scripts/batch.sh data/supplied/development_tickets.json evaluation/reports/development-lexical-fallback
```
