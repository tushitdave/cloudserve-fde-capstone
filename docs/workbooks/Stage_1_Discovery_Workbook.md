# Stage One: Discovery workbook — CloudServe

Completed from the five stakeholder transcripts and `development_tickets.json` (500 tickets). Figures are calculated by script from the data (commands in section 2). Row references such as **1.D2** are used by the PRD and the problem statement.

## 1. Section one: what the interviews tell you

| Row | Who | What they told you | What they appear not to know | What you want to verify in the data |
|---|---|---|---|---|
| 1.1 | Marcus Adeyemi, Head of Support | >500 tickets a week, six agents, first response 8–12 h against a 2 h agreement, FCR 42% against a 65% benchmark. First-contact resolution matters more to him than response time. "Rather it said nothing than said something wrong." Enterprise customers have a different agreement. Compliance review in the autumn; decisions must be explainable. | What tickets are actually about ("I would be guessing"). What is inside the escalations; he sees only the rate. | Intent mix; how many escalations were answerable from docs; outcomes by tier. |
| 1.2 | Sofia Restrepo, Tier One | 40–70 tickets each morning; "seven out of ten" are repeats she could answer; time goes on finding and writing. Documentation is good but search is painful. Everyone keeps a private answer file. Escalates when unsure, when not confident, or for anything security. Wants a draft plus the relevant page. Believes non-fluent tickets have the worst satisfaction. | Whether her impression of non-fluent satisfaction is true. | Repeat share; answerable share; CSAT by fluency. |
| 1.3 | Daniel Okonkwo, Tier Two | About half of what reaches him could have been resolved by tier one with confidence or the right page. Escalations arrive as raw forwards with no context. Private snippet files contain answers that are no longer right. Never automate security, account compromise, billing disputes or data location. | Exact share; how stale the private snippets are. | Share of escalated tickets answerable from docs. |
| 1.4 | Ines Varga, Technical Writer | 29 reviewed articles; agents do not use them because keyword search does not bridge customer wording ("my deployment keeps dying") to titles. Private files are unreviewed. Wants to know which article an answer came from. No content for feature requests, roadmap/timing or novel incidents. | That Sofia meant findability, not quality. | Coverage of intents by articles; vocabulary gap between tickets and titles. |
| 1.5 | Ravi Menon, Customer (business plan) | Waiting is the problem; urgency differs by ticket (pagination question vs failed deployment). He finds the doc himself half the time. Fine with automation if it is honest, cites its page and says it is automated. Believes enterprise customers get answers in about an hour. | Whether enterprise really is faster. | Resolution time and FCR by tier and urgency. |

### Where the accounts disagree

