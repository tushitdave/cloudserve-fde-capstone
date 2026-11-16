# CloudServe acceptance traceability

This matrix maps every Build Specification criterion to an accountable component, implementation file and executable proof. “Local pass” means the criterion works in the current offline prototype; assessment still uses a fresh checkout and unseen file. “Open” means the stated proof is incomplete.

| ID | Acceptance requirement | Component owner | Implementation | Proof and current state |
|---|---|---|---|---|
| A1 | README commands start from a clean checkout | Application packaging | `README.md`, `requirements.txt`, `frontend/package-lock.json`, `scripts/dev.sh`, `deploy/` | Source-only copy passed offline npm install, 41 tests, React build and 80-ticket run; fresh Python install and live bind remain **open**. |
| A2 | Four channels normalize with original text | Ticket intake | `src/cloudserve/service.py`, `contracts.py` | `tests/test_rehearsal.py::test_four_channel_normalization_preserves_original_text`; **local pass**. |
| A3 | Every ticket has intent, urgency and numeric confidence | Classification ML | `src/cloudserve/classifier.py`, `contracts.py` | `tests/test_workflow.py`, 500/80 batch output; numeric `[0,1]` present, but calibration still **open**. |
| A4 | Retrieval finds real corpus passages | Knowledge and evidence | `src/cloudserve/knowledge.py`, `knowledge_store.py` | `tests/test_retrieval_candidates.py` resolves IDs, versions and offsets; lexical **local pass**, live dense index open. |
| A5 | Threshold route repeats deterministically | Business policy | `src/cloudserve/policy.py`, `service.py` | `tests/test_rehearsal.py::test_same_ticket_and_versions_repeat_routing_decision` compares two isolated stores; **local pass**. Threshold calibration remains open. |
| A6 | Released answer cites retrieved passages | Answer and verification | `src/cloudserve/agents.py`, `service.py`, `knowledge.py` | `tests/test_workflow.py::test_answer_has_real_citation`, historical citation tests; **local pass**. Claim-level human audit open. |
| A7 | Triggered guardrail blocks release | Verification and release | `src/cloudserve/service.py`, `scripts/demo_guardrail.py` | `tests/test_workflow.py::test_guardrail_blocks_forbidden_draft`; demo outputs escalation and no refund promise; **local pass**. |
| A8 | All decisions persist and reconcile | Persistence | `src/cloudserve/storage.py`, `evaluation/harness.py` | `tests/test_rehearsal.py` compares exact input, terminal and decision IDs; 500/80 full-run reports; **local pass**. |
| A9 | Entire arbitrary unseen file runs unattended | Batch harness | `evaluation/harness.py`, `scripts/batch.sh` | 500 development, 80 visible validation and six-item reordered/malformed rehearsal; **local pass**. Hidden assessment remains unseen. |
| A10 | Same run emits metrics automatically | Evaluation | `evaluation/harness.py` | Each run writes `metrics.json` with volume, technical, governance and offline business proxies; **local pass**. Observed live outcomes unavailable. |
| A11 | No hit, timeout, rate limit, outage and malformed input fail safely | Reliability | `service.py`, `azure.py`, `tests/test_safety_suite.py` | 13 injected safety cases and full-run reconciliation; **local pass**, live provider recovery open. |
| A12 | One documented command runs tests | Test harness | `scripts/test.sh`, `README.md`, `.github/workflows/ci.yml` | `CLOUDSERVE_PYTHON=... ./scripts/test.sh` passes 41 tests and React build; clean dependency install/hosted CI **open**. |

The component owner names describe responsibility in this single-student project; they do not imply a separate human team. The [build ledger](BUILD_PLAN.md) controls task completion, and the [submission readiness guide](submission_readiness.md) controls final package evidence.
