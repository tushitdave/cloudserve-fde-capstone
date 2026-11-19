# CloudServe Support Intelligence — Capstone Report

**Forward Deployed AI Engineering capstone** · Tushit Dave · November 2026

Repository: https://github.com/tushitdave/cloudserve-fde-capstone (tag of record: the commit included in `04_Source_Code`)

<!-- pagebreak -->

## 1. Executive summary

CloudServe asked for a chatbot. Discovery showed that the support team is not short of answers but short of time to find them. 71% of development tickets are answerable from 29 approved articles that agents do not search. Half of the tickets escalated to tier two could have been answered from those same articles. When a ticket does need an expert, it arrives as a bare forward. The outcome CloudServe needs is therefore not a conversational front end. It needs routine documented questions answered at once, with the source shown, and everything sensitive or uncertain handed to the right person with the context already attached.

I built a single FastAPI application, orchestrated as a LangGraph state graph, with a React workspace and an unattended batch harness. Every ticket is classified for intent and urgency with calibrated confidence. Evidence comes from hybrid search: lexical TF-IDF combined with a Chroma vector index using all-MiniLM-L6-v2 embeddings. A bounded document GraphRAG step can traverse curated related-article edges only inside the policy-authorised intent scope. Hybrid was chosen by measurement over dense-only and cross-encoder reranking. A versioned rule table always escalates security, compliance, billing-dispute, account-compromise and roadmap requests. Answers are assembled only from approved article text, with a passage citation on every line, and a deterministic verifier checks each line before release. Every ticket ends as `sent` or `escalated` with a decision record in the Governance Framework's format. A kill switch stops automatic answers from the next ticket onwards, with no deployment. The API enforces keys, roles and tenant isolation, and stored records are encrypted. The React Trust Center exposes the graph, Chroma state, strategy scores and fallback, per-stage traces, outbox health, drift, offline charts, provider token/cost status and the pending two-reviewer gold workflow.

On the 500 development tickets the final system answers 80.4% automatically (escalation 19.6% against a 58% baseline and a 30% target) and sends no protected ticket. On the 80 visible validation tickets it answers 76.3% (escalation 23.8%), again with no protected ticket sent. 99.5% of answers cite an article the labels expect, and non-fluent customers are now within 2.4 points of fluent ones. The full run is unattended, reconciles every input to a terminal decision, and writes its metrics report itself.

The single most important caveat: **these are offline figures on synthetic, templated data, and no human has yet reviewed answer quality.** The labels disagree with themselves on identical text, so 100 development answers went to tickets labelled "escalate" for reasons the text does not reveal. Hallucination rate and real customer outcomes are unmeasured. The system is ready for a supervised pilot, not for unsupervised deployment.

## 2. The problem

### 2.1 What was asked for

CloudServe sells cloud infrastructure to just over two hundred business customers and receives more than 500 support tickets a week across email, live chat, documentation comments and a community forum. Their head of support, Marcus Adeyemi, brought five numbers to the first meeting, reproduced in Table 1. He asked for a chatbot that "answers the easy ones so my people can do the hard ones".

| Measure | Now | Needed |
|---|---|---|
| Time to first reply | 8–12 hours | Under 2 hours (agreement); brief target under 5 minutes |
| First-contact resolution | 42% | 60–65% |
| Escalation rate | 58% | 30% or lower |
| Customer satisfaction | 3.2 / 5 | 4.0 or better |
| Team attrition | Rising | Stable |

*Table 1. CloudServe's baseline and targets (Project Brief).*

### 2.2 What discovery revealed

A chatbot is a delivery mechanism. It says nothing about where an answer comes from, whether it is right, or what happens when it is not. The interviews and the ticket data described something different from a missing front end:

- **The answers already exist.** 357 of 500 development tickets (71.4%) are labelled answerable from the 29 support articles. The technical writer, Ines, says those articles are reviewed and accurate. Tier-one agent Sofia says "the documentation is fine. I cannot find things in it."
- **Escalation is mostly avoidable.** Tier-two engineer Daniel estimated that half of what reaches him could have been resolved earlier. The data agrees: 138 of the 281 historically escalated tickets (49.1%) were answerable from the articles.
- **Escalations arrive without context.** Daniel reads the whole thread and often re-asks the customer something already asked. That, more than waiting, is where frustration comes from.
- **A wrong answer is worse than none.** Marcus: "I would rather it said nothing than said something wrong." The customer, Ravi, will accept an automated answer if it is honest about being automated and shows where it came from.

### 2.3 The gap

CloudServe asked for a way to put answers in front of customers. What they lack is a reliable path from an approved answer to the person who needs it, together with a disciplined way of not answering when the system cannot stand behind it. The design problem is therefore as much about **when not to answer** as about answering, and about making each "no" useful to the human who receives it. A system that escalates everything is safe and useless. A system that answers everything is useful and dangerous. The value lies in a defensible line between the two, drawn from evidence and recorded for every ticket.

## 3. Discovery findings

The full evidence tables are in the Stage 1 workbook (Appendix A). This section presents the findings that changed the design.

### 3.1 Four disagreements, settled by the data

The transcripts contain points on which stakeholders disagree or are simply wrong about their own operation. Table 2 records how the ticket data settled each.

| # | Disagreement | Data | Consequence for design |
|---|---|---|---|
| D1 | Is the documentation bad, or just unfindable? (Ines heard Sofia say "bad") | 71.4% of tickets answerable from existing articles | Build retrieval over approved articles; do not write new content first |
| D2 | Is the 58% escalation rate the cost of complexity? (Marcus vs Daniel) | 49.1% of escalated tickets were answerable from docs | Automating documented answers attacks escalation directly |
| D3 | Do non-fluent customers get the worst satisfaction? (Sofia: yes) | Historical CSAT 3.04 non-fluent vs 2.95 fluent | Not true historically, but retrieval is where a new system would fail them, so it must be measured |
| D4 | Do enterprise customers get faster answers? (Ravi: in an hour) | Enterprise median resolution 369 min vs 141 business; enterprise FCR lowest at 37.3% | Perception is wrong; automation must not widen the tier gap |

*Table 2. Stakeholder disagreements and how the data resolved them.*

### 3.2 What the data shows that nobody said

The 500 development tickets contain only 216 distinct bodies. The queue is heavily repetitive, which supports Sofia's "same ones over and over" and makes automation attractive. The most frequent single question (14 copies) is a rollback procedure that exists word for word in article DOC-DEPLOY-002.

Effort is not distributed like volume (Table 3). The protected categories, security incidents, compliance and feature requests, are 14% of volume but about 25% of historical resolution time, and they must stay human. The automation opportunity is the long tail of documented procedures such as SSO configuration, rate limits and onboarding. Each escalation there consumes a senior engineer's time for an answer that exists.

