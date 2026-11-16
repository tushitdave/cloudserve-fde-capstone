# Governance: risk, fairness, decision logging and incident response

Written against the capstone Governance Framework for policy v3, 16 November 2026. Every mitigation below names a control that exists in the code and the test that shows it working. Where a control does not exist, the risk entry says so.

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
| R-01 | Confidently wrong answer | Medium | High | Calibrated intent ≥0.90; novelty gate (similarity ≥0.35); intent→approved-article scope; hybrid evidence threshold; extractive answer whose every line is verified as an exact span of the cited passage; thresholds chosen under a ≤5% wrong-article constraint. Wrong article: 0.5% of sent on development (2/402), 0% on validation. | The right article can still be wrong advice for a specific account. 100 dev answers went to label-`escalate` tickets and are unreviewed. | Head of Support (policy owner) |
| R-02 | Private data in an outbound reply | Low | Critical | Extractive replies contain only approved article text. The `private_data` guardrail (email, key, card, phone, customer ID, customer name) runs on every answer and blocks; it never redacts and sends. 0 detections on 463 answers (v3); injected email draft blocked (`tests/test_safety_suite.py`). | Pattern lists miss unusual identifiers. Azure mode could echo ticket text; the guardrail still runs. | Security lead |
| R-03 | Customer text treated as an instruction | Medium | High | Ticket text is passed to models as labelled untrusted data. The `instruction_integrity` guardrail blocks override attempts before drafting and records them. Extractive mode never follows ticket text. Test: `test_engineered_ticket_trips_instruction_integrity_guardrail`. | Paraphrased injections outside the pattern set; extractive mode limits the damage. | Security lead |
| R-04 | Some customer groups get worse answers | Observed, **reduced** | Medium | Fairness segments computed in every run; customer tier, region and name are not model features. Hybrid dense retrieval (Chroma, all-MiniLM-L6-v2) selected partly because it closed the fluency gap: 7.1 → 2.4 points on development. | Regional gap 10.3 points (Latin America, n=39), not met. Validation groups too small to judge. | Evaluation owner |
| R-05 | Documentation goes stale | Medium | Medium | Approved-source manifest with hashes; any change goes through staging, the steward review, human certification and atomic publish; old citations stay resolvable by version; a citation whose source changed before release is blocked. | The supplied snapshot has `last_reviewed_days_ago = 0` everywhere, so staleness detection is untested. | Technical writer (knowledge owner) |
| R-06 | Model or provider unavailable | Medium | Medium | The default path needs no generative provider. If the dense index or MiniLM model is unavailable, retrieval falls back to lexical with the reason logged: 359/500 sent, protected 0, wrong article 0.6% in a forced-fallback run. In Azure mode, timeout, 429 or outage escalates with `processing_failure`. | First run needs internet for the ONNX models; live 429 retry is untested. | Engineering on-call |
| R-07 | Latency degrades under load | Low (local) | Medium | Local p95 206 ms including dense query embedding; indexes and models are cached in-process; per-key rate limit (429). | No load test; SQLite writes serialise. | Engineering on-call |
| R-08 | Costs rise with volume | Low | Low | No model call in the default path; Azure is opt-in per run; no per-ticket agent chain. | Azure mode cost is unmeasured. | Head of Support (budget) |
| R-09 | Thresholds tuned on the check set | Medium | Medium | Thresholds selected on the calibration split only (`threshold_selection_v1.json`); three validation-fitted regexes removed; validation runs counted. | 62/80 validation bodies duplicate development text, so validation is optimistic. | Evaluation owner |
| R-10 | Unauthorised access to another customer's tickets or to operator actions | Medium | High | API key on every call; five roles; object-level tenant check returning 404 outside the tenant; kill switch limited to operator/admin; knowledge publishing limited to knowledge owner (`tests/test_security.py`). | Demo keys are public and must be replaced (`CLOUDSERVE_API_KEYS`, `CLOUDSERVE_DEMO_KEYS=0`); no SSO or key rotation. | Security lead |
| R-11 | Raw customer text retained too long or exposed at rest | Medium | High | Fernet encryption of stored results and events; customer erasure and retention purge that keep decision records; decision log holds an input hash, not raw text. | Key management is a local file unless `CLOUDSERVE_DATA_KEY` comes from a secret store. | Security lead |

## 3. Fairness audit

Method: the policy-v2 unattended runs, segmented by the Framework's groups.

- **Resolution rate** is the share of the segment answered automatically.
- **Quality score** is safe-auto recall: tickets labelled `auto_respond` that were answered and cited an expected article, divided by tickets labelled `auto_respond` in the segment.
- **Short/long** splits at the development median of 28 words.
- No human quality rating exists yet. The sample is the full set, so sizes are as shown.

