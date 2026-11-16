# CloudServe FDE capstone — end-to-end build ledger

**Purpose:** This is the single execution checklist and restart record for the application. Update it after each work session so the next session can see what is done, what failed, what evidence exists, and what to do next. The [architecture](architecture.md) defines *what* to build; this document tracks *when it is actually working*.

**Last reviewed:** 16 November 2026

**Project root for code:** `CloudServe_App/`

**Overall state:** policy v2 (calibrated classifier, versioned rules, kill switch, data-selected thresholds) answers 72.8% of development and 68.8% of visible validation tickets with zero protected false-auto; 64 backend tests and the React build pass. Live browser, dense Azure index, fresh-install/CI and deployment checks remain open.

**Next milestone (student, 17–18 Nov):** review the report and workbooks, fill in effort-log hours, browser-check `scripts/dev.sh` from a fresh clone, record the video, run `scripts/package_submission.sh`.
**Status notation:** `[x]` verified complete · `[ ]` open. A task is complete only when its stated proof is saved. Record blocked work in the session log; do not silently mark it done.

## 1. Source of truth and non-negotiable scope

| Item | Reference | What it controls |
|---|---|---|
| Agreed six-agent/two-pipeline design | [architecture.md](architecture.md) | Agent boundaries, ML tools, HITL and release ownership |
| Architecture-to-code map | [build_map.md](build_map.md) | Intended implementation folders |
| Capstone's twelve pass/fail criteria | `../../Capstone_Pack/01_Read_First/02_Build_Specification.docx` | Working-system gate A1–A12 |
| Submission format | `../../Capstone_Pack/04_Submission/Submission_Guide.docx` | Repository paths, report, video, workbooks, archive |
| Project evidence and dataset limits | `../../Research/01_project_evidence.md` | Business framing and honest outcome claims |
| Proposed handoffs and APIs | `../../Research/03_handoff_json_and_api.md` | Contracts and endpoint starting point |
| Gold and layer metrics | `../../Research/04_evaluation_and_gold.md` | Evaluation definitions and labelling work |
| UI views | `../../Research/05_ui_and_explainability.md` | Customer, support, knowledge and operations screens |
| Full master prompt | `../../Research/Master_prompt.md` | Wider design constraints; conditional work remains conditional |
| Harness/loop/context audit | `../../Research/12_harness_loop_context_audit.md` | Build and runtime controls to implement before expanding agent work |

**Product objective:** safely answer documented CloudServe support questions with resolvable citations, and send sensitive, uncertain or unsupported cases to a human with useful context. Every accepted ticket must finish as `sent` or `escalated`, with a persistent decision record.

**Initial implementation scope:** four channels; supplied approved articles; intent/urgency ML; Azure ada-002 dense retrieval compared with lexical/hybrid search; bounded six-agent roles; GPT-4o default; o3-mini conditional experiment; deterministic business rules and release gateway; FastAPI; React; unattended batch harness; layer-wise evaluation. SQL/GraphRAG/auto-ontology/live CRM integrations are future extensions unless a measured task and suitable source justify them.

## 2. Current verified state — do not overstate

| State | Evidence | Limit |
|---|---|---|
| `[x]` Research, master-prompt gap audit and architecture drafted | `../../Research/` and [architecture.md](architecture.md) | Research is a design proposal, not a deployed system. |
| `[x]` Six agent responsibilities and two pipelines agreed | [architecture.md](architecture.md), `../../Research/10_six_agent_design.md` | Bounded role classes exist; explicit typed envelopes are not enforced at every boundary. |
| `[x]` Azure GPT-4o, o3-mini and ada-002 basic calls confirmed by user | User-reported smoke output: `OK`, `OK`, `dimensions=1536` | Does not establish task quality, cost, quota or p95 latency. |
| `[x]` App folders, FastAPI health source, React shell and container configuration created | `../src/`, `../frontend/`, `../deploy/` | React build passes; container and live browser runs remain open. |
| `[x]` Static syntax checks | Python AST, JSON parse and Compose YAML parse passed in prior session | Runtime integration was not exercised. |
| `[x]` Full unattended prototype runs | `evaluation/reports/dev-prototype-v9/` (500) and `evaluation/reports/validation-prototype-v6/` (80); seven pytest checks passed | Local extractive mode only; validation labels were used to tune policy. |

**Known environment limits at this checkpoint:** `npm ci --offline` and React build pass in a clean source copy. Fresh Python installation, Azure embedding DNS, Docker socket access, localhost bind and browser tab access remain blocked in this managed shell. Treat container, browser and live dense checks as open. The Submission Guide prints a 13 September deadline without a year; follow the cohort's actual deadline.

## 3. Working rules for this ledger

1. Before coding, choose the next open task on the critical path. Record any scope change in the decision log below and, if substantive, in the PRD revision log.
2. After coding, run the task's proof command or review its artifact. Add exact path, command, date and result to the session log. A source file alone is not proof of runtime success.
3. Never place `.env`, keys, private customer data, generated large indexes or raw model traces in Git. Both workspace and app `.gitignore` files exclude `.env`.
4. Keep the research architecture and [deployment copy](architecture.md) aligned when a decision changes. Update contracts, APIs, UI and evaluation tasks affected by the change.
5. Preserve a working end-to-end path. If a complex agent, reranker or graph feature delays A9, keep a safe deterministic/human fallback and measure the optional feature later.
6. Keep the visible 80-ticket validation set separate from routine development tuning. Never use a hidden assessment set for development. Report actual file size at runtime; the pack has a 100-versus-120 hidden-set inconsistency.
7. Do not claim real first-contact resolution, CSAT or first-response-time improvement from offline data. Record proxies separately from observed live outcomes.

## 4. Critical path and release gates

```text
G0 Repository + reproducible startup
  → G1 Four-channel normalization + persistent terminal-state harness
  → G2 Approved KB + resolvable passages
  → G3 ML classification + deterministic routing
  → G4 Grounded draft + blocking validation + human handoff
  → G5 Full unattended run + automatic metrics + one-command tests
  → G6 React workflows + security/observability + deployment rehearsal
  → G7 Report, video, workbooks and final archive
```

**Gate rule:** A gate is complete only when its test artifact exists. A failed gate gets an issue, cause, correction and retest result. The first functional vertical slice may escalate every ticket safely while later answer components are being built; it must never pretend an escalation is a resolved answer.