| Category | Share of volume | Share of resolution time | Mean minutes |
|---|---:|---:|---:|
| Security incident | 5.2% | 9.7% | 786 |
| Compliance request | 5.2% | 8.4% | 679 |
| Feature request | 4.0% | 6.9% | 724 |
| Data residency | 5.8% | 7.1% | 515 |
| SSO configuration | 5.2% | 2.4% | 191 |
| Rate limit | 2.6% | 0.8% | 122 |

*Table 3. Volume versus effort by category (development set; resolution time is elapsed time, an upper-bound proxy for effort).*

### 3.3 Findings that emerged during the build

Three further findings came from building and running the system. They are reported here because they changed the requirements (section 9).

- **F07 — the routing labels conflict with themselves.** Among non-protected tickets, 40 of 191 groups of identical text carry both `auto_respond` and `escalate` labels. A classifier trained to predict the supplied "answerable from docs" label scored ROC AUC 0.32 on held-out development data and 0.55 on validation, no better than chance.
- **F08 — the validation set mostly repeats the development set.** 62 of 80 validation ticket bodies appear verbatim in development. Validation figures therefore overstate performance on genuinely new wording.
- **F09 — urgency is barely learnable from text.** A held-out urgency accuracy of 50% reflects identical texts with different urgency labels.

### 3.4 The problem statement

> CloudServe's support team is not short of answers; it is short of time to find them. Seven in ten tickets ask something an approved article already explains, yet customers wait most of a working day, and about half of what reaches senior engineers could have been answered from those same articles. When a ticket does need an expert it arrives as a bare forward, so the expert starts from scratch. The team needs routine documented questions answered straight away from the approved articles, in a way that shows where the answer came from, and everything sensitive, unusual or uncertain passed to the right person with a short summary of what is known and what is not. Security, compliance and money questions must always go to a person.

## 4. Requirements

Each requirement traces to a discovery row. The full PRD is the Stage 2 workbook and `docs/PRD_v1.md`; the version 2 changes are in section 9. Table 4 lists the functional requirements as they stand after revision.

| ID | Requirement (v2) | Evidence | Acceptance test |
|---|---|---|---|
| FR-01 | Normalise four channels, preserving channel and original text; malformed or empty input escalates | Brief; D1 | `test_four_channel_normalization_preserves_original_text` |
| FR-02 | Exactly one terminal state per ticket with a persistent decision record | Marcus: explainability | Run manifest reconciliation; `test_unattended_full_set_reconciles` |
| FR-03 | Intent and urgency with calibrated confidence and alternatives, trained without leakage | Sofia step 2 | Held-out ECE ≤0.05 test |
| FR-04 | Security, compliance, feature, unclear, billing-dispute, account-compromise and data-location-assurance requests always escalate | Daniel, Ines; 87 must-not tickets | `test_interview_derived_rules_escalate`; protected false-auto = 0 |
| FR-05 | Retrieve only approved, permission-filtered passages with resolvable IDs and scores, using the measured best strategy (hybrid lexical + dense) | D1, Ines | `test_architecture_components.py`, `test_retrieval_candidates.py` |
| FR-06 | Escalate when no approved article covers the intent, evidence is weak, or the request is novel; never invent a citation | Marcus; Ines | `test_no_evidence_abstains`, out-of-scope fixtures |
| FR-07 | Answer only from approved text, with each line cited and verified; block on unsupported claims, private data, commitments or instruction override | Marcus, Daniel | `test_unsafe_draft_is_blocked`, `test_engineered_ticket_trips_instruction_integrity_guardrail` |
| FR-08 | Every escalation carries summary, reason, known/unknown facts, candidate sources and next step | Daniel | `test_escalation_packet_explains_uncertainty` |
| FR-09 | Knowledge changes only through staging, review, human certification and atomic publication | Daniel (stale snippets), Ines | `test_knowledge_pipeline.py` |
| FR-10 | Reviewer UI shows scores, exact citations and versions, reasons, handoffs and lineage | Ines (which article) | React build; demo |
| FR-11 | Any compatible JSON file processed unattended from one command | Build Spec A9 | `test_unseen_file_order_count_and_provider_disabled_reconcile` |
| FR-12 | Same run emits business, technical, governance and fairness metrics | Build Spec A10 | `metrics.json` |
| FR-13 | Requests unlike any learnt ticket escalate (novelty) | Ines: novel incidents | `test_out_of_scope_fixtures_never_auto_answer` |

*Table 4. Functional requirements (version 2), evidence and acceptance tests.*

The non-functional requirements are the brief's targets: p95 latency under 3 seconds, availability of 99.5% with graceful degradation, intent precision of at least 85%, hallucination of at most 5%, citation accuracy of at least 95%, zero private data, under 5 points of group variation, complete decision logging and calibration within 5 points. The revisions added a kill switch (NFR-08), zero cost in the default path (NFR-07, satisfied by making the generative provider optional), API security (NFR-09: keys, roles, tenant isolation, quotas, encryption at rest, retention) and an ML lifecycle (NFR-10: registry, drift monitors and retraining criteria). The traceability matrix from each acceptance criterion A1–A12 to its owner, files and test is `docs/traceability.md` (Appendix C).

<!-- pagebreak -->
## 5. Architecture and design

### 5.1 The system at a glance

The system is one deployable application with two logical pipelines. The **knowledge pipeline** runs when approved content changes. The **ticket pipeline** runs on every ticket. Figure 1 shows the ticket path as implemented. Every box marked DET is deterministic code; no model can change its outcome.

```
 Ticket (email | chat | docs comment | forum)
   │
   ▼
 DET  Normalise ─ invalid channel / empty ──────────────────────────────────────┐
   │                                                                             │
   ▼                                                                             │
 ML   Classify intent + urgency (calibrated) + similarity to known tickets       │
   │                                                                             │
   ▼                                                                             │
 DET  Kill switch on? ─────────────────────────────────────────────────────────►│
 DET  Protective rules R-01..R-07 fired? (security, compliance, billing …) ────►│
 DET  Instruction-override text in ticket? (guardrail) ────────────────────────►│
 DET  Novel request (similarity < 0.35)? ───────────────────────────────────────►│
 AGT  Triage (intent confidence < 0.90): record options ────────────────────────►│
   │                                                                             │
   ▼                                                                             │
 AGT  Evidence: policy-scoped graph + hybrid lexical/Chroma MiniLM (≤ 2 tries)  │
 DET  No approved article / evidence below threshold ──────────────────────────►│
   │                                                                             │
   ▼                                                                             │
 AGT  Answer: full procedure + causes + notes, every line cited                  │
 AGT  Verify: every cited line is an exact span of its passage                   │
 DET  Guardrails: grounding, private data, tone/scope, claim support ──fail────►│
 DET  Kill switch re-checked before release ───────────────────────────────────►│
   │                                                                             ▼
   ▼                                                              ESCALATED + handoff packet
 SENT + citations                                                (reason, known, unknown, sources,
   │                                                              next step) → human review queue
   └──────────── decision record + terminal event (every path) ◄──────────────────┘
```

