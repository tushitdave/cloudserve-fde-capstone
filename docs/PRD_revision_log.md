# PRD revision log

Stage 5 record of substantive requirement changes after contact with the build and the data. Each entry names what changed, the evidence that prompted it and how it was tested. PRD v1 is preserved in [PRD_v1.md](PRD_v1.md); the requirements below supersede it where they conflict.

## Revision R1 — 17 November 2026: routing driven by measured evidence, not by an answerability score

**What prompted it.** The first full runs answered only 46 of 500 development tickets (9.2%) and 3 of 80 visible validation tickets. Escalation was 90.8%, worse than CloudServe's 58% baseline, so the system would have added work rather than removed it, which was Marcus's second failure condition. Diagnosis showed 197 of the 265 wrongly escalated development tickets were stopped by a text classifier predicting `answerable_from_docs`.

**What the data showed (new findings F07–F09 in the [problem statement](problem_statement.md)).**

- On the held-out calibration split, the answerability classifier has ROC AUC 0.32; on visible validation it has AUC 0.55. It is no better than chance.
- The reason is in the labels. In 40 of 191 groups of identical non-protected ticket text (dev + validation), the same words carry both `auto_respond` and `escalate`, or both answerable and not answerable. No text model can learn a distinction the text does not contain.
- 62 of the 80 visible validation ticket bodies appear verbatim in the development set, so earlier validation figures overstated generalisation.
- Three policy-v1 text patterns (`expired_resource_state`, `regional_assurance`, `recurring_access_failure`) had been written to stop specific visible-validation false autos. That is tuning against the check set.

**What changed.**

| Requirement | v1 | Revised |
|---|---|---|
| FR03 classification | Confidence numeric, uncalibrated; trained on all 500 development tickets. | Trained on the frozen near-duplicate-grouped train split (397). Temperature-calibrated on the held-out calibration split (103). Intent ECE is 0.002 on calibration; urgency ECE is 0.055. `calibrated=true` is now declared only because it is measured. |
| FR04 protective rules | Hard-coded regexes in code, including validation-fitted patterns. | Versioned rule table `src/cloudserve/policy_v2.json` with rule ID, priority, owner, effective date, interview evidence and requirement IDs. Validation-fitted patterns are removed. Billing dispute, account compromise and data-location assurance rules are added, sourced from Daniel's interview. |
| FR06 abstention | Answerability score below 0.68 escalated. | The answerability gate is removed. Escalation happens for a protective rule, a novel request, low calibrated intent confidence, no approved article for the intent, or insufficient passage evidence. |
| New FR13 novelty | — | A ticket whose nearest train-split neighbour similarity is below 0.35 escalates as `novel_request` (Ines: novel incidents are where wrong answers do most damage). Added after calibrated confidence proved overconfident on out-of-scope text, for example "My cat ate my keyboard" was classified as authentication failure at 0.99. |
| New NFR08 kill switch | No mechanism. | `POST /v1/policy/kill-switch`, the Overview page or `CLOUDSERVE_AUTO_SEND_DISABLED=1` stops automatic answers from the next ticket with no deploy. A ticket in flight is re-checked before release and held. |
| Thresholds | 0.24 intent, 0.11 evidence, 0.68 answerability, set by hand. | Selected by `evaluation/threshold_selection.py` on the calibration split only, over a 1,680-configuration grid. Objective: maximum coverage. Constraints: zero protected false-auto, zero automatic answers on the 12-ticket out-of-scope fixture, and wrong-article rate ≤ 5% of sent. Chosen thresholds: intent 0.90, similarity 0.35, document 0.30, evidence 0.06. Recorded in `data/manifests/threshold_selection_v1.json`. |
| FR07 answer and validation | First 540 characters of the Resolution passage; verification trivially passed in extractive mode. | Full numbered resolution steps plus the article's common causes and notes, each line cited. The answer discloses that it is automated (Ravi). The verifier checks every cited line is an exact span of its cited passage. Deterministic guardrails (instruction integrity, grounding, tone/scope, private data, claim support) record pass/fail on every ticket. |
| A7 trigger | Guardrail could only be shown by monkey-patching the drafter. | A ticket containing an instruction-override attempt is blocked and escalated by the `instruction_integrity` input guardrail. |

**Result** (extractive mode, 17 November 2026; full tables in [evaluation_snapshot.md](evaluation_snapshot.md)):

| | v1 dev | v2 dev | v1 validation | v2 validation |
|---|---:|---:|---:|---:|
| Automatic answers | 46 (9.2%) | 364 (72.8%) | 3 (3.8%) | 55 (68.8%) |
| Escalation rate | 90.8% | 27.2% | 96.3% | 31.3% |
| Route agreement with labels | 47.0% | 74.6% | 43.8% | 71.3% |
| Safe-auto recall | 14.8% | 86.5% | 6.3% | 81.3% |
| Protected false-auto | 0 | 0 | 0 | 0 |
| Wrong-article answers | — | 7 (1.9% of sent) | — | 1 (1.8% of sent) |

**What it cost, stated plainly.** 90 development answers and 15 validation answers went to tickets labelled `escalate` that were not protected. Given the label disagreement above these are reported, not hidden. They need human review before anyone can say whether they were harmful. The visible validation set was run twice under v2: once to measure, and once after UI-only changes, with identical counts. The 0.06 evidence threshold is the retrieval floor, so the evidence gate adds little on top of the intent and document models. On genuinely new phrasing the novelty gate is the main protection.

**What it taught.** A label in the supplied data is not automatically a learnable target. The requirement should have been written as "escalate what we cannot ground" from the start, rather than "predict answerability".

## Open revisions

- Non-fluent customers have 81% safe-auto recall against 88% for fluent customers on development (a 7-point gap). That breaches the under-5-point fairness condition. The candidate mitigation is dense embedding retrieval (P4-01/P4-05), which needs network access to Azure.
- Urgency prediction is 50% accurate on held-out data. The labels show the same text with different urgencies, so urgency is reported for prioritisation only and is never used to release an answer.