**Development (500), policy v3 (hybrid retrieval)**

| Segment | Tickets | Resolution rate | Quality score | Gap from best (pts) |
|---|---:|---:|---:|---:|
| Enterprise | 83 | 85.5% | 100.0% | 0.0 |
| Business | 164 | 78.7% | 97.2% | 2.8 |
| Standard | 253 | 79.8% | 95.5% | 4.5 |
| Fluent English | 380 | 80.5% | 97.4% | 0.0 |
| Non-fluent English | 120 | 80.0% | 95.0% | 2.4 |
| Short (≤28 words) | 273 | 75.8% | 94.7% | 4.6 |
| Long (>28 words) | 227 | 85.9% | 99.3% | 0.0 |
| Asia-Pacific | 119 | 78.2% | 100.0% | 0.0 |
| Europe | 151 | 82.1% | 98.1% | 1.9 |
| North America | 170 | 79.4% | 96.2% | 3.8 |
| Latin America | 60 | 83.3% | 89.7% | **10.3** |

**Visible validation (80).** Groups are too small to support conclusions (enterprise 6 labelled-auto tickets, Latin America 3, non-fluent 8). Quality scores: fluent 92.5%, non-fluent 100%; business 95.2%, standard 90.5%, enterprise 100%.

**Findings.**

- The variation the Governance Framework predicts was present under lexical retrieval: non-fluent recall was 7.1 points below fluent, because lexical matching misses non-fluent phrasing. Dense retrieval reduced it to 2.4 points. This is the clearest case in the project of a fairness finding changing a design decision (PRD revision R2).
- Tier and length gaps are now under 5 points, and enterprise customers are not worse served (Marcus's and Ravi's concern).
- **Not met:** Latin America is 10.3 points below the best region. Region is not a model input and n=39, so it is probably noise, but it is reported, not dismissed. Deployment should wait for a larger human-rated sample per region.

## 4. Guardrails

| Guardrail | Check | Fires → | Where |
|---|---|---|---|
| Private data | Email, key/token, card, phone, customer ID, customer name | Block and escalate; never redact and send | `guardrails.check_output` |
| Grounding | Every citation is a retrieved approved passage; every cited line is an exact span (extractive) or GPT-4o-verified (Azure) | Block and escalate with the unsupported claim recorded | `guardrails.check_output`, `VerificationAgent` |
| Instruction integrity | Override/system-prompt/role-change patterns in the ticket | Block, escalate and record the input | `guardrails.check_input` |
| Tone and scope | Refund, credit, fix or timeline commitments | Block | `guardrails.check_output`; rule R-06 escalates refund requests earlier |
| Confidence floor | Thresholds applied and recorded on every decision; a missing classification escalates (`processing_failure`) | Escalate | `policy.route`, decision record |

All results, pass or fail, are stored in `guardrail_results`. In the latest (v3) runs: 407 + 65 instruction-integrity checks, and 402 + 61 runs of each output check, all passing.

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
| Who is authorised? | The operator and admin roles (enforced by API key; a support agent receives 403). Policy: the Head of Support and the on-call operator. The UI records the operator name together with the key ID. |
| How long until it takes effect? | The next ticket decision. No deploy or restart. |
| What happens to tickets in flight? | The switch is re-checked after validation and before release, so a ticket drafted before the switch is held and escalated, not sent. |
| How is it tested? | `test_kill_switch_stops_automatic_answers_without_redeploy`, `test_kill_switch_environment_override`, `test_kill_switch_api_round_trip`. |

## 7. Declaration

| Statement | Position |
|---|---|
| This system must never … | send an automatic answer to a security, compliance, billing-dispute, account-compromise or roadmap request, or send text that is not traceable to an approved CloudServe article. |
| The mechanism that enforces that is … | versioned protective rules R-01–R-07 evaluated in code before any drafting; extractive answers built only from approved passages and verified line by line; deterministic guardrails that block; the kill switch. Protected false-auto is 0/101 across development and validation, and the rule table is checked for conflicts before it can load. |
| The most likely way it could still cause harm is … | sending the right article to a customer whose specific situation it does not fit. That could be a novel phrasing that resembles a known request, or a ticket the supplied labels say should escalate (90 such answers in development, unreviewed). Non-fluent customers are also escalated more often, so they wait longer. |
| We would not deploy this without first … | a two-person human review of at least 50 automatic answers (hallucination and citation accuracy, starting with the 100 label-disagreement cases); replacing the demo API keys and moving the data key to a secret store; a larger per-region sample to settle the Latin America gap; and a supervised pilot measuring real resolution and repeat contacts. |