*Figure 1. The ticket pipeline as implemented: each row group is a node of the LangGraph state graph. DET = deterministic code, ML = trained model, AGT = bounded agent role.*

### 5.2 Why this shape and not a chatbot

The brief's reference architecture has six components: ingest, classify, retrieve, route, generate and validate. I kept them and made three choices that follow from discovery.

**First, release is owned by code, not by a model.** Marcus's failure condition is a confidently wrong public answer, and the Governance Framework's test is whether a harm is stopped by "a control you built" rather than "a property of the model". So the decision to send is a deterministic function of the rule table, thresholds, verification result and guardrails. Agents propose and code disposes.

**Second, the default answer path uses no language model.** The answer is built from the approved article itself: the complete numbered procedure, the common causes and the notes, each line followed by its passage ID. A verifier then checks every line is a verbatim span of the passage it cites. This makes hallucination structurally impossible in the default path. It satisfies Ravi's request for honesty and Ines's request to know which article an answer came from. It also keeps the unattended gate free of provider outages, rate limits and cost. The trade-off is that answers are not tailored to the specific ticket; section 7 discusses what this costs. An Azure GPT-4o drafting and verification path exists as an opt-in mode behind the same verifier and guardrails.

**Third, escalation is a product, not a failure branch.** Daniel said he does not need the system to be right; he needs it to "show its working". Every escalation therefore carries a structured handoff packet: why it escalated, what is known, what is not known (for example, the competing intent interpretations when confidence was low), the candidate passages, and a next step specific to the reason.

### 5.3 Six bounded agent roles

The design defines six roles across the two pipelines (Table 5). In the implementation each role is a small class with a single responsibility, a typed output and no ability to publish knowledge or send a reply. Because the default path is deterministic, "agent" here means a bounded decision-making component with an explicit contract. It does not mean an LLM call per role. Running six model calls per ticket would have put the 3-second latency target and the zero-cost constraint at risk without a measured quality gain.

| Role | Pipeline | Trigger | Output | Cannot |
|---|---|---|---|---|
| Source Intake | Knowledge | Unknown or incomplete source format | Parser recommendation or quarantine | Fetch URLs, approve, publish |
| Knowledge Steward | Knowledge | Every staged revision | Missing-section, duplicate, conflict warnings; review spans | Certify or publish |
| Triage | Ticket | Intent confidence below threshold | Ranked intent options for the handoff | Override rules, lower thresholds, send |
| Evidence | Ticket | Eligible ticket | `QueryPlan` and `EvidenceBundle` (≤2 searches) | Search outside approved scope |
| Answer | Ticket | Evidence sufficient | Cited draft | Add sources, set release state |
| Verification | Ticket | Every draft | Per-line supported/unsupported verdict | Release |

*Table 5. Agent roles, triggers and hard boundaries.*

### 5.4 Alternatives considered