| Row | The disagreement | Who says what | How the data settles it | What follows from the answer |
|---|---|---|---|---|
| 1.D1 | Is the problem the documentation or finding it? | Ines heard Sofia say "docs are bad"; Sofia says docs are fine but unsearchable. | 357/500 (71.4%) tickets are labelled answerable from the existing 29 articles. | Findability, not content. Build retrieval over the approved articles; do not write new content first. |
| 1.D2 | How much of tier two's load is avoidable? | Marcus sees a 58% escalation rate as the cost of complexity; Daniel says about half of escalations were answerable. | Of 281 historically escalated tickets, 138 (49.1%) are answerable from docs. | Daniel is right. Automating documented answers attacks the escalation rate directly. |
| 1.D3 | Do non-fluent customers get the worst satisfaction? | Sofia: yes, "and nobody has noticed". | Mean CSAT is 3.04 for non-fluent (n=120) and 2.95 for fluent (n=380); FCR 45.8% vs 43.2%. | Not supported by historical CSAT. The risk moves to the new system: retrieval is the step likely to fail on non-fluent wording, so it must be measured (it was: section 5 and the fairness audit). |
| 1.D4 | Do enterprise customers get faster service? | Ravi: enterprise gets answers in about an hour. | Enterprise median resolution is 369 min against 141 for business; enterprise FCR is 37.3%, the lowest tier. | The perception is wrong. Enterprise tickets are slower and more often escalated, so automation must not widen any tier gap (Marcus's concern). |

### What nobody said

| What was never mentioned | Why you would have expected it | How you will check it |
|---|---|---|
| Ticket volume by channel and how channels differ | The brief stresses four channels behaving differently | Channel split and outcomes (section 2) |
| How the confidence of a reply would be shown to agents | Daniel wants to see "what I was not confident about" | Design: escalation packet with known/unknown lists |
| A way to stop the system quickly | Marcus fears public embarrassment | Governance: kill switch requirement (NFR08) |
| That the labels themselves might be inconsistent | Nobody looks at labels | Checked in build: identical text carries opposite route labels in 40 of 191 duplicate groups (F07) |

## 2. Section two: what the ticket data shows

Source: `data/supplied/development_tickets.json`, counted with Python on 16–16 November 2026.

| What to measure | Your figure | Where the figure came from | What surprised you |
|---|---|---|---|
| Total tickets | 500 | `len(rows)` | Only 216 distinct bodies: heavy templating and repetition, which matches Sofia's "same ones over and over". |
| Split by channel | Email 212, chat 155, docs comment 78, forum 55 | `channel` | Docs comments have the lowest FCR (34.6%) and the slowest median resolution (466 min), although the brief calls them "narrow and answerable". |
| Split by intent | 22 intents. Largest: data_export 29, data_residency 29, rollback_request 28. Smallest: rate_limit 13 | `labels.intent` | Fairly flat; no single dominant intent. |
| Split by urgency | Medium 226, high 146, low 128 | `labels.urgency` | High urgency has the lowest FCR (39.7%). |
| Resolved on first contact | 43.8% | `history.first_contact_resolution` | Close to Marcus's 42%. |
| Average satisfaction | 2.97 / 5 | `history.csat_rating` | Below the 3.2 Marcus quotes; the sample is worse than reported. |
| Most frequent single question | "How do I revert to an earlier revision? The release…" (14 copies) | most common body | A rollback procedure that exists as DOC-DEPLOY-002. |
| Answerable from documentation | 71.4% (357) | `labels.answerable_from_docs` | Larger than the 58% that is escalated: the answers exist. |
| Non-fluent share and outcomes | 24% (120); FCR 45.8%, CSAT 3.04 | `language_fluency` | Historically not worse (contradicts 1.2). |
| Outcomes by tier | Enterprise FCR 37.3% / median 369 min; business 48.2% / 141; standard 43.1% / 266 | `customer_tier` | Enterprise is worst on both (contradicts 1.5). |
| Repeat contacts | 21.6% | `history.repeat_contact` | Docs comments repeat at 33.3%. |
| Must never auto-respond | 87 (17.4%): security incident, compliance, feature request, unclear | `labels.must_not_auto_respond` | Matches Daniel's and Ines's categories exactly. |

## 3. Section three: where the time actually goes

Effort is estimated as the share of total historical `resolution_time_minutes`. This is elapsed time, not agent touch time, so it is an upper-bound proxy.

| Ticket category | Share of volume | Estimated share of effort | Why the two differ | Evidence |
|---|---:|---:|---|---|
| Security incident | 5.2% | 9.7% | Mean 786 min; always escalated | history.resolution_time_minutes |
| Compliance request | 5.2% | 8.4% | Mean 679 min; legal review | same |
| Feature request | 4.0% | 6.9% | Mean 724 min; no answer exists, tickets linger | same |
| Data residency | 5.8% | 7.1% | Mean 515 min; Daniel says humans get it wrong | same |
| Deployment failure | 5.4% | 6.2% | Mean 483 min; urgent for customers (Ravi) | same |
| Rate limit | 2.6% | 0.8% | Mean 122 min; simple documented answer | same |
| SSO configuration | 5.2% | 2.4% | Mean 191 min; documented procedure | same |

Protected categories consume disproportionate time but must stay human. The automation opportunity is the long tail of documented procedures, where every escalation is a wasted senior-engineer read.

### The steps an agent takes on a typical ticket (Sofia, interview 2)

| Step | What the agent does | Roughly how long | Could this be automated? |
|---|---|---|---|
| 1 | Sort queue by age, pick the oldest | <1 min | Partly: urgency prediction can reorder; it is only 50% accurate, so as a hint only. |
| 2 | Read and work out what is asked (longer for non-fluent) | 1–5 min | Yes: intent classification with calibrated confidence. |
| 3 | Search docs or a private file for the answer | Most of the time; "painful" | Yes: retrieval over approved articles. This is the core bottleneck. |
| 4 | Write the answer | 2–5 min | Yes for documented procedures: answer built from the article with citations. |
| 5 | Decide whether confident enough to send, or escalate | Varies; 40 min when unusual | Partly: deterministic rules and evidence checks decide; uncertain cases go to a person with context. |

## 4. Section four: what the client counts as success

| Measure | Who watches it | Current value | What they would call success | Confidence |
|---|---|---|---|---|
| First-contact resolution | Marcus (cares most) | 42% (sample 43.8%) | ≥60–65% | High: stated by Marcus |
| Time to first reply | Executive team via SLA | 8–12 h | <2 h SLA; brief target <5 min | High |
| Escalation rate | Marcus | 58% (sample 56.2%) | ≤30% | High |
| CSAT | Renewal conversations | 3.2 (sample 2.97) | ≥4.0 | Medium: offline only |
| Wrong answers sent | Marcus (failure condition) | Not measured | Zero confidently wrong public answers | High as a constraint |

### The sentence test

| Prompt | Your answer |
|---|---|
| This project will have been worth doing if, within three months of launch, … | the share of tickets closed without a person rises from 42% toward 60%, escalation falls from 58% toward 30%, and documented questions get a cited reply in minutes instead of 8–12 hours, with zero automatic replies on security, compliance or billing-dispute tickets. |
| We will know it did not work if we see … | wrong answers shared publicly, a rising repeat-contact rate (21.6% baseline), agents re-doing automated work, or a widening gap for non-fluent or enterprise customers. |
| The measure the client will actually be judged on internally is … | first response time against the 2-hour agreement. Marcus himself values first-contact resolution most. |

## 5. Section five: data, constraints and risk

| Data source | What it contains | Quality and gaps | Access constraints | Private data? |
|---|---|---|---|---|
| Support tickets (500 dev, 80 validation) | Text, channel, tier, region, fluency, labels, history | Templated (216 distinct bodies); 62/80 validation bodies repeat dev; labels conflict on identical text | Validation for checks only; hidden set never seen | Names and customer IDs (fictional); excluded from model features and logs |
| Documentation (29 articles) | Markdown articles with symptoms, causes, numbered steps, notes | Reviewed; `last_reviewed_days_ago` is 0 for all, so staleness cannot be tested | Approved authority; changes need certification | No |
| Past resolutions (200 reference answers) | Senior-agent answers with must_mention / must_not_claim | Development only; not passage-level evidence | Evaluation reference, never indexed | No |
| Customer records | Not supplied | — | No CRM access; no account-specific answers possible | — |

### Initial risk register

| What could go wrong | How likely | How bad | Who it affects | First thought on preventing it |
|---|---|---|---|---|
| Confidently incorrect answer | Medium | High | Customer, Sofia (angry follow-up) | Answer only from approved text with citations; escalate when unsure |
| Private information in a reply | Low | Critical | Customers, compliance | Never build replies from ticket text; scan every reply and block |
| Some customers get worse answers | Medium | Medium | Non-fluent, enterprise | Measure by segment in every run |
| Documentation goes out of date | Medium | Medium | Everyone | Version every article; human certification before publishing |
| Customer text redirects the system | Medium | High | Everyone | Treat ticket text as data; detect override attempts |

## 6. Section six: the problem statement

| Element | Your statement | Supported by |
|---|---|---|
| What the client asked for | A chatbot to answer easy tickets. | 1.1 |
| What the evidence suggests they actually need | A way to get already-approved answers to customers and agents quickly, and to hand everything else to the right person with the context already attached. | 1.D1, 1.D2, 2 (answerable 71.4%) |
| The gap | The answers exist, but nobody can find them in time. Escalations carry no context, so the hard cases are slow too. | 1.2, 1.3, 1.4 |
| Who is affected and how | Customers wait 8–12 hours for an answer in the docs. Tier one rewrites known answers. Tier two re-reads raw forwards. Enterprise customers wait longest. | 1.5, 1.D4, 3 |
| What will change if solved | Documented questions get a cited reply in minutes. Escalations arrive with a summary, sources and what was uncertain. Protected topics always go to a person. | 4 |
| Explicitly not in scope | Account-specific actions, refunds, roadmap answers, CRM integration, writing new documentation. | 1.3, 1.4 |

### The one-paragraph version

CloudServe's support team is not short of answers; it is short of time to find them. Seven in ten tickets ask something an approved article already explains, yet customers wait most of a working day, and about half of what reaches senior engineers could have been answered from those same articles. When a ticket does need an expert it arrives as a bare forward, so the expert starts from scratch. The team needs routine documented questions answered straight away from the approved articles, in a way that shows where the answer came from. It also needs everything sensitive, unusual or uncertain passed to the right person with a short summary of what is known and what is not. Security, compliance and money questions must always go to a person.