## 5. Task checklist

### P0 — Repository, reproducibility and clean startup (G0)

The Submission Guide requires top-level `README.md`, pinned `requirements.txt`, `.env.example`, `src/`, `prompts/`, `tests/`, `evaluation/`, `docs/`, `data/` and `.github/workflows/`. These paths are now present under `CloudServe_App/`; `backend/` contains only the Dockerfile. React remains in `frontend/`.

| Done | ID | Task | Proof / completion condition |
|---|---|---|---|
| [x] | P0-01 | Choose final repository root and align prescribed top-level paths without duplicating the backend implementation. | Tree review against Submission Guide; imports and Docker paths updated. |
| [x] | P0-02 | Pin backend dependencies and commit frontend lockfile. | Fresh environment installs exact resolved versions. |
| [x] | P0-03 | Complete `.env.example` for every required variable; add configuration validation and safe defaults. | App starts with documented config; missing secret produces clear error or safe fallback. |
| [ ] | P0-04 | Add one-command development startup, batch run and tests to README. | Commands copied literally into a clean directory succeed. |
| [x] | P0-05 | Add CI for syntax, unit/contract/integration checks and secret scan. | CI workflow run ID and passing log. |
| [ ] | P0-06 | Verify FastAPI ↔ Nginx ↔ React health path in a built container stack. | `GET /api/health` returns `ok`; browser screenshot or command output saved. |
| [x] | P0-07 | Run a clean-checkout rehearsal on another directory/machine. | Rehearsal log with OS, commands, versions and result. |
| [x] | P0-08 | Add repository-level coding-agent instructions and a mechanical architecture/dependency check. | Fresh session can follow task ID → proof → ledger update; CI rejects forbidden imports or secret exposure. |

### P1 — Discovery, requirements and traceability (G0 prerequisite)

| Done | ID | Task | Proof / completion condition |
|---|---|---|---|
| [x] | P1-01 | Convert interview and dataset findings into the student's own business and technical problem statements. | Discovery workbook with cited finding IDs and explicit assumptions. |
| [x] | P1-02 | Complete PRD v1: functional requirements, nonfunctional targets, protected cases and exclusions. | Requirement IDs trace to evidence and a test or metric. |
| [x] | P1-03 | Document architecture alternatives, six-agent rationale, Azure model choices and why graph is conditional. | ADRs and PRD design section reviewed. |
| [x] | P1-04 | Build a requirement-to-code-to-test traceability matrix, including A1–A12. | Every acceptance criterion maps to planned owner, file and proof. |
| [ ] | P1-05 | Start effort log now, with actual hours by task/day; maintain throughout project. | Dated entries, not reconstructed estimates. |

### P2 — Contracts, persistence and first unattended spine (G1)

| Done | ID | Task | Proof / completion condition |
|---|---|---|---|
| [x] | P2-01 | Implement `NormalizedTicket`, event envelope, `ClassificationResult`, `EvidenceBundle`, `RoutingDecision`, `DraftAnswer`, `VerificationReport`, `ValidationResult`, `EscalationPacket`, `FinalResult`. | Pydantic/JSON Schema output; valid/invalid fixture tests. |
| [x] | P2-02 | Implement source-side contracts: `SourceRecord`, work item, canonical document, chunk, index manifest, lineage and quarantine. | Versioned schema files and round-trip tests. |
| [x] | P2-03 | Normalize email, chat, documentation comment and forum tickets while preserving channel and original text. | One fixture per channel plus missing/empty/unicode cases. |
| [ ] | P2-04 | Create trusted ticket/event/trace IDs, append-only state transitions and persistent store. | Duplicate/replay tests; no agent-minted trusted IDs. |
| [ ] | P2-05 | Implement idempotency and outbox/delivery intent; terminal state is exactly one of `sent` or `escalated`. | Same key/payload repeats result; conflicting payload gets 409; no duplicate send. |
| [x] | P2-06 | Implement batch CLI taking arbitrary `--input` and `--output` paths and any compatible ticket count. | One command processes a mixed fixture unattended and writes one result per input. |
| [x] | P2-07 | Add persistent decision and run manifest (model, prompt, KB, policy, schema versions). | Input IDs, terminal IDs and decision IDs reconcile 100%. |
| [x] | P2-08 | Implement the first small full-path harness and explicit state-transition/stop-condition tests. | Mixed fixture completes unattended; each input has one terminal output and decision event. |

### P3 — Governed knowledge ingestion and publication (G2)

| Done | ID | Task | Proof / completion condition |
|---|---|---|---|
| [x] | P3-01 | Inventory the 29 articles with stable source ID, owner, version/hash and approved authority. | Source manifest reconciles to supplied corpus; no reference answer indexed. |
| [x] | P3-02 | Parse supplied JSON into canonical documents with section/step boundaries and exact offsets. | Sampled fidelity review; original text reconstructable. |
| [x] | P3-03 | Add Source Intake Agent for uncertain/failed formats only; safe parser catalog or quarantine. | Unknown/corrupt/unsafe fixtures are quarantined; no arbitrary fetch. |
| [x] | P3-04 | Add Knowledge Steward Agent for missing steps, duplicates, conflicting sources and candidate taxonomy links. | Human-review examples with source spans and reasons. |
| [x] | P3-05 | Add HITL knowledge certification and versioned approval record; agent cannot publish. | Changed/conflicting source requires approval; rejected source absent from index. |
| [x] | P3-06 | Implement chunking with stable passage ID, parent section, source version, offsets and inherited permissions. | Exact passage lookup and full procedure-step integrity tests. |
| [x] | P3-07 | Implement idempotent ingestion, checkpoint/retry, quarantine and atomic index publication. | Duplicate source/version creates no duplicates; interrupted job resumes; old index remains usable. |

### P4 — Retrieval and evidence gates (G2 → G3)