| Decision | Alternatives | Choice and reason |
|---|---|---|
| Deployment shape | Microservices; one modular app | One FastAPI app: the clean-checkout gate rewards simplicity, and no independent scaling need exists |
| Orchestration | LangGraph (brief's suggestion); plain Python; other agent frameworks | LangGraph `StateGraph`: one node per architecture step, conditional edges for each escalation branch, no cycles. Routing decisions stay in policy code. A replay of 580 tickets matched the earlier procedural flow exactly |
| Retrieval | Lexical; Chroma + all-MiniLM-L6-v2 dense (brief); hybrid; hybrid + cross-encoder reranker | All four built and compared on the calibration split (Table 7). **Hybrid** chosen: best Hit@1 and coverage, fluency gap 3.6 vs 23.3 points for lexical. Reranker not selected (no gain, twice the latency). Azure ada-002 remains an optional code path |
| Answer generation | LLM drafting; extractive template | Extractive by default (zero hallucination by construction, zero cost); GPT-4o opt-in |
| Model provider | OpenRouter/Groq free tier (brief); Azure OpenAI | Azure deployments were available to me. Because the default path makes no model call, the hidden-set run costs nothing and does not depend on any provider |
| Knowledge structure | Vector store as source of truth; governed store + index; graph | Governed versioned store (SQLite + source manifest) is the source of truth. The Chroma collection is a derived index named by the approved-snapshot hash, so a changed article always builds a new index. No graph: 29 articles and no multi-hop questions |
| Chunking | Section-aware; fixed 80/20 windows; parent-child | Measured (`chunking_comparison_v1.json`): fixed windows broke every numbered procedure; parent-child gained 1 of 73 tickets with 2.5× the chunks. Section-aware kept |
| Classifier | TF-IDF+LR (+temperature); LinearSVC; MiniLM+LR; GPT-4o zero-shot | Measured (`classifier_comparison_v1.json`): production model best (macro-F1 1.00, ECE 0.002); MiniLM 0.968; GPT-4o 0.896 at 459 ms per ticket |
| Claim verifier (azure mode) | GPT-4o; o3-mini; deterministic exact-span | Measured on 20 clean and 20 fabricated drafts: unsafe-claim recall GPT-4o 0.05, o3-mini 0.95, exact-span 1.00. Exact-span in the default path; o3-mini in azure mode |
| Routing thresholds | Hand-set; learned from labels; risk–coverage selection | Risk–coverage selection on a held-out split under explicit safety constraints (section 6.3) |
| API security | Open local API; API keys + roles; external identity provider | API keys with five roles, object-level tenant checks, quotas, encryption at rest and retention (section 6.2). SSO is out of scope for a clean-checkout capstone |

*Table 6. Main design alternatives and the reasons for each choice.*

### 5.5 Layers

The code follows the brief's three-layer split. Interface: FastAPI routes, the React workspace and the batch CLI. Processing: normalisation, classifier, policy engine, agents and guardrails. Persistence: the ticket and decision log, the knowledge store and versioned manifests. A mechanical check (`scripts/architecture_check.py`, run in CI) forbids production modules from importing API routes or the evaluation harness, forbids contracts from depending on adapters, and scans for committed credentials.

## 6. Implementation

### 6.1 How it was built

The repository follows the prescribed layout: `src/`, `prompts/`, `tests/`, `evaluation/`, `docs/`, `data/` and `.github/workflows/`. Python 3.12+ with FastAPI, scikit-learn and Pydantic; React 19 with Vite for the workspace; SQLite for persistence. Dependencies are pinned. Hosted GitHub Actions run 44473651983 passed all 92 tests and the architecture check on a fresh Python 3.12 runner; the React production build also passes locally.

Three commands cover the assessment procedure:

```
./scripts/dev.sh                                  # API on :8001 + React on :5173
./scripts/test.sh                                 # architecture check, 92 tests, UI build
./scripts/batch.sh <input.json> <output-dir>      # unattended run + metrics + manifest
```

### 6.2 Components

**Ingest.** Any JSON row becomes a typed `Ticket`. An unrecognised channel or an empty subject and body produces a logged escalation, not an exception. Non-dict rows and missing IDs get generated IDs so that nothing is skipped. Original text, channel and an input hash are stored in the first event.

**Classify.** TF-IDF unigram/bigram features with class-balanced logistic regression, one model per head. The training data is the 397-ticket train side of a frozen split built by grouping near-duplicate tickets (cosine ≥ 0.90), so no near-copy of a calibration ticket is trained on. Each head is then **temperature-scaled** on the 103 held-out calibration tickets, minimising negative log-likelihood (Guo et al., 2017). Customer name, tier, region and history are never features.

**Retrieve.** Articles are split at their `##` sections, so each numbered procedure stays whole in one passage (145 passages, median 24 words, maximum 103). Every passage carries a stable ID (`DOC-DEPLOY-002#p04`), the source version hash, exact character offsets into the original article and inherited permissions.

The passages are indexed twice:

- a TF-IDF lexical index;
- a persistent Chroma collection embedded with all-MiniLM-L6-v2 (ONNX, 384 dimensions), whose name is derived from the hash of the approved snapshot.

Hybrid search fuses the two: score = 0.5 × lexical cosine + 0.5 × dense cosine, over the union of each method's top candidates. The caller's role is applied as a filter inside the Chroma query and the lexical candidate set, so an unauthorised passage never leaves retrieval. The Evidence role restricts the search to the articles approved for the predicted intent, and narrows it to one article when the document model agrees confidently. It retries once with the intent name added to the query, and keeps only Resolution passages as primary evidence. If the dense index or model is unavailable, retrieval falls back to lexical and the reason is logged with the lexical threshold applied. Ines's example shows why the dense index matters. "My deployment keeps dying and restarting" retrieves an onboarding passage lexically, but the container health-check article densely.

**Route.** `policy_v2.json` (policy v3) holds eight rules: the kill switch plus seven protective rules. Each has a priority, owner, effective window, approval status, the interview evidence behind it, the requirement it serves, and positive and negative examples. `policy_rules.py` validates the table before it can load. It checks the schema, unique IDs and priorities, effective dates, and that every example still fires (or does not fire) its rule. It reports a conflict if two active rules with different actions both match any example in overlapping windows, and warns about shadowed rules. Rules are evaluated before any drafting. The retrieval strategy and all thresholds are read from the same file and were produced by the selection script.

**Generate and validate.** The extractive answer and line-level verifier are described in 5.2. The deterministic guardrails then run on every answer and record pass or fail: grounding, private data (email, keys, card and phone patterns, customer ID and the customer's own name), tone and scope (refund, credit, fix or timeline commitments) and claim support. An instruction-integrity guardrail runs on the ticket before drafting.

**Log.** Each ticket writes an encrypted sequence of events (normalised, classified, triage, evidence, drafted, verified, routed, decision, terminal) and a final result. The `decision` event follows the Governance Framework's minimum record, including prompt version and requirement IDs. The harness writes `results.json`, `metrics.json` and a `run_manifest.json`. The manifest holds the input hash, all component versions, the thresholds, the kill-switch state and the exact lists of input, terminal and decision IDs. The run fails loudly if they do not match.

**Orchestration.** The ticket path is a LangGraph `StateGraph` (`orchestration/ticket_graph.py`) with nodes classify → policy_gate → triage or evidence → answer → verify_validate. Conditional edges lead to escalation at every gate. The graph has no cycles, so each node runs at most once per ticket. Nodes call agents and policy functions but never decide release themselves.

**Security.** Every API call except `/health` needs an API key. Keys map to five roles (customer, support agent, knowledge owner, operator, admin) and a tenant.

- A customer can only raise and read tickets for its own account. Another tenant's ticket returns 404, so its existence is not revealed.
- Decisions are visible to support staff only. The kill switch belongs to operators and knowledge publishing to knowledge owners.
- Each key has a per-minute quota (429 when exceeded).
- Stored results and events are encrypted with Fernet.
- An administrator can erase a customer's raw text, or purge it after a retention period, while the decision records stay for audit.

Local demo keys make the README demo work. They are documented as public and must be replaced for any real use.

**ML lifecycle.** `model_registry.json` records each classifier head's dataset and split hashes, feature definition, hyperparameters, a platform-stable artifact fingerprint, calibration temperature, held-out report and promotion record. Every batch run compares its tickets with the training reference: predicted-intent PSI, text length, out-of-vocabulary rate, novelty share and confidence. It raises drift alerts against registered thresholds. Retraining is recommended only on a window of at least 200 tickets. A retrained model must pass `promotion_check` (no per-class precision loss, no extra protected false-auto, no larger subgroup gap, bounded latency) and be approved by a person.

**Reliability and observability.**

- Every graph node runs inside an OpenTelemetry span that carries identifiers, versions and timings but no ticket text.
- Each node has a time budget in the policy file; a node that overruns escalates the ticket.
- Batch runs write `traces.jsonl` and per-stage p50/p95 latency.
- The customer message is written to a transactional outbox in the same commit as the decision. A dispatcher delivers it at most once, retrying with backoff and moving persistent failures to a dead-letter state.
- Knowledge ingestion retries model and storage failures in the same way and parks exhausted work items for an operator.

**Code structure.** The code follows the hexagonal layout the architecture specified:

- `domain/` holds contracts, rules and guardrails;
- `ports/` holds Protocol interfaces;
- `adapters/` holds persistence, retrieval, ML and Azure;
- `application/` holds the use cases;
- `orchestration/` holds the graph and agents.

`scripts/architecture_check.py`, run in CI, rejects imports that cross layers the wrong way.

**Knowledge governance.** A changed article is staged, checked by Source Intake and Knowledge Steward, and quarantined if it contains secrets, instruction-like text, unknown IDs or permission changes. It must then be certified by a named reviewer and published atomically. Old citations remain resolvable by source version.

### 6.3 Choosing thresholds from data

The brief warns against "a threshold chosen because it looked reasonable", and the architecture asks for retrieval methods to be compared rather than assumed. Both choices were made together, on the 103-ticket calibration split only.

First, `evaluation/retrieval_comparison.py` measured document-level retrieval quality for the four strategies (Table 7).

| Strategy | Hit@1 | Recall@3 | MRR@5 | Non-fluent Hit@1 | p95 latency |
|---|---:|---:|---:|---:|---:|
| Lexical TF-IDF | 0.918 | 0.973 | 0.948 | 0.667 | 5 ms |
| Dense (Chroma + all-MiniLM-L6-v2) | 0.931 | 0.959 | 0.951 | 0.800 | 98 ms |
| Hybrid (chosen) | 0.959 | 0.973 | 0.964 | 0.800 | 112 ms |
| Hybrid + cross-encoder | 0.945 | 0.973 | 0.957 | 0.800 | 230 ms |

*Table 7. Retrieval strategies on the calibration split (unscoped over 29 articles; answerable tickets; expected-document labels).*

Then `evaluation/threshold_selection.py` replayed the full routing decision for every calibration ticket over 5,712 combinations: four strategies × intent confidence × similarity to known tickets × document-model confidence × a strategy-specific evidence threshold. It kept only configurations meeting three hard constraints:

- zero protected tickets answered;
- zero answers to a 12-ticket hand-written out-of-scope fixture (weather, pizza, poems, a cat eating a keyboard);
- answers citing an unexpected article at most 5% of the time.

Among those it chose the highest automatic coverage. Ties were broken by safe-auto recall, then the cheaper strategy, then stricter values.

The best eligible configuration per strategy reached these coverages:

- lexical 79.6%, with a fluency gap of 23.3 points;
- dense 83.5%, with 4.7% wrong articles;
- hybrid 84.5%, with safe-auto recall 95.8% and a fluency gap of 3.6 points;
- hybrid + rerank 84.5%, with the same recall but a 21.4-point fluency gap and twice the latency.

**Hybrid was selected, and the reranker was measured but not adopted**, as ADR-004 requires ("add reranking only if it improves within latency"). Table 8 shows the risk–coverage trade-off along the hybrid evidence threshold at the chosen values of the other three.

| Hybrid evidence threshold | Coverage | Wrong-article rate | Safe-auto recall |
|---:|---:|---:|---:|
| 0.10 (chosen) | 84.5% | 2.3% | 95.8% |
| 0.20 | 80.6% | 2.4% | 91.5% |
| 0.30 | 73.8% | 2.6% | 83.1% |
| 0.40 | 35.9% | 0.0% | 42.3% |

*Table 8. Risk–coverage along the hybrid evidence threshold on the calibration split (protected and out-of-scope answers are zero in every row shown).*

The chosen values are hybrid retrieval, intent ≥ 0.90, similarity ≥ 0.35, document ≥ 0.20 and hybrid evidence ≥ 0.10. The lexical fallback keeps its own selected threshold (0.06). A stricter evidence gate cost coverage without reducing wrong articles consistently, because intent and document scoping already do most of the work. The novelty and out-of-scope constraints are what protect against genuinely unfamiliar text.

### 6.4 What the system produces

Figure 2 is the complete customer message the system released for development ticket DEV-0026 (chat, no subject): *"When I page through results I am seeing some records twice and missing others entirely. The collection does change while I iterate. Am I doing this the wrong way?"*

```
Thanks for contacting CloudServe support. This reply was prepared automatically from our approved
guide "Pagination and handling large result sets"; a member of the team can review it if it does
not resolve the problem.

Common causes:
- The cursor from the previous response was not passed to the next request [DOC-API-002#p03]
- Offset pagination was used against a changing collection [DOC-API-002#p03]
- The page size requested exceeds the maximum [DOC-API-002#p03]

What to do:
1. Use cursor pagination for anything that may change while you iterate. Offset pagination will
   skip or repeat records when items are inserted mid-iteration. [DOC-API-002#p04]
2. Pass the next_cursor value from each response as the cursor parameter of the following
   request, and stop when it is null. [DOC-API-002#p04]
3. Keep page size at or below two hundred. Larger requests are rejected rather than truncated.
   [DOC-API-002#p04]
4. For very large extracts, use the export endpoint, which runs asynchronously and returns a
   download link. [DOC-API-002#p04]

Note: Cursors expire after one hour. Long-running iterations should handle expiry by restarting
from a recorded checkpoint. [DOC-API-002#p05]

If these steps do not resolve it, reply to this ticket and a support specialist will take over.
```

*Figure 2. A released answer. Every factual line is a verbatim span of the cited passage, and each passage ID resolves to an exact version of the approved article.*

The decision record for this ticket shows calibrated intent confidence 1.00, `api_usage_question`, hybrid evidence score 0.251 against a threshold of 0.10, no rules fired, and all five guardrails `pass`. Its fields are `action_taken: auto_respond`, `prompt_version: answer-extractive-v2` and `requirement_ids: FR05, FR07`.

Figure 3 is the handoff a specialist receives for a protected ticket: *"We believe a production key was exposed and unauthorized access may have occurred."*

```
reason_codes : protected_intent:security_incident     rules fired: R-01, R-02, R-03
summary      : Review security incident request (urgency high). Why escalated: This type of
               request always needs a specialist. Customer said: Possible security incident …
known        : Channel: email | Predicted intent: security_incident (0.98) |
               Predicted urgency: high (0.40)
unknown      : Customer-specific account state and final resolution are unverified.
next_step    : A specialist must handle this category directly; check the customer's account
               and policy before replying.
customer msg : We have passed your request to a support specialist, together with the details
               you sent. You do not need to resend anything; the specialist will reply on this
               ticket.
```

*Figure 3. An escalation packet. The customer is told honestly that a person will reply. No response-time promise is made.*

Three rules fired independently: the predicted intent (R-01), the word "exposed" (R-02) and "unauthorized access" (R-03). Layered rules mean a misclassified security ticket is still caught by its wording. The urgency confidence of 0.40 is shown as it is: low, and labelled as such in the UI.

### 6.5 What was difficult

The hardest problem was not technical. The first complete version passed every acceptance test, yet escalated 90.8% of tickets, worse than the 58% the client is trying to reduce. Finding the cause took a deliberate step back from the code to the labels (section 9). A second difficulty was calibration on templated data. With no classification errors on the calibration split, temperature scaling drove confidence toward 1.0. That is correct for in-distribution tickets and badly overconfident for anything else, which is what motivated the novelty gate. The build environment at first blocked network installs, localhost binding, Docker and Azure DNS, so hosted CI became the independent proof of a clean install. When network access returned, dense retrieval and the reranker were built on local ONNX models instead of Azure, so the assessed path needs no provider key. A last, small lesson came from CI: the registry's artifact fingerprint differed between macOS and Linux because of floating-point noise in the model coefficients. It now hashes rounded coefficients.

### 6.6 What I would restructure

The ticket flow is a LangGraph graph inside a hexagonal layout, but its nodes still share one mutable context object for simplicity. I would replace that with the typed `ContextEnvelope` design from the research, so each node receives only the fields it is allowed to see and can be tested in isolation. The handoff contracts exist as versioned JSON Schemas (`docs/schemas/`), but the prototype still passes some loosely typed dictionaries between steps. I would also move persistence behind a port so that PostgreSQL could replace SQLite for concurrent use.

<!-- pagebreak -->
## 7. Evaluation

### 7.1 Method

**Data.** Three disjoint uses of the supplied data:

- The 500 development tickets were split once, by near-duplicate group, into 397 train tickets (model fitting) and 103 calibration tickets (temperature scaling and threshold selection).
- The 80 visible validation tickets were used to check progress.
- The hidden 120-ticket assessment set has never been seen.

The harness takes an input path and was rehearsed on a reordered six-ticket file with a malformed row, a missing ID and the provider disabled.

**Runs.** The figures below come from the final policy (v3: hybrid retrieval), extractive mode, run unattended on 16 November 2026 with `scripts/batch.sh`. Every metric is computed by the harness in the same run (`metrics.json`). I have to be candid about the visible validation set. It was run at least fifteen times over the project (twelve recorded batch directories, a repeat under v2 and two clean-clone rehearsals). During the first version, some of its results influenced policy text patterns, and those patterns have since been removed (section 9). The final retrieval strategy and thresholds were selected on the calibration split only, and no v2 or v3 threshold or rule changed after a validation run.

**Definitions.**

- **First-contact resolution proxy:** automatically answered tickets divided by all tickets. No customer confirmed resolution, so this is an upper bound.
- **Safe-auto recall:** tickets labelled `auto_respond` that were answered and cited an expected article, divided by tickets labelled `auto_respond`.
- **Wrong-article rate:** answers whose citations include none of the expected articles, divided by all answers.
- **Protected false-auto:** tickets labelled `must_not_auto_respond` that were answered.

### 7.2 Business outcomes

| Measure | Baseline | Target | Achieved (dev) | Achieved (validation) | Confidence in the figure |
|---|---:|---:|---:|---:|---|
| First-contact resolution (proxy) | 42% | 60% | 80.4% | 76.3% | Low–medium: offline upper bound, no customer confirmation |
| Mean time to first reply | 8–12 h | < 5 min | ~0.1 s (automated share) | ~0.1 s | Low: local processing only; escalations still wait for a person |
| Satisfaction proxy | 3.2 / 5 | 4.0 | not measured | not measured | No human-rated sample yet |
| Escalation rate | 58% | ≤ 30% | 19.6% | 23.8% | Medium: depends on label quality (7.5) |
| Repeat contacts | 21.6% (sample) | halved | not measurable offline | — | Requires live follow-up data |

*Table 9. Business outcomes. The automated figures are offline proxies.*

Read together, these say that on tickets resembling the supplied data, roughly eight in ten could receive a cited answer within seconds instead of 8–12 hours. That would bring escalations below the 30% target. What they do not say is that those customers' problems were solved. A pilot would need to measure confirmed resolution and repeat contacts, which is exactly the false-resolution failure the Evaluation Framework warns about.

### 7.3 Technical performance

| Measure | Target | Achieved (dev) | Achieved (validation) | Notes |
|---|---:|---:|---:|---|
| Intent precision (macro, 22 classes) | ≥ 85% | 100% | 100% | Also 100% on the held-out calibration split; templated data, so expect lower on new wording |
| Intent recall (macro) | — | 100% | 100% | |
| Urgency accuracy | — | 64.8% | 42.5% | 50% held-out; used for priority only, never for release |
| Intent calibration (ECE) | ≤ 0.05 | 0.0003 | 0.002 | 0.002 on calibration split |
| Route agreement with labels | — | 78.2% | 76.2% | v1: 47.0% / 43.8%; v2: 74.6% / 71.3% |
| Safe-auto recall | — | 96.8% | 93.8% | v1: 14.8% / 6.3%; v2: 86.5% / 81.3% |
| Answers citing an expected article | — | 99.5% | 100% | 2 and 0 wrong-article answers |
| Exact citation resolvability | — | 100% | 100% | ID, version and text match the corpus |
| Hallucination rate | ≤ 5% | not measured | not measured | Extractive lines are verified verbatim (402/402 pass), but relevance needs two-person review |
| Citation accuracy (semantic) | ≥ 95% | not measured | not measured | Same |
| Latency p95 | < 3 s | 206 ms | 204 ms | Local, includes dense query embedding; Azure mode unmeasured |
| Availability | ≥ 99.5% | not measured | — | Provider outage degrades to escalation (tested), but no live uptime record |

*Table 10. Technical performance.*

### 7.4 Governance conditions

| Condition | Requirement | Result |
|---|---|---|
| Private data in outbound text | Zero | 0 detections; the scan ran on all 463 answers; injected email draft blocked |
| Protected tickets answered | Zero | 0 of 87 (dev) and 0 of 14 (validation) |
| Out-of-scope tickets answered | Zero | 0 of 12 |
| Decision logging | Complete | 500/500 and 80/80; input, terminal and decision ID lists identical |
| Confidence calibration | Within 5 points | Intent: met (ECE 0.2 points); urgency: 5.5 points on calibration, not met |
| Quality across groups | < 5 points | Fluency **met** (2.4 points, was 7.1); tier met (4.6); region **not met** (10.3 points, Latin America n=39) |
| Degraded mode | Safe without dense index | Forced lexical fallback: 359/500 sent, protected 0, wrong article 0.6% |

*Table 11. Governance conditions.*

### 7.5 Interpretation

**Where the escalations come from.** Of the 98 development escalations, 87 are protective-rule escalations: security, compliance, feature and unclear requests. Another 6 are data-location assurance requests. Only 3 have insufficient passage evidence and 2 are novel requests. Under lexical retrieval (v2), 41 tickets escalated for insufficient evidence. Hybrid retrieval recovered almost all of them, which is where the 7.6-point coverage gain came from.

**Coverage by intent.** Table 12 breaks the development run down by intent. Thirteen documented intents are answered every time, and the four protected intents are never answered. Onboarding was the weakest intent under lexical retrieval: 18% answered, because broad "how do I get started" wording rarely matched a Resolution passage. It is now 95% answered with 100% safe-auto recall. Data residency remains the lowest answered documented intent (79%), by design: the data-location assurance rule sends definitive compliance questions to a specialist. Database issue and performance degradation are answered far more often than their labels suggest (25 of 26 and 23 of 23 answered, only 10 labelled auto each). That is where the label disagreement concentrates.

| Intent | Tickets | Answered | Labelled auto | Safe-auto recall | Main escalation reason |
|---|---:|---:|---:|---:|---|
| account access | 22 | 22 (100%) | 17 | 100% | — |
| api key issue | 18 | 18 (100%) | 12 | 100% | — |
| billing query | 24 | 24 (100%) | 21 | 100% | — |
| configuration help | 17 | 17 (100%) | 10 | 100% | — |
| data export | 29 | 29 (100%) | 27 | 100% | — |
| deployment failure | 27 | 27 (100%) | 19 | 95% | — |
| integration help | 21 | 21 (100%) | 16 | 100% | — |
| performance degradation | 23 | 23 (100%) | 10 | 100% | — |
| quota or overage | 23 | 23 (100%) | 20 | 100% | — |
| rate limit | 13 | 13 (100%) | 12 | 100% | — |
| rollback request | 28 | 28 (100%) | 21 | 100% | — |
| sso configuration | 26 | 26 (100%) | 22 | 100% | — |
| webhook issue | 21 | 21 (100%) | 16 | 100% | — |
| database issue | 26 | 25 (96%) | 10 | 90% | insufficient evidence |
| onboarding | 22 | 21 (95%) | 20 | 100% | insufficient evidence |
| authentication failure | 20 | 19 (95%) | 14 | 100% | insufficient evidence |
| api usage question | 24 | 22 (92%) | 23 | 91% | novel request |
| data residency | 29 | 23 (79%) | 21 | 71% | data location assurance |
| compliance request | 26 | 0 (0%) | 0 | — | protected intent |
| feature request | 20 | 0 (0%) | 0 | — | protected intent |
| security incident | 26 | 0 (0%) | 0 | — | protected intent |
| unclear request | 15 | 0 (0%) | 0 | — | protected intent |

*Table 12. Development run by intent (policy v3). Safe-auto recall uses only tickets labelled `auto_respond`.*

**The answers that disagree with the labels.** 100 development answers (25% of answers) went to tickets whose supplied label says `escalate` but which are not protected. I could have reduced this number only by escalating tickets whose text is identical to tickets labelled `auto_respond`. Among non-protected tickets, 40 of 191 groups of identical text carry both labels. Whatever distinguishes them is not in the ticket, perhaps account context or the historical agent's judgement. I therefore report them separately from safety failures and treat them as the first item for human review. They are not proof of harm, and they are not proof of safety either.

**Fairness.** The variation the Governance Framework predicts was present, and measuring it changed the design. Under lexical retrieval, non-fluent customers' safe-auto recall was 81.2% against 88.3% for fluent customers: their phrasing failed the lexical evidence threshold more often. With hybrid retrieval it is 95.0% against 97.4%, a 2.4-point gap inside the 5-point condition. Only 3 of 80 labelled-auto non-fluent tickets now escalate, two of them through the data-location rule. Tier and length gaps are below 5 points, and enterprise customers are not worse served (100%), which answers Marcus's and Ravi's concern. Latin America remains 10.3 points below the best region. Region is not a model input and n=39, so it is probably noise, but the condition is not met and it is reported.

### 7.6 Limits of what was measured

The figures above should be treated with caution because the tickets are synthetic and heavily templated (216 distinct bodies in 500). The development figures are partly in-sample. The validation set shares 62 of its 80 texts with development. The route labels contradict themselves on identical text. Retrieval was compared at document level, not on human-adjudicated passages. No human has yet rated answer relevance or claim support. Business outcomes are offline proxies with no customer confirmation. The single most informative next measurement is a two-person review of at least 50 automatic answers, including the 100 label-disagreement cases. The review tooling, a 120-ticket stratified queue, two independent reviewer templates and an agreement script, is built and waiting in `evaluation/gold/`.

## 8. Governance and risk

The full governance pack is Appendix B (`docs/governance.md`). In summary:

**Risk register.** Eleven risks are registered, each with likelihood, impact, a mitigation that names a control in the code and the test that shows it, residual risk and owner. The two highest are a confidently wrong answer (R-01) and instruction injection (R-03). They are mitigated by protective rules, the novelty gate, extractive verified answers and the instruction-integrity guardrail. Two security risks (R-10 unauthorised access and R-11 raw text at rest) are mitigated by the API key, role and tenant checks, encryption and retention controls. The only risk recorded as observed rather than potential is unequal quality across groups (R-04). It was reduced by hybrid retrieval and remains open for region.

**Fairness audit.** Section 7.5 and Appendix B give segment tables by tier, fluency, ticket length and region, with counts. The fluency condition is now met; the regional condition is not, and I say so.

**Decision logging.** Every ticket writes the Governance Framework's minimum record. That includes model and prompt versions, alternatives, sources with scores, thresholds applied, rule IDs fired, the action and a readable reason, guardrail results (pass and fail) and requirement IDs. Coverage reconciles exactly in every run, and the harness refuses to finish if it does not.

**Guardrails.** Five checks run in production code on every answer, plus an input check on every eligible ticket. All can block, none redacts and sends, and every result is recorded. An assessor can trigger one by submitting a ticket containing "Ignore all previous instructions…", which is blocked and escalated.

**Access, data protection and rules.**

- Every API call carries a key that maps to a role and tenant. A customer cannot see another tenant's tickets, and only operators can throw the kill switch.
- Stored decisions are encrypted.
- A customer's raw text can be erased on request, or after a retention period, without losing the audit record.
- The rule table is checked for conflicts and failing examples before it can load.
- The classifier's lineage, promotion and drift thresholds are kept in a model registry.

**Kill switch and incident procedure.** An operator (role-checked) can stop all automatic answers from the Overview page, through `POST /v1/policy/kill-switch`, or with an environment variable. It takes effect on the next ticket, and tickets in flight are re-checked and held. A six-step incident procedure (detect, contain, assess, notify, remediate, review) is written for someone unfamiliar with the system at 2 a.m.

**Declaration.** This system must never send an automatic answer to a security, compliance, billing-dispute, account-compromise or roadmap request, or send text not traceable to an approved CloudServe article. That is enforced by versioned rules evaluated before any drafting, extractive answers verified line by line, blocking guardrails and the kill switch. The most likely way it could still cause harm is sending the right article to a customer whose situation it does not fit. I would not deploy it without a two-person review of answers, replacing the demo keys and moving the data key to a secret store, a larger per-region sample, and a supervised pilot.

## 9. The requirements revision

**What prompted it.** The first complete version met every acceptance criterion, and it was useless. It answered 46 of 500 development tickets and escalated 90.8%, worse than the baseline it was meant to reduce. That fails Marcus's second test: a system that makes more work than it saves. Tracing the escalations showed that 197 came from a single gate, a classifier predicting the supplied `answerable_from_docs` label.

**What I found.** That classifier scored ROC AUC 0.32 on held-out development data and 0.55 on validation, which is chance. The cause was in the labels themselves: identical text carries both answers in 40 of 191 duplicate groups. I also found that 62 of 80 validation texts repeat development text. Three of my own policy patterns had been written against specific validation tickets, which is tuning against the check set. And the classifier had been trained on all 500 development tickets, so its "100% precision" was in-sample.

**What changed (version 2).**

- The classifier now trains on a leakage-safe split and is calibrated on held-out data.
- The answerability gate is gone; the system escalates only what it cannot ground.
- Rules moved into a versioned table with interview evidence. The three validation-fitted patterns were deleted, and billing-dispute, account-compromise and data-location rules were added from Daniel's interview.
- A novelty requirement (FR-13) was added after I found calibrated confidence of 0.99 on "My cat ate my keyboard".
- A kill switch (NFR-08) was added.
- Thresholds are now chosen by the recorded risk–coverage procedure.

Automatic answers rose from 9.2% to 72.8% and escalation fell to 27.2%, with protected false-auto still zero.

**Second and third revisions (versions 3 and R3).** A review against the research architecture then showed six designed components still unbuilt: Chroma with MiniLM dense retrieval, LangGraph orchestration, a reranker experiment, the security layer, an ML registry with drift monitoring, and rule conflict detection. The fluency gap had no tested remedy either. Building and measuring them changed the system again:

- Hybrid retrieval was selected over lexical, dense and reranked alternatives.
- The fluency gap fell from 7.1 to 2.4 points.
- Automatic answers rose to 80.4% (development) and 76.3% (validation), with wrong-article answers falling to 0.5% and 0%.
- The reranker was an instructive negative result: built, measured, and not adopted because it added latency without improving retrieval.
- The verifier comparison was another. GPT-4o, the model the architecture first assigned to verification, passed 19 of 20 fabricated claims, while o3-mini caught 19 and the deterministic exact-span check caught all 20. The azure-mode verifier was switched to o3-mini.

| Measure (development / validation) | Version 1 | Version 2 | Version 3 |
|---|---|---|---|
| Automatic answers | 46 / 3 | 364 / 55 | 402 / 61 |
| Escalation rate | 90.8% / 96.3% | 27.2% / 31.3% | 19.6% / 23.8% |
| Route agreement with labels | 47.0% / 43.8% | 74.6% / 71.3% | 78.2% / 76.2% |
| Safe-auto recall | 14.8% / 6.3% | 86.5% / 81.3% | 96.8% / 93.8% |
| Protected false-auto | 0 / 0 | 0 / 0 | 0 / 0 |
| Intent calibration ECE | 0.456 / 0.501 | 0.0003 / 0.002 | 0.0003 / 0.002 |
| Thresholds | Hand-set (0.24, 0.11, 0.68) | Selected on calibration split (0.90, 0.35, 0.30, 0.06) | Strategy + thresholds selected together (hybrid; 0.90, 0.35, 0.20, 0.10) |
| Rules | Regexes in code, three fitted to validation tickets | Versioned table R-00–R-07 with evidence and owners | Plus lifecycle fields, examples and conflict detection |
| Kill switch | None | UI, API, environment variable | Operator role enforced |
| Retrieval / orchestration / security | Lexical / procedural / none | Lexical / procedural / none | Hybrid Chroma MiniLM / LangGraph / keys, roles, tenants, encryption, retention |
| Answer content | First 540 characters of one passage | Full procedure, causes and notes, each line verified | Same |

*Table 13. Versions 1, 2 and 3.*

**Fourth revision (R4, evaluator-visible trust).** The final submission audit found that relationship metadata and observability existed in code or files but were difficult to inspect in the product. I added policy-scoped one-hop document GraphRAG and a Trust Center that renders the knowledge graph, Chroma collection, four retrieval strategies and fallback, ticket trace waterfall, per-stage latency, outbox health, drift, offline metrics, provider token/cost status and the human-review queue. The architecture now names MiniLM/384 dimensions as the active index rather than ada-002. The graph is real execution over curated document edges, but I do not claim a quality gain until the pending two-reviewer passage gold is adjudicated.

**What it taught me.** I had treated the labels as ground truth and escalation as the safe default. Both were wrong. A label is only a useful target if the input contains the information to predict it, and a system that escalates everything hides its uncertainty as effectively as one that answers everything. The requirement should have been "escalate what cannot be grounded" from the first day. The full log, including the assumptions that failed and the things I chose not to change, is the Stage 5 workbook (Appendix A) and `docs/PRD_revision_log.md`.

## 10. Conclusions

**What was achieved.** A runnable, tested system that answers about eight in ten CloudServe-style tickets with a cited, verifiable reply from approved documentation. It refuses every protected ticket and every out-of-scope fixture, and hands the rest to a person with the reasoning attached. It processes any input file unattended, explains every decision in a persistent record, can be stopped instantly, and costs nothing to run in its default mode.

**What I would do next, in order.**

1. Two-person review of at least 50 automatic answers, starting with the 100 label-disagreement cases, to measure hallucination and citation accuracy properly.
2. Label passages (not only documents) for the retrieval comparison, and settle the regional gap with a larger per-region sample.
3. Replace the demo API keys with an identity provider and move the data key into a secret store.
4. Run a supervised pilot that measures confirmed resolution, repeat contacts and CSAT instead of proxies.
5. Make answers more specific to the ticket, possibly with the GPT-4o drafting path, but only behind the same verifier, and only once the reviewed sample shows it adds value.

**What remains uncertain.** Whether the answers are actually helpful to the customers who receive them; whether the label disagreements hide real risk; how the system behaves on wording genuinely unlike the training set; and whether CloudServe's real tickets are as repetitive as the supplied sample.

## Declaration of AI tool use

AI-assisted development tools were used as a productivity aid for research synthesis, code scaffolding, documentation refinement and test generation. I defined the problem framing, architecture, requirements, Azure deployment choices, safety boundaries, evaluation approach and submission scope. I reviewed implementation changes, ran the automated and browser checks, analysed failures, and accepted or revised the final results. Examples of decisions made during that review include:

- I rejected the first version after seeing its 90.8% escalation rate, and directed the diagnosis that led to revision R1.
- I removed patterns that had been fitted to validation tickets.
- I corrected a date inconsistency during the documentation review.
- I insisted that effort-log hours come only from my own record.

All figures in this report were produced by scripts in the repository and can be regenerated with the commands in Appendix D. The final system was validated through automated tests, production builds, container rehearsal and evaluator-facing browser checks. No third-party source code was copied beyond the open-source packages listed in `requirements.txt` and `frontend/package-lock.json`.

<!-- pagebreak -->

## Appendices

- **Appendix A — Stage workbooks.** Submitted separately in `03_Workbooks` and in the repository under `docs/workbooks/`.
- **Appendix B — Governance pack.** Reproduced below from `docs/governance.md`.
- **Appendix C — Acceptance traceability (A1–A12).** Reproduced below from `docs/traceability.md`.
- **Appendix D — Evaluation snapshot and reproduction commands.** Reproduced below from `docs/evaluation_snapshot.md`.
- **Appendix E — Prompt register.** `prompts/registry.json` and the Stage 3 workbook.
