# CloudServe support intelligence

CloudServe is a governed support-automation system for the FDE capstone. It classifies support tickets from four channels and retrieves evidence from 29 approved articles with hybrid lexical + dense (Chroma, all-MiniLM-L6-v2) search. It releases a cited answer only after deterministic policy, verification and guardrail checks; anything else becomes a human handoff with context. Orchestration is a LangGraph state graph, the API is FastAPI with role-based access, and a React workspace serves reviewers, knowledge owners and operators.

The [architecture](docs/architecture.md) is the design target. The [build ledger](docs/BUILD_PLAN.md) records what is proven. The [evaluation snapshot](docs/evaluation_snapshot.md) and [governance pack](docs/governance.md) hold the measured results and controls.

## Run locally

Prerequisites: **Python 3.12** (3.13 also works), Node.js 22 or newer with npm, Git, and internet access on the first run. On first use, about 160 MB of ONNX models are downloaded: all-MiniLM-L6-v2 for dense retrieval and ms-marco-MiniLM-L-6-v2 for the reranker experiment. Without network the system still runs, falls back to lexical retrieval, and logs why. No model-provider key is needed; the default mode makes no generative-model calls. From the repository root:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm --prefix frontend ci
CLOUDSERVE_PYTHON=.venv/bin/python ./scripts/dev.sh
```

Open `http://localhost:5173`. Vite proxies `/api` to FastAPI on port 8001; OpenAPI is at `http://localhost:8001/docs`. If port 8001 is busy, set `CLOUDSERVE_API_PORT=8012` on the same command. Use the **Acting as** selector in the top bar to switch between the local demo roles.

## One-command tests and the unattended run

```bash
CLOUDSERVE_PYTHON=.venv/bin/python ./scripts/test.sh
CLOUDSERVE_PYTHON=.venv/bin/python ./scripts/batch.sh <input.json> <new-output-dir>
```

`test.sh` runs the architecture/credential check, the Python suite and the React production build. `batch.sh` processes any compatible JSON list unattended, for example `data/supplied/validation_tickets.json`. It writes `results.json`, `metrics.json` (business, technical, governance, fairness, calibration and drift blocks), `run_manifest.json` (exact input, terminal and decision ID lists) and an encrypted `run.sqlite` decision log. Use a new output directory for each run.

## API access and roles

Every endpoint except `/health` needs an `X-API-Key` header. Without `CLOUDSERVE_API_KEYS`, five **local demo keys** are enabled:

| Key | Role | Can |
|---|---|---|
| `demo-customer-key` | customer (tenant `CUST-DEMO`) | raise tickets and read its own tickets only |
| `demo-agent-key` | support_agent | read all tickets and decisions, resolve handoffs, read knowledge and policy |
| `demo-knowledge-key` | knowledge_owner | stage, approve and publish article revisions |
| `demo-operator-key` | operator | operate the kill switch, read metrics |
| `demo-admin-key` | admin | everything, plus customer data erasure and retention purge |

For any non-local use, set `CLOUDSERVE_API_KEYS` to a JSON list of `{key, key_id, role, tenant}` and `CLOUDSERVE_DEMO_KEYS=0`. Other controls:

- Requests are rate-limited per key (`CLOUDSERVE_RATE_LIMIT_PER_MIN`, default 600).
- Stored results and events are encrypted with `CLOUDSERVE_DATA_KEY` (a Fernet key), or with a generated `data/runtime/data.key` for local use.
- `DELETE /v1/customers/{id}/data` and `POST /v1/admin/retention/purge {"days": 90}` erase raw customer text and keep decision records.

## Retrieval, policy and kill switch

- Retrieval strategies are compared by `PYTHONPATH=src:. python -m evaluation.retrieval_comparison` (lexical, dense, hybrid, hybrid + cross-encoder). The strategy and every threshold are then chosen on the held-out calibration split by `PYTHONPATH=src:. python -m evaluation.threshold_selection` (≈5 min), which writes `data/manifests/threshold_selection_v1.json`. Hybrid was selected; set `CLOUDSERVE_RETRIEVAL_STRATEGY=lexical` to force the fallback.
- Routing rules live in `src/cloudserve/policy_v2.json` (policy v3). Each rule has a priority, effective dates, an approval status, interview evidence and examples. `cloudserve.policy_rules` refuses to load a table with conflicts or failing examples.
- Kill switch: Overview page, `POST /v1/policy/kill-switch` (operator role), or `CLOUDSERVE_AUTO_SEND_DISABLED=1`. It takes effect on the next ticket.
- Measured design choices: `evaluation/chunking_comparison.py`, `evaluation/classifier_comparison.py` and `evaluation/verifier_comparison.py` (needs Azure) write their results to `data/manifests/`.
- Each batch run also writes `traces.jsonl` (OpenTelemetry spans, no raw text) and delivers decided messages through a transactional outbox (`outbox_deliveries.jsonl`).
- ML registry and drift: `PYTHONPATH=src python -m cloudserve.ml_registry` writes `data/manifests/model_registry.json`. Every batch run reports drift against it.

`CLOUDSERVE_MODEL_MODE=azure` optionally uses Azure GPT-4o for drafting and verification behind the same verifier and guardrails. Copy `.env.example` to `.env` only for that mode.

## API

Tickets:

- `POST /v1/tickets`, `GET /v1/tickets`, `GET /v1/tickets/{id}`, `GET /v1/tickets/{id}/decision`
- `GET /v1/escalations`, `POST /v1/escalations/{id}/resolve`
- `POST /v1/feedback`, `GET /v1/metrics`

Knowledge:

- `POST/GET /v1/knowledge/jobs`, `POST /v1/knowledge/jobs/{id}/approve|reject|publish`
- `GET /v1/knowledge/documents[/{id}[/versions|/lineage]]`, `GET /v1/knowledge/passages/{id}`, `GET /v1/knowledge/indexes/active`

Policy and administration:

- `GET /v1/policy/active`, `GET|POST /v1/policy/kill-switch`
- `DELETE /v1/customers/{id}/data`, `POST /v1/admin/retention/purge`

Ticket IDs are idempotent: the same input returns the stored result, and different input with an existing ID returns 409. Every accepted ticket has exactly one terminal state (`sent` or `escalated`) and a decision record.

## Repository

| Path | Contents |
|---|---|
| `src/cloudserve/` | Hexagonal layout: `domain/` (contracts, policy rules, guardrails), `ports/` (Protocol interfaces), `adapters/` (encrypted SQLite + outbox, Chroma/MiniLM + TF-IDF retrieval, calibrated classifier + model registry, Azure OpenAI), `application/use_cases/` (ticket processing, knowledge governance, message delivery), `orchestration/` (LangGraph graph + six agent roles), `observability/` (OpenTelemetry spans, time budgets), `api/` (routes, security). Old flat module paths remain as aliases. |
| `prompts/` | Versioned prompt library and registry |
| `tests/` | Test suite (one command: `scripts/test.sh`) |
| `evaluation/` | Harness, quality report, retrieval comparison, threshold selection, gold seed and fixtures |
| `data/` | Supplied data and manifests (split, source, calibration, thresholds, retrieval comparison, model registry) |
| `docs/` | Architecture, PRD and revision log, governance, evaluation snapshot, workbooks, report |
| `frontend/` | React workspace |

Secrets, runtime databases, model caches and indexes, and evaluation reports are git-ignored.
