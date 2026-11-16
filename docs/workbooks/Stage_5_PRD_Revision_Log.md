# Stage Five: PRD revision log — CloudServe

The full narrative with evidence is in `docs/PRD_revision_log.md` (revision R1).

## 1. Section one: revision summary

| Field | Value |
|---|---|
| New version number | 2.0 |
| Date of revision | 16 November 2026 |
| Who carried out the revision | Tushit Dave |
| Who reviewed and agreed it | Student as product owner; evidence reviewed against the held-out calibration split and test suite |
| Number of requirements changed | 4 (FR-03, FR-04, FR-06, FR-07) |
| Number of requirements added | 4 (FR-13 novelty, NFR-08 kill switch; v3: NFR-09 security, NFR-10 ML lifecycle) |
| Number of requirements removed | 1 (implicit "predict answerability" gate) |

## 2. Section two: the changes

| Requirement ID | What it said in version one | What it says now | What prompted the change | Agreed by |
|---|---|---|---|---|
| FR-03 | Predict intent/urgency with a numeric confidence | Train on the near-duplicate-grouped train split only; temperature-calibrate on the held-out calibration split; declare `calibrated` only when measured (intent ECE 0.002) | v1 trained on all 500 tickets, so its precision was in-sample; ECE was 0.456 | Product owner |
| FR-04 | Protected intents never auto-answered; regex signals in code | Versioned rule table `policy_v2.json` (R-00–R-07) with owner, effective date, interview evidence and requirement IDs. Three validation-fitted regexes removed. Billing-dispute, account-compromise and data-location rules added. | Discovery 1.3 (Daniel); audit found patterns written against specific visible-validation tickets | Product owner |
| FR-06 | Escalate when evidence is weak (in practice: answerability score <0.68) | Escalate on protective rule, novelty, intent confidence <0.90, no approved article, or evidence <0.06. No answerability gate. | 90.8% escalation; the gate had held-out AUC 0.32–0.55; labels conflict on identical text in 40/191 groups | Product owner |
| FR-07 | Draft from evidence; verify citations | Full procedure + causes + notes, each line cited and verified as an exact span; five guardrails recorded on every answer; instruction-override tickets blocked | v1 quoted 540 characters (cut steps); verification was trivially true; A7 could only be shown by patching code | Product owner |
| FR-13 (new) | — | Escalate requests whose nearest training-ticket similarity is <0.35 | Calibrated confidence was 0.99 on "My cat ate my keyboard" | Product owner |
| NFR-08 (new) | — | Kill switch: UI, API or environment variable; effective on the next ticket; in-flight tickets held | Governance Framework section 5; none existed | Product owner |
| FR-05 (v3) | Lexical retrieval only | Hybrid lexical + Chroma all-MiniLM-L6-v2, chosen over dense-only and cross-encoder reranking on the calibration split; lexical fallback logged | Architecture review; 7.1-point fluency gap under lexical | Product owner |
| NFR-09/10 (v3, new) | — | Security layer (keys, roles, tenants, quotas, encryption, retention); ML registry with drift monitors and retraining criteria; rule conflict detection; LangGraph orchestration | Gaps against `Research/02_architecture_and_agents.md` | Product owner |
| Thresholds | Hand-set 0.24 / 0.11 / 0.68 | Selected by `evaluation/threshold_selection.py` on the calibration split: maximum coverage subject to 0 protected false-auto, 0 out-of-scope auto and ≤5% wrong article | Brief: "a threshold chosen because it looked reasonable" is the failure mode | Product owner |

**Effect.** v2: development auto-answers rose from 9.2% to 72.8%, escalation fell from 90.8% to 27.2%, and safe-auto recall went from 14.8% to 86.5%. v3: 80.4% auto (validation 76.3%), escalation 19.6%, safe-auto recall 96.8%, and a fluency gap of 2.4 points. Protected false-auto stayed at 0 throughout.

## 3. Section three: assumptions that turned out to be wrong

| Assumption from version one | Did it hold? | What you found instead | What you changed because of it |
|---|---|---|---|
| The supplied route/answerability labels are a learnable target | No | Identical text carries opposite labels in 40 of 191 duplicate groups of non-protected tickets | Route on what can be grounded; report label disagreement separately |
| A text model can predict answerability | No | Held-out AUC 0.32 (calibration) and 0.55 (validation) | Removed the gate |
| The visible validation set measures generalisation | Partly | 62/80 bodies duplicate development text | Treated validation as optimistic; added out-of-scope fixtures and a novelty gate |
| Calibrated confidence protects against unknown inputs | No | Temperature fitted on in-distribution data is overconfident on out-of-scope text | Added novelty gate |
| Non-fluent customers are historically worst served (Sofia) | No | Historical CSAT 3.04 vs 2.95 | The risk moved to the new system: measured a 7-point retrieval gap |

## 4. Section four: what you decided not to change

| What looked wrong | Why you left it | What it would have cost to change | Revisit when? |
|---|---|---|---|
| Urgency is 50% accurate | Labels conflict; urgency never releases an answer | New labels or features | When live priority data exists |
| 90 dev answers to label-`escalate` tickets | No text signal separates them; hiding them would cut coverage on identical text | Escalating every look-alike ticket, which would also escalate their identical labelled-auto twins | After human review of the 90 |
| Fluency gap 7.1 points | Closed in v3 by hybrid retrieval (2.4 points) | — | Done |
| Evidence threshold at the retrieval floor (0.06) | Selection showed no safety gain from higher values on calibration data | Lower coverage | When a passage-level gold set exists |

## 5. Section five: the reflection

| Question | Your answer |
|---|---|
| What did you most misunderstand about the problem when you wrote version one? | I treated escalation as the safe default and the labels as ground truth. The result was a system that escalated 91% of tickets, worse than the 58% baseline. It would have failed Marcus's second test ("makes more work than it saves") while appearing safe. |
| Which piece of discovery work would have caught it earlier? | A label-consistency count in Stage 1, section 2 (identical text, different labels), and a held-out check before building on a predicted field. |
| What would you do differently if you started again on Monday? | Build the train/calibration split and threshold-selection harness first, and write requirements as "escalate what cannot be grounded" from day one. |
| What is still uncertain, and what would you need to resolve it? | Whether the 90 label-disagreement answers are acceptable (needs human review), the real hallucination and citation rates (two-person review of ≥50 answers), and whether dense retrieval closes the fluency gap (needs Azure access). |
