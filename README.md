# CloudServe support prototype

CloudServe is a six-role support workflow prototype for the FDE capstone. It classifies fictional support tickets, searches 29 approved articles, releases an answer only after evidence and policy checks, and otherwise records a human handoff. The React workspace lets a reviewer submit tickets, inspect scores and exact citations, browse handoffs and view local metrics.

The [architecture](docs/architecture.md) is the design target. The [build ledger](docs/BUILD_PLAN.md) records implemented behavior and remaining acceptance work. Current role implementations are bounded: source intake and knowledge stewardship inspect the supplied snapshot, triage recommends human review, evidence searches at most twice, answer drafts from an approved passage or GPT-4o, and verification checks citation support. Code owns the final release decision.

## Run locally

Prerequisites: Python 3.12 or newer, Node.js 22 or newer with npm, and Git. No API key is needed; the default mode makes no model calls. If `python3 --version` is older than 3.12, use `python3.12` in the first command below. From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm --prefix frontend ci
CLOUDSERVE_PYTHON=.venv/bin/python ./scripts/dev.sh
```

Open `http://localhost:5173`. Vite proxies `/api` to FastAPI on port 8001. If port 8001 is already occupied, stop the earlier Uvicorn process before starting the combined development command. A Docker Compose build is defined in `deploy/compose.yaml` for a machine with Docker Compose and network access. The API serves OpenAPI at `http://localhost:8001/docs`.
Set `CLOUDSERVE_API_PORT=8012` on the command when port 8001 is occupied; the backend and Vite proxy will use the same alternate port.

One-command checks and the unattended batch run, from the same directory. The batch command takes any input file and a new output directory, and writes `results.json`, `metrics.json` and `run_manifest.json` there:

```bash
CLOUDSERVE_PYTHON=.venv/bin/python ./scripts/test.sh
CLOUDSERVE_PYTHON=.venv/bin/python ./scripts/batch.sh data/supplied/development_tickets.json evaluation/reports/local-run
```

`scripts/batch.sh` accepts any compatible JSON-list input path and a fresh output directory. A rerun into the same output directory reuses persisted ticket IDs; use a new output directory for a different file.

The default `CLOUDSERVE_MODEL_MODE=extractive` runs locally without Azure calls. `CLOUDSERVE_MODEL_MODE=azure` uses GPT-4o for answer and verification, with escalation on provider failure. Copy `.env.example` to `.env` only if using Azure. The embedding deployment is opt-in:

```bash
PYTHONPATH=src python scripts/build_dense_index.py
```

This writes a version-checked, 1536-dimensional index under ignored `data/runtime/`. Search then reranks lexical candidates with Azure dense similarity. It falls back to lexical ranking on embedding query failure. The supplied reference answers are never indexed as answer authority.

## Policy, thresholds and kill switch

Routing rules live in `src/cloudserve/policy_v2.json`: versioned, each with evidence and requirement IDs. Thresholds are selected on the held-out calibration split by `PYTHONPATH=src:. python -m evaluation.threshold_selection`, which writes `data/manifests/threshold_selection_v1.json`. To stop all automatic answers immediately, use the Overview page, `POST /v1/policy/kill-switch` with `{"active": true, "operator": "...", "reason": "..."}`, or start with `CLOUDSERVE_AUTO_SEND_DISABLED=1`. See [PRD revision R1](docs/PRD_revision_log.md) and the [evaluation snapshot](docs/evaluation_snapshot.md).

## Test and evaluate

```bash
PYTHONPATH=src:. pytest -q
PYTHONPATH=src python -m evaluation.harness --input data/supplied/development_tickets.json --output evaluation/reports/dev
PYTHONPATH=src python -m evaluation.harness --input data/supplied/validation_tickets.json --output evaluation/reports/validation
```

Each batch writes `results.json`, `metrics.json`, `run_manifest.json` and `run.sqlite`. Metrics distinguish offline proxies from observed customer outcomes. The 500-ticket development data trained the classifier; the visible 80-ticket set informed policy tuning. Neither is untouched final gold. A human-reviewed claim and passage gold set is still needed before claiming trust targets.

The [gold seed package](evaluation/README.md) now freezes all 580 supplied route/document labels and prepares a 120-ticket, two-reviewer passage/claim queue. Its scorer validates source hashes and reports current route/document performance; semantic claim-support metrics stay unavailable until human adjudication.

The [offline evaluation snapshot](docs/evaluation_snapshot.md) gives denominators for the 500/80 runs, ECE, protected false-auto counts, citation resolvability and language-fluency cuts. It explicitly leaves hallucination, semantic citation accuracy and live availability unknown.

## API

`POST /v1/tickets`, `GET /v1/tickets`, `GET /v1/tickets/{id}`, `GET /v1/tickets/{id}/decision`, `GET /v1/escalations`, `POST /v1/escalations/{id}/resolve`, `POST /v1/feedback`, `GET /v1/knowledge/documents`, `GET /v1/knowledge/indexes/active`, `GET /v1/knowledge/passages/{id}`, `GET /v1/metrics`, `GET /v1/policy/active` and `GET|POST /v1/policy/kill-switch`. Ticket IDs are idempotent for the same input; a different input with an existing ID returns 409. Accepted tickets have one persisted terminal state and decision log. A human reviewer can record an outcome for an escalated ticket; this adds an audit event and removes it from the open queue without changing the original terminal result or sending a customer message. Duplicate identical resolutions return the existing record; a conflicting second resolution returns 409.

The [knowledge pipeline](docs/knowledge_pipeline.md) adds `POST/GET /v1/knowledge/jobs`, `POST /v1/knowledge/jobs/{id}/approve|reject|publish`, `GET /v1/knowledge/documents/{id}`, `GET /v1/knowledge/documents/{id}/versions`, and `GET /v1/knowledge/documents/{id}/lineage?source_version=...`. The Knowledge page shows the 29 supplied articles, active and historical passages, citation links, staged updates, quarantine reasons and review actions. Restart a backend started without `--reload` to see these routes.

This is a local demonstration API. The knowledge approval fields currently accept user-entered names; identity, tenant authorization, production monitoring and a clean deployment rehearsal remain open gates. Do not expose it publicly.

## Repository

`src/cloudserve/` holds the FastAPI application, ML classifier, agents, policy, retrieval and SQLite persistence. `frontend/` holds the React workspace; `data/supplied/` contains the fictional capstone data; `evaluation/` contains the batch harness; `tests/` contains workflow regression tests; `docs/` and `prompts/` contain project design notes. Secrets, runtime databases and evaluation reports are Git ignored.
