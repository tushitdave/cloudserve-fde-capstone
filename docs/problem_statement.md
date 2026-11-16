# CloudServe problem statement and discovery evidence

## Business problem

CloudServe receives more than 500 support tickets each week across email, chat, documentation comments and a forum. The stated company baseline is 8–12 hours to first reply, 42% first-contact resolution, 58% escalation and 3.2/5 customer satisfaction. Support staff already have approved articles, but finding and applying them consistently is slow; escalations often omit enough context for a specialist to act quickly. The business goal is to answer routine documented questions promptly while sending sensitive, uncertain and undocumented cases to a human with useful context and a traceable reason.

## Technical problem

Build an unattended four-channel workflow that normalizes every ticket, predicts intent and urgency, retrieves identifiable passages from approved documentation, routes by deterministic policy, generates a grounded answer only when evidence is sufficient, blocks unsupported or private claims, and persists one final `sent` or `escalated` decision per ticket. It must process an arbitrary unseen JSON file, emit a metrics report, and remain safe when retrieval or a model fails.

## Evidence IDs

| Finding | Evidence | Design consequence |
|---|---|---|
| F01 | Project Brief company baseline: >500 weekly tickets; 8–12 hour first reply; 42% first-contact resolution; 58% escalation; 3.2/5 CSAT. | Optimize a safe documented-answer path and measure real customer outcomes only in a later pilot. |
| F02 | Five stakeholder interviews describe difficult internal search, personal answer files and escalations with missing context. | Use one approved KB and structured human handoff. |
| F03 | Supplied corpus has 29 approved articles; all `last_reviewed_days_ago` values are zero in this snapshot. | Store source/version lineage; do not claim staleness detection was evaluated. |
| F04 | Development set has 500 tickets, four channels and 22 intent labels; 357 are labelled answerable from docs, 311 expected auto, 87 must not auto-respond. | Train baseline classification, hard-block protected routes and measure safe coverage. |
| F05 | Visible validation set contains 80 tickets; reference responses cover 200 development tickets and include `must_mention`/`must_not_claim`. | Keep validation diagnostic, freeze independent human passage/claim gold, never treat reference wording as source authority. |
| F06 | Development historical fields calculate to 43.8% first-contact resolution, 56.2% escalation and 2.972/5 mean CSAT; first-reply and post-automation outcomes are absent. | Separate offline proxies from observed business improvement and disclose the baseline mismatch. |
| F07 | Supplied route/answerability labels conflict on identical text: 40 of 191 duplicate-text groups of non-protected dev + validation tickets carry both outcomes. A text answerability classifier scores ROC AUC 0.32 on the held-out calibration split and 0.55 on validation. | Do not gate on predicted answerability; escalate what cannot be grounded (protective rule, novelty, intent confidence, approved article, passage evidence). Report label disagreement separately from protected safety failures. See [PRD revision R1](PRD_revision_log.md). |
| F08 | 62 of 80 visible validation ticket bodies appear verbatim in the development set; held-out intent accuracy is 1.00, but out-of-scope text still receives ~0.99 calibrated confidence. | Treat validation as optimistic; add a novelty gate and an out-of-scope fixture as a hard threshold constraint. |
| F09 | Urgency is 50% accurate on the held-out split; identical text carries different urgency labels. Non-fluent customers have 7 points lower safe-auto recall on development. | Urgency is used for prioritisation only. The fluency gap is reported as a fairness finding with dense retrieval as the candidate mitigation. |

Evidence sources: `Capstone_Pack/01_Read_First/01_Project_Brief.docx`, `Capstone_Pack/05_Datasets/Stakeholder_Interviews.docx`, the four supplied JSON files, and the audited counts in `Research/01_project_evidence.md`. These are fictional capstone assets, not production customer records.

## FDE considerations and assumptions

- The system is delivered as one modular FastAPI/React application with two logical pipelines. This reduces clean-checkout and deployment risk for the capstone.
- The 29 supplied articles are approved baseline authority. Any changed article needs human certification. Reference answers are evaluation hints only.
- Six bounded roles have distinct responsibilities. Agents propose parsing, triage, evidence, drafting and verification; code owns permissions, policy and release.
- An automatic answer is only a local offline outcome. Without customer confirmation, it is not observed first-contact resolution.
- The supplied 80-ticket validation set has informed tuning, so it cannot be called an untouched final holdout. The hidden assessment set must remain unseen.
- Tenant identity and live support-system integration are absent from the supplied data. The local API must not be exposed publicly until role and object authorization are implemented.