| Done | ID | Task | Proof / completion condition |
|---|---|---|---|
| [ ] | P4-01 | Integrate Azure ada-002 embeddings for chunks and queries; record deployment and dimensions in index manifest. | Index/query both 1536-dimensional; version mismatch rejected. |
| [ ] | P4-02 | Build lexical baseline, dense candidate and hybrid candidate over the same approved snapshot. | Search returns ranked real passage IDs, scores and source locators. |
| [ ] | P4-03 | Enforce tenant/role/source permissions before any passage reaches an agent prompt or cache. | Unauthorized retrieval fixture returns zero disallowed passages. |
| [ ] | P4-04 | Label passage-level relevance and no-answer cases; compare Recall@1/3/5, MRR and no-answer specificity. | Versioned gold file, evaluation script and results by intent/language fluency. |
| [ ] | P4-05 | Choose chunk size, hybrid weighting, optional reranker and relevance threshold from measured tradeoffs. | Decision record with quality, p95 latency and cost; weak evidence abstains. |
| [x] | P4-06 | Implement Evidence Agent with query planning, maximum two searches and structured `EvidenceBundle`. | Query-rewrite gain/harm measured; insufficient/tool-error becomes escalation. |

### P5 — Classification ML, policy and routing (G3)

| Done | ID | Task | Proof / completion condition |
|---|---|---|---|
| [x] | P5-01 | Split development tickets by near-duplicate group; reserve calibration set, keep 80-ticket validation separate. | Split manifest, label counts and leakage check. |
| [x] | P5-02 | Train/evaluate conventional intent and urgency baselines, including `unknown` fallback and alternatives. | Per-class precision/recall, macro F1 and confusion matrix. |
| [x] | P5-03 | Calibrate numeric probabilities and version model/calibrator. | Reliability plot, ECE/Brier; no raw similarity presented as probability. |
| [x] | P5-04 | Implement versioned business rules: protected intents, `must_not_auto_respond`, priority, evidence eligibility, forbidden commitments, kill switch and effective dates. | Rule fixtures, conflict/priority tests, human approval record. |
| [x] | P5-05 | Implement deterministic `QueryPlan` and route selection (`rule`, approved-document RAG, human). | Same input + versions yields same decision/reason; unsupported paths fall back to human. |
| [ ] | P5-06 | Add conditional Triage Agent for low confidence/conflicting signals only. | Incremental gain versus ML alone; protected cases never overridden. |
| [x] | P5-07 | Select thresholds from risk–coverage analysis, including zero protected false-auto on test cases. | Versioned threshold rationale and regression tests. |

### P6 — Grounded answer, verification and HITL handoff (G4)

| Done | ID | Task | Proof / completion condition |
|---|---|---|---|
| [ ] | P6-01 | Version prompts and tool allowlists for all six agents; specify per-agent input/output, timeout, call budget and failure behavior. | Prompt files, contract tests and trace spans; no unbounded loops. |
| [ ] | P6-02 | Implement Answer Agent using only authorized `EvidenceBundle` and claim-level source IDs. | `must_mention` coverage and fabricated-citation tests. |
| [ ] | P6-03 | Implement Verification Agent for every generated draft; compare GPT-4o versus conditional o3-mini/NLI on human-labelled claims. | Unsafe-claim recall, false-block rate, latency and cost comparison. |
| [x] | P6-04 | Implement independent deterministic validator for schema, exact citation/version, permission, PII/secrets and forbidden commitments. | Engineered unsafe response is blocked; findings recorded even on pass. |
| [x] | P6-05 | Implement release gateway with policy + evidence + verification + validator gates. | Only validated eligible answers reach `sent`; failure becomes logged escalation. |
| [ ] | P6-06 | Build `EscalationPacket` with summary, route/priority, known/unknown, source links, reasons and next verification step. | Support reviewer can act without rereading full trace; no unvalidated draft presented as fact. |
| [ ] | P6-07 | Add human resolution and correction events; reviewed lessons feed KB/rules only through approval. | Auditable HITL action; prior event preserved. |
| [ ] | P6-08 | Implement typed `ContextEnvelope` and central context assembler for every agent call. | Trusted/untrusted separation, permission/version checks, token budget and truncation/abstention fixtures pass. |

### P7 — API, React UI and explainability (G4 → G6)

| Done | ID | Task | Proof / completion condition |
|---|---|---|---|
| [ ] | P7-01 | Implement `POST /v1/tickets`, `GET /v1/tickets/{id}` and restricted decision endpoint. | OpenAPI contract; auth, idempotency, status and object authorization tests. |
| [ ] | P7-02 | Implement escalation queue/detail/resolve and customer/agent feedback endpoints. | Role checks, pagination, idempotent resolution and audit events. |
| [ ] | P7-03 | Implement knowledge jobs/source/index endpoints and operator approval actions. | Quarantine/publish status visible; no unauthorized source text. |
| [ ] | P7-04 | Build React customer view: ticket status, automated answer with exact citations, or honest human-handoff state. | Browser test for sent and escalated states; no invented SLA promise. |
| [ ] | P7-05 | Build React support desk: queue, ticket, evidence, uncertainty, guardrail reason and human actions. | Handoff information readable and edits audited. |
| [ ] | P7-06 | Build React knowledge operations: source review, lineage, quarantine and active index. | Operator can trace cited passage to approved version; cannot bypass approval. |
| [ ] | P7-07 | Build React operations/evaluation: volume, safe coverage, retrieval, citations, guardrails, latency and decision reconciliation. | Totals match metrics report; offline metrics clearly labelled. |
| [ ] | P7-08 | Add per-ticket explanation timeline and score definitions; check keyboard/status accessibility. | Each shown score names its meaning and calibration status; no opaque combined trust score. |

### P8 — Gold truth, automatic metrics and full-run evaluation (G5)

