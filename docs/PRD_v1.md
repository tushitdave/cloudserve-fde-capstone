# CloudServe product requirements version 1

## Purpose and decision

The product helps CloudServe answer documented support questions safely and route all other tickets to a specialist with context. It is a local FDE capstone prototype. The [problem statement](problem_statement.md) records the business and technical framing and evidence IDs F01–F06. The [architecture](architecture.md) defines six bounded roles across knowledge governance and ticket processing. The [build ledger](BUILD_PLAN.md) controls what is actually proven.

## Functional requirements

| ID | Requirement | Evidence | Implemented owner and proof |
|---|---|---|---|
| FR01 | Accept email, chat, documentation-comment and forum tickets; preserve channel and original Unicode text. | F01, F04 | Ticket intake; `tests/test_rehearsal.py`. |
| FR02 | Every accepted ticket has one trusted ID, trace ID, final state and persistent decision events. | F01, Build Specification A8–A9 | Workflow/persistence; `tests/test_workflow.py`, batch manifest. |
| FR03 | Predict intent, urgency and numeric confidence, retaining alternatives and an unknown fallback. | F04 | Classification ML; `classifier.py`, `contracts.py`, batch metrics. Calibration remains open. |
| FR04 | Apply hard protected-intent and `must_not_auto_respond` rules before any automatic answer. | F04 | Policy/release gate; safety tests and protected sample. |
| FR05 | Search only approved, versioned articles; return real passage IDs, text, offsets and relevance scores. | F02, F03 | Knowledge/evidence; `tests/test_retrieval_candidates.py`, knowledge tests. |
| FR06 | Escalate when evidence is absent, weak, unauthorized or unavailable; never invent a citation. | F02, F03 | Evidence/release; workflow and safety tests. |
| FR07 | Draft from approved evidence and verify citations, unsupported claims, private data and forbidden commitments before release. | F03, F05 | Answer/verification; `tests/test_workflow.py`, `scripts/demo_guardrail.py`. |
| FR08 | Provide human handoff summary, known/unknown facts, reasons, source candidates and next step. | F02 | Handoff/persistence; `tests/test_human_resolution.py`. |
| FR09 | Govern source updates through staging, quarantine, human review and atomic publication with history. | F02, F03 | Knowledge pipeline; `tests/test_knowledge_pipeline.py`, API tests. |
| FR10 | Let a reviewer see ticket scores, exact citation/version, decision reasons, handoffs, knowledge lineage and review state in React. | F02, F05 | UI/API; React build passes; live browser proof open. |
| FR11 | Process any compatible JSON-list file unattended with one output per input and no manual action. | F04, Build Specification A9 | Batch harness; 500/80 runs and six-item unseen rehearsal. |
| FR12 | Emit volume, classification, retrieval, latency, guardrail and decision metrics in the same run. | F01, F04, F06 | Evaluation harness; `metrics.json`, `run_manifest.json`. |

## Nonfunctional requirements and measurement

| ID | Target or gate | Measurement and current status |
|---|---|
| NFR01 | 100% accepted-ticket terminal and decision reconciliation. | Exact input, terminal and decision ID lists in run manifest; local 500/80 and unseen rehearsal pass. |
| NFR02 | Zero protected false-auto outcomes in the evaluated protected fixtures. | Safety suite and labelled batch diagnostic; an independent hidden set is still required. |
| NFR03 | Intent precision ≥85%, hallucination ≤5%, citation accuracy ≥95%. | Project Brief targets. Per-class metrics exist, but human claim/passage gold and untouched holdout are pending; do not claim achievement. |
| NFR04 | p95 substantive response <3 seconds, availability ≥99.5%, confidence calibration within five percentage points. | Project Brief targets. Offline batch latency is available; live availability and calibration remain unmeasured. |
| NFR05 | No outbound private customer data or unsupported promises. | Deterministic validator and injected safety cases; production privacy review remains open. |
| NFR06 | Less than five percentage points of quality variation across defined customer groups. | Compare tier, region and language fluency with sample sizes and uncertainty; fairness audit pending. |
| NFR07 | Reproducible clean checkout and one-command tests. | Source-copy npm/test/build/batch passed; fresh Python install, live browser and Docker checks remain open. |

## Protected cases and exclusions

Security incidents, compliance requests, feature requests, unclear tickets, missing evidence, failed model/retrieval calls, unsafe source updates, private data and unsupported commitments route to human review or source quarantine. Customer text and retrieved documents are data, not instructions. The prototype includes authenticated tenant isolation and bounded document GraphRAG over curated relationships. It excludes live CRM writes, real customer messaging, SQL/entity auto-ontology execution, and claims of observed CSAT or first-contact-resolution improvement.

## Design choice and revision trigger

The implementation defaults to local extractive answers with hybrid TF-IDF + Chroma MiniLM retrieval. A bounded one-hop document graph may widen a weak document seed only inside the intent policy's authorised scope. Azure GPT-4o/o3-mini and ada-002 remain optional tools. Full entity ontology and further graph expansion require measured gain against human-approved passage gold and latency limits. A poor metric never justifies bypassing the release gate.
