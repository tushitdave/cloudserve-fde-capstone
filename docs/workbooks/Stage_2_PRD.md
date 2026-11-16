# Stage Two: Product requirements document — CloudServe support intelligence

## 1. Document control

| Field | Value |
|---|---|
| Version | 1.0 (revised to 2.0 in the Stage 5 log) |
| Written by | Tushit Dave |
| Date | 16 November 2026 |
| Status | Approved for build (v1); superseded in part by v2 |
| Approved by | Student acting as product owner for the capstone |

## 2. The problem in one paragraph

CloudServe's support team is not short of answers; it is short of time to find them. Seven in ten tickets ask something an approved article already explains, yet customers wait most of a working day, and about half of what reaches senior engineers could have been answered from those articles. When a ticket does need an expert it arrives as a bare forward. The system must answer routine documented questions straight away from the approved articles, show where each answer came from, and pass everything sensitive, unusual or uncertain to the right person with a summary of what is known and what is not. (Stage 1, section 6.)

## 3. Who this is for

| User group | What they need | What they currently do instead | How you will know it worked |
|---|---|---|---|
| Customers raising tickets | A fast, honest answer that says it is automated and where it came from; a person for anything sensitive | Wait 8–12 h; search docs themselves (1.5) | Automatic-answer share; cited answers; no protected auto-replies |
| Tier one agents | Fewer repeat tickets; drafts with the right page attached | Private answer files, painful search (1.2) | Escalation rate falls; handoffs carry sources |
| Tier two / specialists | Escalations with a summary, sources and stated uncertainty | Re-read raw forwards (1.3) | Every escalation packet has reason, known/unknown and next step |
| Head of support | Better FCR and response time without wrong public answers; explainability for the compliance review | Reports a red SLA number (1.1) | Metrics report each run; full decision log; kill switch |

## 4. Functional requirements

| ID | Requirement | Priority | Discovery evidence | Acceptance criteria |
|---|---|---|---|---|
| FR-01 | The system shall accept email, chat, documentation-comment and forum tickets and normalise them, preserving channel and original text. | Must | Brief; 2 (channel split) | One ticket per channel normalised; Unicode preserved; empty body escalates (A2) |
| FR-02 | The system shall give every ticket exactly one terminal state, `sent` or `escalated`, with a persistent decision log. | Must | 1.1 (explainability) | Input, terminal and decision IDs reconcile 100% (A8, A9) |
| FR-03 | The system shall predict intent and urgency with a numeric confidence and alternatives, falling back to `unknown`. | Must | 1.2 (step 2), 3 | Every result carries labels and [0,1] scores (A3) |
| FR-04 | The system shall never automatically answer security, compliance, feature-request or unclear tickets. | Must | 1.3, 1.4, 2 (87 must-not tickets) | Protected false-auto = 0 |
| FR-05 | The system shall search only the approved articles and return real passage IDs with scores. | Must | 1.D1, 1.4 | Returned IDs resolve to the corpus text (A4) |
| FR-06 | The system shall escalate when evidence is absent, weak or unavailable, and never invent a citation. | Must | 1.1 ("rather said nothing"), 1.4 | No-hit and failure cases escalate (A11) |
| FR-07 | The system shall draft only from approved evidence and block drafts with unsupported claims, private data or commitments. | Must | 1.1, 1.3 (money) | An engineered unsafe case is blocked (A7) |
| FR-08 | The system shall attach to every escalation a summary, reason, known/unknown facts, candidate sources and a next step. | Must | 1.3 (Daniel) | Packet present on every escalation |
| FR-09 | The system shall change approved knowledge only through staging, review, human certification and atomic publication. | Should | 1.3 (stale snippets), 1.4 | Uncertified source never indexed |
| FR-10 | The system shall let reviewers see scores, citations, reasons, handoffs and knowledge lineage in a web UI. | Should | 1.4 (which article) | UI shows passage and version for each citation |
| FR-11 | The system shall process any compatible JSON file unattended from one command. | Must | Build Specification A9 | Arbitrary path; one result per input |
| FR-12 | The system shall emit volume, business, technical and governance metrics from the same run. | Must | 4; A10 | `metrics.json` written by the run |

## 5. Non-functional requirements

| ID | Category | Requirement | How it will be verified |
|---|---|---|---|
| NFR-01 | Latency | p95 substantive response <3 s | Harness p95; local only until a provider path is measured |
| NFR-02 | Availability | ≥99.5%; provider outage degrades to escalation | Outage injection tests; no live observation available |
| NFR-03 | Accuracy | Intent precision ≥85%, hallucination ≤5%, citation accuracy ≥95% | Per-class metrics; human review of ≥50 answers |
| NFR-04 | Privacy | Zero private data in outbound replies | Guardrail on every reply plus injected test |
| NFR-05 | Auditability | Every decision reconstructable: inputs, model, sources, thresholds, reason | Decision record fields; reconciliation |
| NFR-06 | Fairness | <5 points quality difference across tier, region and fluency | Segment report each run |
| NFR-07 | Cost | Runs at zero cost; the provider is optional | Default extractive mode with no API calls |

## 6. What is deliberately out of scope

| Not building | Why not | What would have to change |
|---|---|---|
| Account actions, refunds, credits | Contractual; Daniel says never automate money | A governed billing API and owner approval |
| Roadmap or timing answers | No approved source (Ines) | Published roadmap content with an owner |
| CRM or live channel integration | Not supplied; clean-checkout gate | A pilot with real channels |
| New documentation authoring | Content is adequate (1.D1) | Gap analysis from escalations |
| GraphRAG or ontology | 29 articles; no multi-hop questions | Labelled cross-document questions |

## 7. Assumptions and their consequences

| Assumption | Why you believe it | What happens if it is false | How you will find out |
|---|---|---|---|
| A1 The 29 articles are correct | Ines reviews them on a rotation | Correct citations to wrong advice | Human answer review; incident path |
| A2 Supplied labels are a reliable target for routing | They are the client's labels | Thresholds optimise noise | Label consistency check (**false: see Stage 5, F07**) |
| A3 A text classifier can predict answerability | Labels exist per ticket | Over-escalation | Held-out AUC (**false: AUC 0.32–0.55**) |
| A4 The validation set measures generalisation | Dataset Guide | Optimistic numbers | Overlap check (**partly false: 62/80 duplicates**) |
| A5 The hidden set has the same schema | Build Specification | Harness breaks | Arbitrary-file rehearsal with malformed rows |

## 8. Success measures

| Measure | Baseline | Target | Measured how | Reported by |
|---|---|---|---|---|
| First-contact resolution | 42% | ≥60% | Automatic answers / all tickets (offline proxy) | `metrics.json` business block |
| Time to first reply | 8–12 h | <5 min for automated replies | Processing time per ticket | `metrics.json` |
| Customer satisfaction | 3.2 / 5 | ≥4.0 | Not measurable offline; proxy rubric review | Report (stated as unmeasured) |
| Escalation rate | 58% | ≤30% | Escalated / all | `metrics.json` |
| Protected false-auto | — | 0 | Labelled must-not tickets sent | `metrics.json` governance block |

## 9. Open questions

| Question | Why it matters | Owner | Resolve by |
|---|---|---|---|
| Are identical-text label conflicts errors or hidden context? | Decides whether 90 answers were unsafe | Head of Support | Before pilot |
| Who may operate the kill switch? | Governance | Head of Support | Before pilot |
| Is Azure use acceptable versus free-tier providers? | Brief names free tiers | Course staff | Declared in report |