| Done | ID | Task | Proof / completion condition |
|---|---|---|---|
| [ ] | P8-01 | Freeze corpus/split manifests and create annotation guide for route, passage, required/forbidden claims and claim support. | Versioned guide and reviewer decisions; source hashes recorded. |
| [ ] | P8-02 | Label a stratified development subset for passage and no-answer relevance; include protected and non-fluent cases. | Human-reviewed gold with exact supporting spans; agreement reported. |
| [ ] | P8-03 | Review generated answer claims and escalation packets with two assessors where required by evaluation framework. | Disagreement log and adjudicated labels; counts and sampling method reported. |
| [x] | P8-04 | Build adversarial/operational fixtures: prompt injection, false citations, private data, malformed input, empty body, no hit, timeout, rate limit, outage. | Separate safety-suite report; protected false-auto count zero. |
| [x] | P8-05 | Implement automatic metrics report: volume, auto/escalated/blocked, business proxies, per-class ML, retrieval hit, median/p95 latency, logs, guardrail types, PII detections. | One batch command writes report without postprocessing. |
| [x] | P8-06 | Run full 500-ticket development set unattended; then infrequent 80-ticket validation check. | Run manifests, complete results, 100% terminal/log reconciliation and error analysis. |
| [x] | P8-07 | Measure project targets honestly: ≥85% classification precision, ≤5% hallucination, ≥95% citation accuracy, p95 <3 s, calibration/fairness/availability where measurable. | Numerators, denominators, reviewer sample and unknown live outcomes explicit. |
| [x] | P8-08 | Run arbitrary-path unseen-file rehearsal with changed ticket count/order and provider disabled. | One-command completion, no skipped ticket, safe escalation on outage. |
| [ ] | P8-09 | Evaluate bounded loop behavior and human-approved improvement cycle. | Retry/stop counts, no loop violations, candidate-versus-baseline regression report and approval record. |

### P9 — Reliability, security, deployment and governance (G6)

| Done | ID | Task | Proof / completion condition |
|---|---|---|---|
| [ ] | P9-01 | Add structured audit and traces for every stage, model/prompt/KB/policy version, reason, timing, cost and terminal state. | Trace-to-ticket reconstruction without raw text/keys in general metrics. |
| [ ] | P9-02 | Add bounded retries, rate-limit backoff, timeouts, concurrency limits and failure-to-escalation behavior. | Fault-injection run completes with all IDs reconciled. |
| [ ] | P9-03 | Enforce API identity, tenant/role/object authorization, source permissions, cache partitioning and secrets handling. | Cross-tenant negative tests; secret scan passes. |
| [ ] | P9-04 | Add liveness/readiness, logs/metrics, alerts and operator runbook for outage, bad index, policy rollback and PII incident. | Induced failure fires alert and documented recovery steps work. |
| [ ] | P9-05 | Run performance and cost profile across answer and escalation paths; benchmark conditional o3-mini use. | p50/p95, token/cost and timeout rates by stage; decision on model routing. |
| [ ] | P9-06 | Verify container build, React production build, clean checkout, one-command tests and CI. | Recorded commands/logs on a fresh machine or clean directory. |
| [x] | P9-07 | Complete governance/risk register, fairness audit and incident procedure. | Risk owner, trigger, mitigation, residual risk and subgroup counts. |

### P10 — Workbooks, report, video and final package (G7)

| Done | ID | Task | Proof / completion condition |
|---|---|---|---|
| [ ] | P10-01 | Complete all five stage workbooks: discovery, PRD, prompt library, sprint plan and PRD revision log. | Filled documents, not templates; requirement revision is substantive. |
| [ ] | P10-02 | Keep task-level effort log current and export final PDF. | Dated actual hours and stage totals. |
| [ ] | P10-03 | Write 20–30 page report in prescribed order, with methods/limits beside every performance claim. | Single PDF; numbered figures/tables and AI-tool-use declaration. |
| [ ] | P10-04 | Record 18–22 minute video with ≥7 minutes live demo: successful answer, escalation, guardrail block, full unattended-run evidence. | Legible MP4, audible sound, required on-camera introduction/close. |
| [ ] | P10-05 | Rehearse exact assessment procedure from a fresh clone; review credentials and attribution/history. | Checklist with every A1–A12 result and no keys in repository/history. |
| [ ] | P10-06 | Create required archive with exactly `01_Video`, `02_Report`, `03_Workbooks`, `04_Source_Code` at top level. | Archive listing, exact name format and all four parts present. |

## 6. A1–A12 acceptance matrix — current state

| Criterion | Required proof | Linked tasks | State |
|---|---|---|---|
| A1 clean checkout | README commands succeed in fresh directory | P0-01–07, P9-06 | Open |
| A2 four channels | One normalized ticket from each channel | P2-03 | Open |
| A3 intent, urgency, numeric confidence | Every result carries both labels and `[0,1]` scores | P5-01–03 | Local pass: calibrated on held-out split (intent ECE 0.002) |
| A4 real retrieval passages | Search IDs resolve to exact supplied corpus text | P3-01–07, P4-01–05 | Open |
| A5 deterministic threshold routing | Same input/version yields same route/reason | P5-04–07 | Local pass: thresholds from recorded risk–coverage selection; repeat test |
| A6 resolvable citations | Draft claims cite passages actually retrieved | P4-06, P6-02, P6-04 | Open |
| A7 blocking guardrail | Engineered unsafe response never sent | P6-03–05, P8-04 | Local pass: instruction-override ticket and injected unsafe drafts blocked |
| A8 persistent decision log | Logs and ticket totals reconcile | P2-04–07, P9-01 | Local pass: Governance-format `decision` event per ticket; P9-01 cost/timing open |
| A9 unattended full set | Arbitrary-path run finishes with no missing IDs | P2-06, P8-06, P8-08 | Open |
| A10 automatic metrics | Report emitted by same run | P8-05–07 | Open |
| A11 failure handling | No hit, timeout, outage, rate limit, malformed input all terminal | P2-03, P6-06, P8-04, P9-02 | Local pass; live provider and persistence recovery open |
| A12 one-command tests | Documented command passes from clean checkout | P0-04–05, P9-06 | Open |

## 7. Evidence artifact register

Create these as the work proceeds. Record actual filenames/run IDs in the session log; proposed paths below are organizational targets.

| Evidence class | Target path | Must contain |
|---|---|---|
| Decisions and requirements | `docs/adr/`, `docs/prd/`, `docs/traceability.md` | Date, owner, alternatives, rationale, affected tests |
| Prompt specifications | `prompts/` | Agent, version, inputs/outputs, allowed tools, change log |
| Schema and contract tests | `src/cloudserve/contracts/`, `tests/contracts/` | JSON Schema, examples, invalid fixtures and compatibility checks |
| Data and KB manifests | `data/manifests/` | Source/index hashes, model/chunker/version, permissions |
| Gold annotations | `evaluation/gold/` | Annotation guide, reviewer IDs, disagreement resolution, frozen corpus |
| Batch run | `evaluation/reports/<run_id>/` | Result per input, decision log, metrics, run manifest and errors |
| Security/reliability | `docs/runbooks/`, `tests/faults/` | Fault injection, recovery, secret/permission scan |
| UI proof | `docs/ui/` | Screenshots or browser test outputs for customer, agent, knowledge and ops |
| Submission | `submission/` outside source repository if large | Final video, PDF report, workbooks/effort log, archive listing |

