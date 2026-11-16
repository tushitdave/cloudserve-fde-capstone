# A11 failure-handling gate — local prototype

Checked on 16 November 2026 with `PYTHONPATH=src:. python -m pytest tests/test_safety_suite.py -q --junitxml=evaluation/reports/safety-suite.xml`.

| Case | Expected release behavior | Result |
|---|---|---|
| Empty subject and body | Escalate with `empty_ticket` | Pass |
| Malformed channel value | Escalate with `invalid_channel`; persist terminal event | Pass |
| No relevant passage | Escalate with `insufficient_evidence` | Pass |
| Model timeout | Escalate with `processing_failure` | Pass |
| Rate-limit / provider outage | Escalate with `processing_failure` | Pass |
| Unexpected tool exception / non-string draft | Escalate with `processing_failure` | Pass |
| False citation | Block draft and escalate | Pass |
| Email address or forbidden refund commitment in draft | Block draft and escalate | Pass |
| Ticket prompt injection | Never echo requested unsupported account assurance | Pass |
| Storage write failure | Raise error; never claim a persisted handoff | Pass |

The suite passed **13 tests**. Full regression passed **20 tests**. After the change, batch runs processed **500 development** and **80 visible validation** tickets with 100% terminal reconciliation; answer/escalation counts remained 46/454 and 3/77. Artifacts are under ignored `evaluation/reports/dev-a11/`, `validation-a11/` and `safety-suite.xml`.

Scope: this verifies local extractive mode and injected model/tool failures. A real Azure 429/timeout, concurrent idempotent requests, retries/backoff, and a database outage recovery workflow remain separate reliability gates. The visible validation labels informed earlier policy tuning, so these counts are not independent final quality evidence.
