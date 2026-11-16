# CloudServe gold annotation guide — v1

## Purpose and status

This package freezes the **supplied** route, intent, urgency, answerability and expected-document labels for 500 development and 80 visible-validation tickets. It also prepares 120 development tickets for two independent passage/claim reviewers. The supplied labels are useful seed truth, but the model trained on the development set and the visible-validation labels informed policy tuning. Neither split is an untouched final holdout. The 120-ticket passage/claim queue is **pending human adjudication**.

A valid support response does not need to match a reference answer word for word. The gold unit is a safe route plus relevant source spans and atomic claims. For an unsupported or protected ticket, the correct result may be escalation with no automatic answer.

## Frozen inputs

`manifest_v1.json` records SHA-256 of all four supplied files, 29 article versions, 145 passage count, selection method, and the 120 selected ticket IDs hash. If any source hash changes, create a new gold version; do not silently edit v1. `supplied_labels_v1.jsonl` has one source-labelled row per ticket. `review_queue_v1.jsonl` is the adjudicator's queue with supplied label seeds, candidate passages, and blank adjudicated fields. `reviewer_a_template_v1.jsonl` and `reviewer_b_template_v1.jsonl` are independent forms without the supplied label seeds or model outputs.

Candidate passages combine lexical top results and the supplied expected documents' Resolution sections. They are **not gold passage labels** and may omit a relevant passage. Reviewers may search the full frozen `data/supplied/documentation.json` corpus; record any additional passage ID. Do not use the system's generated answer to decide relevance.

## Reviewer instructions

For each assigned ticket, read subject and body as the customer request. Use only the frozen articles. Fill these fields independently in your own reviewer copy:

- `reviewer_name`, `reviewed_at`: person and ISO timestamp.
- `route`: `auto_respond` only if a safe, complete answer exists in approved articles and no specialist-only policy applies; otherwise `escalate`.
- `answerable_from_frozen_kb`: `true` only if article text can answer the actual question without account-specific inspection, unapproved commitments, or speculation.
- `passage_labels`: map every reviewed passage ID to `relevant`, `partly_relevant`, or `irrelevant`. Use `relevant` only when it directly supports the needed answer. For no-answer cases, record `no_article_exists` in `notes` after checking the full corpus.
- `supporting_spans`: list `{passage_id, exact_text}` for each decisive source span. Copy text exactly; the adjudication validator will check that the text occurs in the passage at the frozen version.
- `required_claims`: short, atomic factual points a safe answer must contain. Example: `Use cursor pagination when the collection changes during iteration.` Avoid style or exact wording requirements.
- `forbidden_claims`: false, unsupported or unauthorized claims the answer must not contain. Include ticket-specific risks in addition to generic refund/fix/timeline promises.
- `notes`: explain ambiguity, why an escalation is needed, and any missing source. Do not insert a model prediction as evidence.

The `must_mention` and `must_not_claim` fields from supplied senior-agent references are **seeds for adjudication**, not human-approved claims. References exist only for 200 development tickets and can contain incomplete or stylistic wording.

## Adjudication

1. Reviewers A and B work independently. Preserve their completed files unchanged.
2. Compare route, answerability, relevant passages and atomic claims. Record disagreements per ticket and resolve using the frozen source. A third reviewer decides unresolved cases.
3. Copy the v1 queue into a **new adjudicated v2 file**. Fill final labels, set `review_status` to `approved`, add reviewer names, supporting spans and an adjudication note. Never edit frozen v1 or mark a row approved solely because supplied labels and an automatic answer agree.
4. Record agreement: route exact-match agreement; passage binary relevance agreement or Cohen's kappa; claim disagreements as count and resolution notes. Report denominators and missing ratings.
5. Once approved, freeze a **new adjudicated version** with hashes. Do not overwrite this seed version. Use the new version for passage Recall@k, MRR and claim-support/hallucination assessments.

## Scoring rules

`gold_eval.py` can already score intent, urgency, route, unsafe auto, expected-document citation hit and citation ID/version resolution against the supplied seed labels. It reports `claim_support_rate: null` and `hallucination_rate: null` until human claim labels exist. Document hit here uses **final answer citations**, not raw retrieval Recall@k. Report safe-auto coverage and false-auto count together; a low false-auto rate with near-zero automation is not a complete success.

A true final holdout needs newly collected or separately authored and human-reviewed tickets that were never used for training, threshold selection or policy tuning. Keep it sealed until model and policy versions are frozen. Do not use hidden assessment data for development.