The supplied 200 senior-agent responses are content references and `must_mention`/`must_not_claim` hints, **not** approved retrieval passages or an exact-match answer key. The 80 visible validation tickets are not the hidden assessment set.

## 8. Session handoff log — update after every work session

**Latest session: 15 November 2026**

- **Completed:** research and canonical architecture; Azure model smoke test reported successful by user; `CloudServe_App/` scaffold with FastAPI health source, React overview shell, Nginx/Compose files and architecture-to-code map; static Python/JSON/YAML checks.
- **Not completed:** dependency install, React production build, container run, clean-checkout rehearsal, any ticket/KB/agent implementation or quantitative evaluation.
- **Main finding:** required submission repository paths differ from current scaffold; P0-01 is first structural task.
- **Next action:** implement P0-01 and P0-02, then verify P0-06/P0-07 in a network-enabled environment. Begin P2 contracts and full-run spine immediately after.
- **Environment note:** workspace had no Docker Compose plugin and lacked cached frontend type packages; this is why build/runtime proof is absent.

**Planning audit: 16 November 2026**

- **Completed:** [harness, loop and context audit](../../Research/12_harness_loop_context_audit.md) against the current architecture and repository; four explicit implementation tasks added (P0-08, P2-08, P6-08, P8-09).
- **Finding:** design specifies bounded agent calls, handoffs, feedback and evidence rules, but no executable build harness, runtime loop or context assembler exists yet. Six-agent scope remains unchanged.
- **Next action:** P0-01 remains the first implementation task when work resumes.

### Future session entry template

```text
Date / session:
Task IDs attempted:
Changed files:
Commands/tests run and exact results:
Evidence artifact paths or run IDs:
Decisions or scope changes:
Blocked items and reason:
Next task IDs:
```

## 9. Decision and change log

| Date | Decision | Reason | Follow-up |
|---|---|---|---|
| 15 Nov 2026 | Two pipelines, six specialized agent roles; bounded calls and deterministic release. | Separate knowledge governance from ticket response; keep auditable responsibility boundaries. | Implement and evaluate conditional invocation. |
| 15 Nov 2026 | Azure GPT-4o, o3-mini and ada-002 selected; basic connectivity user-confirmed. | Existing deployments available; keep provider adapter isolated. | Benchmark quality, cost, latency and quotas. |
| 15 Nov 2026 | React + TypeScript UI, FastAPI API, Docker/Nginx scaffold. | Four audiences need distinct views; browser must not hold model keys. | Build and test actual workflows. |
| 15 Nov 2026 | GraphRAG/ontology/SQL kept conditional. | Current 29-article corpus lacks a verified graph task and transactional source. | Revisit only with labelled use case and evidence of value. |

## 10. Final release rule

Do not mark the project complete because the diagram, six agents, UI shell or demo looks finished. Release readiness requires: **A1–A12 pass from a clean checkout, every input ID reconciled to a terminal result and decision log, supported citations and blocking guardrails, honest measured metrics, completed governance evidence, and the four-part submission package.**

## 11. Build session — 16 November 2026

- Implemented the prescribed root layout, FastAPI/SQLite ticket flow, four-channel normalization, ML intent/urgency/answerability, deterministic routing, six bounded role classes, approved passage catalog, extractive and optional GPT-4o answer paths, citations, human handoff, React workspace, and offline harness.
- Added optional Azure ada-002 index build and lexical-plus-dense reranking. Live embedding index build is untested in this sandbox; active manifest reports lexical until built. o3-mini, source publication approval, RBAC, graph retrieval and production monitoring are still open.
- `PYTHONPATH=src:. .../bin/python -m pytest -q`: 7 passed. `PYTHONPATH=src .../bin/python -m evaluation.harness` processed 500 development and 80 visible validation tickets with 100% terminal reconciliation. Latest runs: 46/500 and 3/80 auto answers respectively.
- Two false auto answers in the first validation run led to policy and evidence changes; the visible validation set is now tuning data. A fresh, human reviewed holdout is required for independent quality claims.
- ASGI smoke passed for `POST /v1/tickets` and `GET /v1/tickets/{id}/decision`, including typed escalation packet and terminal event.
- `npm install` failed with registry DNS resolution and a localhost server bind returned permission denied. React source, production build, browser screenshot, Docker Compose and Azure live path are unverified, not passing.
- Next: install frontend dependencies in a network-enabled environment; run browser and container checks; create a separate gold set for claim support, exact citations and no-answer cases; add auth/tenant isolation and human resolution endpoints before external exposure.

### Startup attempt — 16 November 2026

- React production build passed with TypeScript and Vite 6.4.3 using a temporary link to locally cached dependencies; output is `frontend/dist/`. Temporary dependency links were removed afterward. `npm install` still requires registry access for a reproducible install and lockfile.
- Backend Uvicorn startup reached application initialization, then localhost bind returned `[Errno 1] operation not permitted` in the managed shell. No live backend or frontend server is running from this session.
- Browser policy rejected opening the built `file://` preview because only HTTP(S) protocols are allowed and expressly prohibited an alternate browser route. No visual browser check was performed.
- Backend regression: `7 passed in 2.61s`. Direct ASGI integration: ticket POST, decision GET, handoff packet and terminal event passed.

### Task status clarification — 16 November 2026

The first **local prototype vertical slice** is complete: P2-06/P2-08 (batch spine) and P8-05/P8-06 (automatic metrics and full supplied-set runs). Seven regression tests, direct ASGI ticket/decision integration, and React production compilation passed. A1–A12 are not all accepted: fresh checkout, real browser demo confirmation, independent gold, full failure suite, auth/tenant isolation, container/CI run and final submission artifacts remain open. Features implemented as partial slices (ML, six role classes, lexical retrieval, API, UI) are not marked complete where their task row requires calibration, HITL approval, security or browser evidence.

### Safety gate session — 16 November 2026

