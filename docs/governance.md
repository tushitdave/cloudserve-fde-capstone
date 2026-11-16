# Governance: risk, fairness, decision logging and incident response

Written against the capstone Governance Framework for policy v2, 16 November 2026. Every mitigation below names a control that exists in the code and the test that shows it working. Where a control does not exist, the risk entry says so.

Owners are roles. In this single-student project the student holds all of them for the prototype; a CloudServe deployment would assign named people.

## 1. Decision logging

Every ticket writes a `decision` event holding the Framework's minimum record:

- `decision_id`, `timestamp`, `ticket_id`, `stage`, `input_summary` (channel, length, SHA-256 of the input; no raw identity)
- `model` name, version and calibration flag
- `prediction` and `alternatives` with confidences
- `sources_used` with scores and source versions
- `threshold_applied`, `rule_ids_fired` and `policy_version`
- `action_taken` (`auto_respond | escalate | block`) and a readable `reason`
- `guardrail_results` (pass/fail per check), `prompt_version` and `requirement_ids`

A `terminal` event follows. The run manifest reconciles input IDs against terminal and decision IDs exactly, and the batch harness fails the run if they differ. Coverage was 500/500 on development and 80/80 on validation (`evaluation/reports/*-policy-v2/run_manifest.json`). Tests: `tests/test_policy_v2.py::test_documented_ticket_is_answered_with_full_decision_record`, `tests/test_rehearsal.py`.

## 2. Risk register

| ID | Risk | Likelihood | Impact | Mitigation in this design (control → evidence) | Residual risk | Owner |
|---|---|---|---|---|---|---|
| R-01 | Confidently wrong answer | Medium | High | Calibrated intent ≥0.90; novelty gate (similarity ≥0.35); intent→approved-article scope; evidence threshold; extractive answer whose every line is verified as an exact span of the cited passage; thresholds chosen under a ≤5% wrong-article constraint. Wrong article: 1.9% of sent on development, 1.8% on validation. | The right article can still be the wrong advice for a specific account. 90 dev answers went to label-`escalate` tickets and are unreviewed. | Head of Support (policy owner) |
| R-02 | Private data in an outbound reply | Low | Critical | Extractive replies contain only approved article text. The `private_data` guardrail (email, key, card, phone, customer ID, customer name) runs on every answer and blocks; it never redacts and sends. 0 detections on 419 answers; injected email draft blocked (`tests/test_safety_suite.py`). | Pattern lists miss unusual identifiers. Azure mode could echo ticket text; the guardrail still runs. | Security lead |
| R-03 | Customer text treated as an instruction | Medium | High | Ticket text is passed to models as labelled untrusted data. The `instruction_integrity` guardrail blocks override attempts before drafting and records them. Extractive mode never follows ticket text. Test: `test_engineered_ticket_trips_instruction_integrity_guardrail`. | Paraphrased injections outside the pattern set; extractive mode limits the damage. | Security lead |
| R-04 | Some customer groups get worse answers | **Observed** | Medium | Fairness segments are computed in every run's `metrics.json`. Customer tier, region and name are not model features. | **Not mitigated:** non-fluent safe-auto recall is 7.1 points below fluent on development (section 3). Dense retrieval is the planned fix, not yet measured. | Evaluation owner |
| R-05 | Documentation goes stale | Medium | Medium | Approved-source manifest with hashes; any change goes through staging, the steward review, human certification and atomic publish; old citations stay resolvable by version; a citation whose source changed before release is blocked. | The supplied snapshot has `last_reviewed_days_ago = 0` everywhere, so staleness detection is untested. | Technical writer (knowledge owner) |
| R-06 | Model provider unavailable | Medium | Medium | The default extractive path needs no provider. In Azure mode, timeout, 429 or outage escalates with `processing_failure` (`tests/test_safety_suite.py`). | Retry/backoff under real 429s is untested live. | Engineering on-call |
| R-07 | Latency degrades under load | Low (local) | Medium | Local p95 is 8–10 ms; models are cached in-process. | No load test; SQLite writes serialise; Azure mode adds network latency. | Engineering on-call |
| R-08 | Costs rise with volume | Low | Low | No model call in the default path; Azure is opt-in per run; no per-ticket agent chain. | Azure mode cost is unmeasured. | Head of Support (budget) |
| R-09 | Thresholds tuned on the check set | Medium | Medium | Thresholds selected on the calibration split only (`threshold_selection_v1.json`); three validation-fitted regexes removed; validation runs counted. | 62/80 validation bodies duplicate development text, so validation is optimistic. | Evaluation owner |

