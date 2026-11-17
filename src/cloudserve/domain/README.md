# Domain layer

Pure business rules and contracts. Imports only `cloudserve.domain` and `cloudserve.config` (enforced by `scripts/architecture_check.py`).

- `models/contracts.py`: typed handoff contracts (exported as JSON Schemas in `docs/schemas/`).
- `policies/policy.py`, `policy_rules.py`, `policy_v2.json`: versioned rule engine, thresholds, kill switch, conflict detection.
- `policies/guardrails.py`: deterministic input/output guardrails.