P8-04 completed for the local prototype. [A11 failure handling](A11_failure_handling.md) records 13 adversarial/operational cases, the 20-test full regression, full 500/80 batch reconciliation and limits. The service now fails closed on unexpected model/tool exceptions; malformed channel and empty request routing are deterministic. P9-02 remains open for live 429 retry/backoff, concurrency and outage recovery.

### Gold seed session — 16 November 2026

P8-01 is **partially implemented**: `evaluation/gold/manifest_v1.json` freezes source hashes and 29 article versions; `supplied_labels_v1.jsonl` contains 580 source-provided labels; `review_queue_v1.jsonl` selects 120 deduplicated development tickets across 22 intents, four channels, two routes and both fluency groups. The annotation guide, independent reviewer templates, frozen-hash scorer and reviewer comparison validator are implemented. **No human reviewer has approved a passage or claim yet (0/120)**, so P8-01/P8-02 remain open and the package is explicitly a seed, not final adjudicated gold.

The seed scorer ran against the latest 500/80 outputs. Development: route accuracy 0.4700, safe-auto recall 0.1479, urgency accuracy 0.6900, zero labelled unsafe autos. Visible validation: route accuracy 0.4375, safe-auto recall 0.0625, urgency accuracy 0.4375, zero labelled unsafe autos. These sets were used in development/tuning; report as diagnostic baselines only. The full regression now passes 24 tests. Next: two independent human reviews, disagreement adjudication, a new frozen v2 gold, and an untouched holdout before quality claims.

### HITL resolution session — 16 November 2026

Implemented a local human-resolution slice for P6-07/P7-02: typed `HumanResolution`, transactional SQLite write, idempotent replay, conflict rejection, `human_resolved` audit event, pending-only queue, metrics, FastAPI route and React support form. The original terminal result remains immutable and no customer message is sent. Full regression: **27 passed**; API lifecycle test passed; React production build passed with Vite 7.3.8. [HITL resolution guide](HITL_resolution.md) has the UI/API test. P6-07 and P7-02 remain open because authenticated reviewer identity, role/object authorization, correction approval and production browser checks are not yet complete.

### Governed knowledge pipeline session — 16 November 2026

Implemented the local P3-05 approval gate and partial P3-01–04/P3-06–07/P7-03/P7-06 slices. The 29-article baseline now has revisioned active indexing, exact passage offsets and source-version citation lookup. Existing-article revisions pass Source Intake and Knowledge Steward checks; unsafe or unknown sources are quarantined. Human review notes are required before atomic publication, and a stale approval cannot replace a newer source. The React Knowledge view includes catalog, lineage, version history, citing-ticket links and review actions. See [knowledge pipeline](knowledge_pipeline.md) for flow and limits.

Backend suite: **31 passed**; React TypeScript/Vite production build passed. The 500/80 supplied batch outcomes remained unchanged with complete terminal reconciliation. P3-05 is checked for local lifecycle behavior; role authentication and tenant permissions remain an external deployment gate. Other P3/P7 tasks remain open because their full proof conditions include additional formats, checkpointing, permission inheritance or browser/authorization checks.

### Submission critical path session — 16 November 2026

Completed P2-03, P2-07 and P8-08. Normalized events now preserve original channel, subject and Unicode body in the private ticket database. The batch run manifest records input SHA-256, schema/model/prompt/KB/policy versions and exact input/terminal/decision ID lists; reconciliation checks IDs and uniqueness, not just counts. An arbitrary-path six-ticket file with changed count/order, missing ID, malformed entry, four channels and Azure credentials disabled completed unattended. Protected and empty requests escalated. `tests/test_rehearsal.py` contains the acceptance fixtures. Full backend suite: **33 passed**. The manifest's prompt labels identify the prototype extractive/Azure paths; they are not a substitute for versioned agent prompt files.

P0-01 repository-layout review passed: prescribed top-level paths exist under `CloudServe_App/`, Python imports resolve from `src/`, and the backend Dockerfile copies `src/` and `data/supplied/` from this root. Added `scripts/test.sh`, `scripts/batch.sh`, `scripts/dev.sh`; the first two ran successfully. A source-only copy in `/private/tmp/cloudserve-rehearsal.Xt7YOc` passed offline `npm ci`, 33 tests, React build, and an 80-ticket batch with complete reconciliation. This is **partial P0-04/P0-07 evidence**: Python reused the existing interpreter because a fresh offline `uv` cache initialization was denied by the sandbox, and a live dev/browser check was not possible while port 8001 was occupied/inaccessible. Docker Compose is unavailable in this shell (`docker: unknown command: docker compose`).

P0-03 passed locally: `.env.example` lists Azure chat/embedding names and safe extractive default; `tests/test_config.py` confirms an unconfigured extractive run works and missing Azure secrets raise clear `ModelUnavailable` errors without network calls. P0-08 passed locally: top-level `AGENTS.md`, `scripts/architecture_check.py`, CI invocation and negative fixtures reject forbidden imports and credential patterns. The full suite and React build now pass with **37 tests**. A hosted CI run ID remains open under P0-05.

P4-02 is partially implemented: `search_candidates()` now exposes lexical, dense and hybrid rankings over the active approved passages, with source version and exact offsets. `tests/test_retrieval_candidates.py` verifies lexical resolution and dense/hybrid behavior with injected 1536-dimensional vectors; full suite **39 passed**, React build passed. Live Azure index publication failed at DNS resolution (`ModelUnavailable: embedding request failed: URLError`), so real dense recall/latency comparisons and P4-01/P4-02 acceptance remain open. The production release path continues to use its independent evidence threshold and safe lexical fallback.

P2-01/P2-02 contract schemas now exist as 17 versioned JSON Schema files in `docs/schemas/`, generated by `scripts/export_schemas.py` from Pydantic types in `src/cloudserve/contracts.py`. Valid round trips and invalid handoff/source fixtures pass in `tests/test_contract_schemas.py`. Full suite **41 passed** with React build. Existing prototype calls retain their earlier short contract names; migration to the new explicit envelope names and per-agent enforcement remains open under P6-01/P6-08.

The [submission readiness guide](submission_readiness.md) now tracks required report, video, workbooks, effort log and source archive. `scripts/demo_guardrail.py` passed: an injected unsupported refund promise was blocked, terminal state was `escalated`, and the customer message contained no promise. The guide provides a timed live-demo sequence. Actual dated effort hours and on-camera video must come from the student; they cannot be reconstructed or generated from code evidence.

