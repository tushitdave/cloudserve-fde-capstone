# Stage Four: Sprint plan — CloudServe

**How the time actually ran.** This project was carried out in a compressed window, 15–18 November 2026, with heavy AI-assisted implementation, instead of the three-week shape the pack assumes. The plan below keeps the pack's sequence (discovery → requirements → build → gate → revision → governance → submission). The daily record shows what really happened. Estimated hours are planning figures. **Actual hours are recorded only in the effort log, by the student.**

## 1. Section one: capacity

| Period | Hours realistically available | Other commitments | Days you cannot work |
|---|---|---|---|
| 15 Nov (discovery, research, architecture) | _student to fill_ | _student to fill_ | — |
| 16 Nov (build, gate, revision) | _student to fill_ | _student to fill_ | — |
| 17 Nov (governance, workbooks, report) | _student to fill_ | _student to fill_ | — |
| 18 Nov (video, review, submission) | _student to fill_ | _student to fill_ | — |

**Working alone.** One person holds every role. The controls against blind spots are the automated test suite, hosted CI, an explicit build ledger with proof per task (`docs/BUILD_PLAN.md`), and recorded threshold-selection evidence instead of judgement calls.

## 2. Section two: the backlog

| ID | Item | Est. hours | Priority | Depends on | Definition of done | Status |
|---|---|---:|---|---|---|---|
| B-01 | Environment and dependency setup | 2 | Must | — | Pinned `requirements.txt`; fresh install passes in CI | Done (CI run 43889620478) |
| B-02 | Data loading and normalisation | 2 | Must | B-01 | Four channels normalised; malformed and empty rows escalate | Done |
| B-03 | Document chunking and embedding | 3 | Must | B-02 | Section-aware passages with exact offsets; procedures never split | Done: Chroma + all-MiniLM-L6-v2 index |
| B-04 | Vector store and retrieval | 3 | Must | B-03 | Ranked real passage IDs; threshold returns nothing when weak | Done: lexical/dense/hybrid/rerank compared; hybrid selected |
| B-05 | Evaluation harness | 3 | Must | B-02 | One command, arbitrary input/output, metrics + manifest | Done |
| B-06 | Intent and urgency classifier | 3 | Must | B-02 | Per-class P/R; calibrated on held-out split | Done (v2) |
| B-07 | Routing logic and thresholds | 4 | Must | B-06 | Versioned rules; thresholds from risk–coverage on calibration split | Done (v2) |
| B-08 | Answer generation with citations | 3 | Must | B-04 | Every factual line cited and verified | Done (extractive; Azure optional) |
| B-09 | Guardrails and validation | 3 | Must | B-08 | Five checks recorded on every answer; engineered ticket blocked | Done |
| B-10 | Decision logging | 2 | Must | B-07 | Governance-format record per ticket; reconciliation | Done |
| B-11 | First full unattended run (THE GATE) | 1 | Must | B-05, B-09 | 500 + 80 processed, 100% reconciled | Done (16 Nov) |
| B-12 | Monitoring and dashboards | 4 | Could | B-10 | Prometheus/Grafana | **Dropped** (section 5) |
| B-13 | Continuous integration | 1 | Should | B-11 | Green hosted run | Done |
| B-14 | Fairness audit | 2 | Must | B-11 | Segment table with counts | Done (`docs/governance.md`) |
| B-15 | Report, video and submission package | 10 | Must | all | Four-part archive | In progress |
| B-16 | Governed knowledge pipeline and UI | 4 | Should | B-03 | Stage, review, certify, publish; React views | Done (local, unauthenticated) |
| B-17 | Kill switch | 1 | Must | B-07 | Next-ticket effect, tested | Done |
| B-18 | LangGraph orchestration, security layer, ML registry, rule conflict detection | 6 | Should | B-07, B-10 | Architecture components built and tested | Done (policy v3) |

## 3. Section three: build plan in detail (compressed "week two")

| Day | What will be finished by the end of the day | Est. hours | Risk to this |
|---|---|---:|---|
| 16 Nov a.m. | B-01–B-05: repository layout, ingest, chunking, retrieval, harness | 8 | Sandbox blocks network installs and Azure DNS |
| 16 Nov p.m. | B-06–B-11: classifier, routing, answers, guardrails, log, full 500/80 run | 8 | Over-escalation (it happened: 90.8%) |
| 16 Nov eve | Revision (v2): split + calibration, rule table, thresholds, kill switch; CI | 6 | Tuning on visible validation (controlled by using calibration split only) |

## 4. Section four: finishing plan in detail (compressed "week three")

| Day | What will be finished by the end of the day | Est. hours | Risk to this |
|---|---|---:|---|
| 16–17 Nov | Governance doc, prompt library, workbooks, report draft | 8 | Time; honest figures only |
| 18 Nov | Report review, video recorded twice, effort log, archive, final checklist | 8 | Video length and quality |
| 18 Nov | Final presentation and submission | 1 | Archive naming and structure |

## 5. Section five: what you will drop if you run out of time

| Item | Cut order | Consequence of cutting it | What you will say about it in the report |
|---|---|---|---|
| Prometheus/Grafana monitoring | 1st to go | No live dashboards; metrics only per run | Per-run `metrics.json` and the decision log cover auditability; live monitoring is a pilot requirement |
| Dense retrieval comparison | (not cut) | — | Built in v3 with Chroma + MiniLM; closed the fluency gap |
| API authentication and tenant isolation | (not cut) | — | Built in v3; demo keys must be replaced before real use |
| o3-mini triage experiment | 4th | Triage remains deterministic | No measured gain to justify it |
| Two-person answer review | 5th | Hallucination rate unmeasured | Stated plainly as unmeasured; extractive design limits the risk |

## 6. Section six: the daily check-in record

| Date | Finished since yesterday | Doing today | Blocked by |
|---|---|---|---|
| 15 Nov 2026 | — | Pack read; research package; architecture; Azure smoke test (user-run) | Sandbox DNS for Azure |
| 16 Nov 2026 (a.m.) | Research and architecture | Prototype, KB pipeline, HITL, 500/80 runs, safety suite (A11), gold seed | Sandbox: no localhost bind, no Docker |
| 16 Nov 2026 (p.m.) | Prototype with 9.2% auto | Diagnosed over-escalation; policy v2; threshold selection; GitHub publish; CI green | — |
| 17 Nov 2026 | _student to fill_ | Governance, workbooks, report | — |
| 18 Nov 2026 | _student to fill_ | Video, submission | — |