## 3. Fairness audit

Method: the policy-v2 unattended runs, segmented by the Framework's groups.

- **Resolution rate** is the share of the segment answered automatically.
- **Quality score** is safe-auto recall: tickets labelled `auto_respond` that were answered and cited an expected article, divided by tickets labelled `auto_respond` in the segment.
- **Short/long** splits at the development median of 28 words.
- No human quality rating exists yet. The sample is the full set, so sizes are as shown.

**Development (500)**

| Segment | Tickets | Resolution rate | Quality score | Gap from best (pts) |
|---|---:|---:|---:|---:|
| Enterprise | 83 | 79.5% | 90.2% | 0.0 |
| Business | 164 | 69.5% | 85.8% | 4.4 |
| Standard | 253 | 72.7% | 85.7% | 4.5 |
| Fluent English | 380 | 74.2% | 88.3% | 0.0 |
| Non-fluent English | 120 | 68.3% | 81.2% | **7.1** |
| Short (≤28 words) | 273 | 69.2% | 84.7% | 4.0 |
| Long (>28 words) | 227 | 77.1% | 88.7% | 0.0 |
| Asia-Pacific | 119 | 71.4% | 92.2% | 0.0 |
| Europe | 151 | 76.2% | 88.3% | 3.9 |
| North America | 170 | 70.0% | 83.8% | 8.4 |
| Latin America | 60 | 75.0% | 79.5% | **12.7** |

**Visible validation (80)** — groups are too small to support conclusions: enterprise has 6 labelled-auto tickets, Latin America 3 and non-fluent 8. Quality scores: fluent 82.5% versus non-fluent 75.0%; business 76.2%, standard 85.7%, enterprise 83.3%.

**Findings.**

- The variation the Framework predicts is present. Non-fluent tickets do worse by 7.1 points, mostly because lexical retrieval misses their phrasing: 10 of 80 labelled-auto non-fluent tickets escalated on insufficient evidence, against 19 of 231 fluent.
- The failure direction is safe. A non-fluent customer is more likely to be escalated, not more likely to get a wrong answer.
- Regional gaps (Latin America, North America) have no causal feature in the model, since region is not an input. With n=39–105 labelled-auto tickets they are likely sampling noise, but they are reported, not dismissed.
- Enterprise customers are not worse served, which addresses Marcus's and Ravi's concern.
- The <5-point condition **is not met** for fluency and region. Deployment should wait for the dense-retrieval comparison and a human-rated sample per group.

## 4. Guardrails

| Guardrail | Check | Fires → | Where |
|---|---|---|---|
| Private data | Email, key/token, card, phone, customer ID, customer name | Block and escalate; never redact and send | `guardrails.check_output` |
| Grounding | Every citation is a retrieved approved passage; every cited line is an exact span (extractive) or GPT-4o-verified (Azure) | Block and escalate with the unsupported claim recorded | `guardrails.check_output`, `VerificationAgent` |
| Instruction integrity | Override/system-prompt/role-change patterns in the ticket | Block, escalate and record the input | `guardrails.check_input` |
| Tone and scope | Refund, credit, fix or timeline commitments | Block | `guardrails.check_output`; rule R-06 escalates refund requests earlier |
| Confidence floor | Thresholds applied and recorded on every decision; a missing classification escalates (`processing_failure`) | Escalate | `policy.route`, decision record |