P1-04 is complete: [acceptance traceability](traceability.md) maps each A1–A12 criterion to a component owner, implementation files, executable proof and current limitation. This matrix is for assessment rehearsal; it does not replace the stricter task-level checks above.

An isolated two-database repeat test now shows the same ticket and source/policy versions yield identical classification, routing decision and terminal state. `scripts/test.sh`: **42 passed** plus React build. This gives local A5 evidence independent of idempotent replay.

The authored [problem statement](problem_statement.md) records F01–F06 evidence IDs and FDE assumptions. [PRD v1](PRD_v1.md) defines FR01–FR12 and NFR01–NFR07 with source findings, tests/metrics, protected cases and exclusions, so P1-02 is checked. P1-01 remains open until the actual discovery workbook is filled.

P1-03 is now checked after [architecture decision review](architecture_decision_review.md) compared the modular deployment, governed KB, six conditional roles, deterministic routing, Azure model choices and conditional graph against alternatives and current proof. PRD v1 links that reviewed decision. The live dense comparison and agent-quality experiments remain explicit revisit triggers, not claimed results.

P8-07 is checked for honest measurement/reporting: `evaluation/quality_report.py` writes exact denominators, per-class intent precision, ECE/Brier, protected false-auto count, citation resolvability, local p95 and language-fluency group counts. It explicitly sets hallucination, semantic citation accuracy and availability to unknown with zero human/live observations. [Evaluation snapshot](evaluation_snapshot.md) records the 500/80 diagnostic results and limitations. Full backend suite **43 passed**; React build passed. None of the unavailable target metrics are claimed achieved.

P0-07 source-checkout rehearsal passed in a local Git clone; [rehearsal log](rehearsal_log.md) records OS, tool versions, commands, 43 tests, React build and 80/80 batch reconciliation. Python dependencies were reused from an existing interpreter, so P0-04/P9-06 and A1/A12 fresh-environment proof remain open. The repository now has an initial local commit, with no remote configured; generated artifacts, runtime databases and `.env` are ignored.

P0-02 is partially improved: `requirements.txt` now pins all 26 packages in the tested Python 3.14.6 dependency closure, and `pyproject.toml` separates runtime from dev requirements. A local metadata check verified every pin equals the installed version. Fresh Python 3.12 install remains unverified, so P0-02 stays open. The frontend lockfile did pass `npm ci --offline` in the clone.

P3-01/P3-02 completed: `data/manifests/source_manifest_v1.json` inventories all 29 approved documents with stable IDs, owner, authority, SHA-256, short source versions and 145 passage counts. `canonicalize_documents()` retains original text plus 145 section spans and 116 numbered-step spans. `tests/test_source_manifest.py` verifies every offset against the original source and confirms the active index contains exactly the 29 supplied document IDs, not reference-answer IDs. Full suite **44 passed**, React build passed.

P3-06 completed: each passage now carries inherited source permissions, section, source version and exact offsets. An attempted permission change during source staging is quarantined until an authorization design exists. Tests verify every numbered resolution step remains inside its parent Resolution passage and explicit source permissions propagate to all chunks. `scripts/test.sh`: **45 passed** plus React build. Tenant/role enforcement at retrieval remains separately open under P4-03/P9-03.

P3-07 completed for the local SQLite pipeline: `tests/test_knowledge_pipeline.py::test_job_checkpoint_resume_and_atomic_visibility` shows duplicate staging returns one job, a reviewed job survives service restart, the old approved index stays readable until publication, and the new revision appears only after the atomic publish. Quarantine and stale-base tests remain green. `scripts/test.sh`: **46 passed** plus React build. Distributed worker retry and multi-tenant source enforcement are separate production extensions.

P3-03 completed for the supplied JSON source format: known complete JSON takes the deterministic approved parser path; Source Intake is invoked only for uncertain/incomplete or unsupported formats and can only recommend the approved JSON parser or quarantine. Unknown PDF and incomplete owner fixtures are quarantined, as are unsafe source-text fixtures. No arbitrary fetch tool exists. `scripts/test.sh`: **47 passed** plus React build. PDF parsing itself is outside the current capstone corpus.

P3-04 completed: Knowledge Steward returns warnings for missing resolution steps, duplicate content and conflicting article titles, plus exact review spans and up to three candidate same-category taxonomy links. `tests/test_knowledge_pipeline.py::test_steward_flags_duplicate_conflict_and_candidate_links` exercises all of these. The review job exposes warnings/spans to the human; the agent cannot publish. `scripts/test.sh`: **48 passed** plus React build.

P4-06 completed: Evidence Agent now returns typed `QueryPlan` and `EvidenceBundle` with source revision, searches, queries, sufficiency and reason. `evaluation/query_rewrite_eval.py` measured document-label candidate gain/harm and bounded search on both supplied sets; [diagnostic summary](evidence_rewrite_snapshot.md) states its in-sample and passage-gold limits. Insufficient evidence and tool errors still escalate. `scripts/test.sh`: **50 passed** plus React build, and the full diagnostic found zero two-search budget violations.

Fresh full batches after the typed Evidence Agent change processed **500 development** (46 sent, 454 escalated) and **80 visible validation** (3 sent, 77 escalated) in `evaluation/reports/dev-evidence-v2/` and `validation-evidence-v2/`, each with exact terminal/decision reconciliation. No customer-facing route changed.

### Step 2 session — routing, calibration and policy v2 (16 November 2026)

- **Task IDs:** P5-01, P5-02, P5-03, P5-04, P5-05, P5-07, P6-04 and P6-05 are checked. P5-06 (Triage incremental gain), P6-06 (reviewer usability of packets) and P9-01 (cost/timing in traces) remain open.
- **Finding:** v1 escalated 90.8% of tickets. The answerability gate behind 197 of those wrong escalations has held-out AUC 0.32–0.55, because identical non-protected text carries opposite labels in 40 of 191 groups. 62 of 80 validation bodies duplicate development text. Three v1 regexes were fitted to validation tickets and have been removed. Details: [PRD revision R1](PRD_revision_log.md), F07–F09 in the [problem statement](problem_statement.md).
- **Changed files:** `classifier.py` (train-split fit, temperature calibration, novelty similarity), `policy.py` + `policy_v2.json` (versioned rules R-00–R-07, kill switch, thresholds), `guardrails.py` (new; pass/fail records), `agents.py` (Evidence scope, full cited extractive answer, exact-span verifier, Triage options), `service.py` (flow, Governance decision record, packet next steps), `api/routes/policy.py` (active policy, kill switch), `evaluation/threshold_selection.py`, `evaluation/fixtures/out_of_scope_v1.json`, `evaluation/harness.py` (business/governance/fairness/calibration blocks), `tests/test_policy_v2.py`, React overview kill-switch panel and demo samples.
- **Proof:** `CLOUDSERVE_PYTHON=… ./scripts/test.sh` gave architecture check OK, **64 passed**, React build OK. `evaluation.threshold_selection` used the calibration split only: 1,680 configurations, chosen intent 0.90 / similarity 0.35 / document 0.30 / evidence 0.06, coverage 79.6%, wrong article 2.4%, protected 0, out-of-scope 0 (`data/manifests/threshold_selection_v1.json`). Batch `development-policy-v2`: 364 sent / 136 escalated, safe-auto recall 0.865, protected false-auto 0, wrong-article 1.9% of sent, reconciliation true. Batch `validation-policy-v2`: 55 / 25, recall 0.812, protected 0, wrong-article 1.8%, reconciliation true. Calibration record: `data/manifests/calibration_report_v1.json`.
- **Not met / limits:** the fluency gap is 7.1 points on development (<5 required) and the region gap is 12.7 points. Urgency is 50% on held-out data. 90 dev / 15 validation answers went to label-`escalate` tickets and need human review. Hallucination and semantic citation accuracy remain unmeasured. The visible validation set was run twice under v2 with identical counts; no threshold was changed after it.
- **Next:** commit; fresh-install + CI (P0-02/04/05); live browser demo; dense retrieval for the fluency gap (P4); two-person answer review (P8-02/03); governance register (P9-07); workbooks/report (P10).

### Repository publication and hosted CI (16 November 2026)

- Repository published at https://github.com/tushitdave/cloudserve-fde-capstone after a credential scan. Every key and endpoint value from the private workspace `.env` was checked against full git history, the tracked tree and pending files, and none was found.
- Hosted CI run **43889620478** passed on a fresh `ubuntu-latest` runner with Python 3.12. It ran a pinned `pip install -r requirements.txt` (exact versions installed), the architecture/credential check, **64 passed**, and `npm ci && npm run build`. This closes P0-02 (fresh install of the pinned dependencies) and P0-05 (CI run ID). A clean-checkout run of README `scripts/dev.sh` with a browser check (P0-04/P0-06) and the container build (P9-06) remain open.

### Prompt library, governance and demo script (16 November 2026)

- `prompts/` now holds versioned prompts PR-01–PR-05 with a `registry.json` (agent, model, inputs/outputs, requirement IDs, change log). The Azure prompts are loaded from these files at runtime (`agents.prompt`), and the backend Dockerfile copies `prompts/`. Test `test_prompt_registry_files_exist_and_load`. P6-01 stays open: knowledge-agent and Evidence specifications, per-agent timeouts and trace spans are not yet in the registry.
- **P9-07 checked:** [governance.md](governance.md) holds the decision-log specification, a 9-risk register (likelihood, impact, control with evidence, residual risk, owner), the fairness audit across all Framework segments with counts, the guardrail table, a 6-step incident procedure, the kill-switch table and the declaration. The fluency and region gaps are reported as not meeting the <5-point condition.
- The demo script in [submission_readiness.md](submission_readiness.md) has been rewritten for v2: success, escalation, guardrail, out-of-scope, kill switch, full run and limits.
- `./scripts/test.sh`: **65 passed**, React build OK.

### Workbooks and effort-log draft (16 November 2026, evening)

- **P1-01 checked:** `docs/workbooks/Stage_1_Discovery_Workbook.md` is filled from the transcripts and data. Its four disagreements are settled by counts: answerable 71.4%; escalated-but-answerable 49.1%; non-fluent CSAT 3.04 vs 2.95; enterprise median resolution 369 min.
- Stage 2–5 workbooks drafted in `docs/workbooks/` from the PRD, prompt registry, ledger and revision log. They are rendered to DOCX with `scripts/md_to_html.py` and `textutil`. P10-01 stays open until the student reviews them.
- The effort log is a template with tasks and outputs from the ledger. Hours are blank by design (P1-05/P10-02: student only).
- Correction: entries earlier in this ledger dated "17 November" were written on 16 November and have been corrected.

### Report draft (16 November 2026, evening)

- `docs/report/report.md` holds the 10 prescribed sections, 12 numbered tables and 3 figures, the "should be treated with caution because" statement and the AI-use declaration. Appendices B–D (governance, traceability, evaluation snapshot) are appended at build time.
- `scripts/build_report.sh` renders it with headless Chrome. The output is 32 pages: body pp. 1–20, appendices from p. 21. Every figure in the report traces to `metrics.json`, `threshold_selection_v1.json` or the Stage 1 counts.
- P10-03 stays open until the student reviews and approves the report text.

### Submission staging (16 November 2026, night)

- `scripts/package_submission.sh <Name> <staging> <out>` clones the committed repository as `04_Source_Code`, runs the architecture/credential check and a key-pattern scan, and zips exactly `01_Video`, `02_Report`, `03_Workbooks` and `04_Source_Code`. A dry run with a placeholder video produced `TushitDave_Capstone_Submission.zip` (1.9 MB) with those four folders only.
- Staging lives at `../Submission_Staging/` (outside the repository): the report PDF, five workbook DOCX files and the effort-log template (DOCX + PDF). `01_Video` holds a placeholder until the recording exists.
- README now states prerequisites (Python ≥3.12, Node ≥22) and what the batch command writes.
- **Remaining, student only:** report and workbook review (P10-01, P10-03); effort hours (P1-05, P10-02); video (P10-04); a fresh-clone browser rehearsal (P0-04, P0-06, P10-05); final archive (P10-06). **Deliberately dropped** (stated in the report): dense retrieval measurement (P4-01..05), API authentication (P7-01, P9-03), monitoring (P9-04), o3-mini triage (P5-06), ContextEnvelope (P6-08), Docker Compose rehearsal (P9-06), and the two-person gold review (P8-02/03).