All results, pass or fail, are stored in `guardrail_results`. In the latest runs: 407 + 65 instruction-integrity checks, and 364 + 55 runs of each output check.

## 5. Incident procedure (written for 2 a.m.)

| Step | What to do | Who | Time |
|---|---|---|---|
| 1. Detect | A report of a wrong or unsafe auto-reply, a guardrail spike in `metrics.json` (`guardrail_by_type`), or an unexpected rise in the auto rate. Find the ticket with `GET /v1/tickets/{id}/decision`. | Support agent on shift, or on-call engineer | Immediately on report |
| 2. Contain | **Throw the kill switch:** Overview page → "Stop automatic answers", or `POST /v1/policy/kill-switch {"active": true, "operator": "<name>", "reason": "<why>"}`. If the API is down, restart with `CLOUDSERVE_AUTO_SEND_DISABLED=1`. Confirm `GET /v1/policy/kill-switch` returns `active: true`. | Anyone on the support rota | < 2 minutes |
| 3. Assess | From the decision record read `rule_ids_fired`, `sources_used`, `prompt_version`, `policy_version` and `guardrail_results`. Decide whether the article is wrong (knowledge owner), retrieval picked the wrong article (engineering), or a rule is missing (policy owner). List other affected tickets: same intent and same source version since the last good state. | On-call engineer + Head of Support | < 1 hour |
| 4. Notify | Contact affected customers with a human-written correction. Inform the Head of Support; inform compliance if private data was involved. | Head of Support | Same business day |
| 5. Remediate | Wrong article → stage a corrected revision, steward review, certify, publish. Missing rule → new rule in a new `policy_vN.json` with evidence and a test. Thresholds → rerun `evaluation.threshold_selection`. Run `./scripts/test.sh` and a full batch, then turn the switch off. | Knowledge owner / policy owner / engineer | Hours to days |
| 6. Review | Add the incident ticket as a regression fixture and record the change in the PRD revision log. | Policy owner | Within a week |

## 6. Kill switch

| Question | Answer |
|---|---|
| What is the mechanism? | A runtime flag read on every ticket: UI button, `POST /v1/policy/kill-switch`, or the `CLOUDSERVE_AUTO_SEND_DISABLED=1` environment variable. An unreadable flag file fails closed (switch on). Rule R-00, highest priority. |
| Who is authorised? | Policy: Head of Support and anyone on the support rota. Today any caller of the local API can use it, because authentication is not implemented. That is a known gap and a reason the API must not be exposed publicly. |
| How long until it takes effect? | The next ticket decision. No deploy or restart. |
| What happens to tickets in flight? | The switch is re-checked after validation and before release, so a ticket drafted before the switch is held and escalated, not sent. |
| How is it tested? | `test_kill_switch_stops_automatic_answers_without_redeploy`, `test_kill_switch_environment_override`, `test_kill_switch_api_round_trip`. |

## 7. Declaration

| Statement | Position |
|---|---|
| This system must never … | send an automatic answer to a security, compliance, billing-dispute, account-compromise or roadmap request, or send text that is not traceable to an approved CloudServe article. |
| The mechanism that enforces that is … | versioned protective rules R-01–R-07 evaluated in code before any drafting; extractive answers built only from approved passages and verified line by line; deterministic guardrails that block; the kill switch. Protected false-auto is 0/101 across development and validation. |
| The most likely way it could still cause harm is … | sending the right article to a customer whose specific situation it does not fit. That could be a novel phrasing that resembles a known request, or a ticket the supplied labels say should escalate (90 such answers in development, unreviewed). Non-fluent customers are also escalated more often, so they wait longer. |
| We would not deploy this without first … | a two-person human review of at least 50 automatic answers (hallucination and citation accuracy), authenticated access and role checks on the API, a dense-retrieval comparison to address the fluency gap, and a supervised pilot measuring real resolution and repeat contacts. |
