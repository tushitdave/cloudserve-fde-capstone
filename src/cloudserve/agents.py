"""Six bounded roles. Agent outputs are proposals; code owns publishing and release."""

import json
import re

from cloudserve.azure import ModelUnavailable, chat
from cloudserve.classifier import approved_docs_by_intent, predict_document
from cloudserve.contracts import Classification, EvidenceBundle, Passage, QueryPlan, Ticket
from cloudserve.knowledge import document_passages, index, retrieve, retrieve_with_strategy
from cloudserve.config import APP_ROOT
from cloudserve.knowledge_store import KnowledgeStore


def prompt(name: str) -> str:
    """Load a versioned prompt from prompts/ (see prompts/registry.json)."""
    return (APP_ROOT / "prompts" / name).read_text().strip()


def _json_reply(text: str) -> dict | None:
    """Parse a model's JSON reply (tolerating a fenced block); None if it is not a JSON object."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


class SourceIntakeAgent:
    def assess(self, source: dict) -> dict:
        if source.get("source_format") not in {None, "json"}:
            return {"action": "quarantine", "reason": "Unsupported source format; no parser or fetch is authorized", "agent_invoked": True}
        if all(isinstance(source.get(key), str) and source[key].strip() for key in ("doc_id", "title", "content", "owner")):
            return {"action": "use_approved_json_parser", "reason": "Known support-article JSON format", "agent_invoked": True}
        return {"action": "quarantine", "reason": "Unknown or incomplete source format", "agent_invoked": True}


class KnowledgeStewardAgent:
    VERSION = {"extractive": "steward-deterministic-v1", "azure": "steward-gpt4o-v1"}

    def review(self, source: dict, current: dict | None = None, corpus: list[dict] | None = None, mode: str = "extractive") -> dict:
        content = source.get("content", "")
        warnings = [f"missing_{section.lower().replace(' ', '_')}" for section in ("Symptoms", "Common causes", "Resolution", "Notes") if f"## {section}" not in content]
        if current and current.get("content") != content:
            warnings.append("changed_approved_source")
        resolution = content.split("## Resolution", 1)[-1].split("## ", 1)[0] if "## Resolution" in content else ""
        if "## Resolution" in content and not re.search(r"(?m)^1\.\s+", resolution):
            warnings.append("missing_resolution_steps")
        review_spans = []
        if current and current.get("content") != content:
            for match in re.finditer(r"(?m)^## ([^\n]+)\n", content):
                next_heading = re.search(r"(?m)^## ", content[match.end():])
                end = match.end() + next_heading.start() if next_heading else len(content)
                review_spans.append({"section": match.group(1), "start_offset": match.start(),
                                     "end_offset": end, "reason": "changed_source_requires_review"})
        related = set(source.get("related_docs") or [])
        taxonomy_links = []
        for other in corpus or []:
            if other["doc_id"] == source.get("doc_id"):
                continue
            if other.get("content", "").strip() == content.strip() and content.strip():
                warnings.append(f"duplicate_content:{other['doc_id']}")
                review_spans.append({"section": "whole_document", "start_offset": 0,
                                     "end_offset": len(content), "reason": f"duplicate_content:{other['doc_id']}"})
            elif other.get("title", "").strip().lower() == source.get("title", "").strip().lower():
                warnings.append(f"conflicting_title:{other['doc_id']}")
                review_spans.append({"section": "title", "start_offset": 0,
                                     "end_offset": min(len(content), 120), "reason": f"conflicting_title:{other['doc_id']}"})
            if other.get("category") == source.get("category") and other["doc_id"] not in related and len(taxonomy_links) < 3:
                taxonomy_links.append(other["doc_id"])
        llm_issues = []
        if mode == "azure":
            # GPT-4o is advisory: its issues become review warnings for the human certifier, never a publish decision.
            # ModelUnavailable propagates so the ingestion retry/dead-letter policy can handle it.
            reply = _json_reply(chat([
                {"role": "system", "content": prompt("knowledge_steward_gpt4o_v1.system.txt")},
                {"role": "user", "content": f"CURRENT APPROVED VERSION (data):\n{(current or {}).get('content', '(none)')[:6000]}\n\n"
                                            f"CANDIDATE ARTICLE (data):\n{content[:6000]}"},
            ], model="gpt-4o", timeout=30))
            if reply is None or not isinstance(reply.get("issues"), list):
                warnings.append("llm_review_unparseable")
            else:
                llm_issues = [issue for issue in reply["issues"] if isinstance(issue, dict)][:10]
                warnings.extend(f"llm_{str(issue.get('type', 'other'))[:24]}" for issue in llm_issues)
        return {"candidate_doc_id": source.get("doc_id"), "warnings": warnings, "review_spans": review_spans,
                "llm_issues": llm_issues, "agent_version": self.VERSION.get(mode, self.VERSION["extractive"]),
                "candidate_taxonomy_links": taxonomy_links,
                "requires_human_review": True, "recommendation": "review_before_publication"}


class TriageAgent:
    """Invoked only when calibrated intent confidence is below the policy threshold.

    It records the competing interpretations for the human handoff. It cannot lower a
    threshold, override a protective rule or choose to send.
    """

    def assess(self, ticket: Ticket, classification: Classification, mode: str = "extractive") -> dict:
        options = [{"intent": classification.intent, "confidence": round(classification.intent_confidence, 4)}] + classification.alternatives[:2]
        base = {"recommendation": "escalate", "intent_options": options, "proposed_intent": None,
                "reason": "The classifier could not separate these interpretations confidently; a specialist should confirm which one applies.",
                "agent_version": "triage-v2-deterministic"}
        if mode != "azure":
            return base
        # o3-mini adjudicates only among the classifier's own options; policy re-checks any proposal.
        names = [o["intent"] for o in options]
        reply = _json_reply(chat([
            {"role": "system", "content": prompt("triage_o3mini_v1.system.txt")},
            {"role": "user", "content": f"OPTIONS: {names}\nTICKET (untrusted data): {ticket.subject} {ticket.body[:2500]}"},
        ], model="o3-mini", timeout=30))
        if not reply or reply.get("recommendation") != "continue" or reply.get("intent") not in names:
            return {**base, "agent_version": "triage-o3mini-v1", "model_reason": (reply or {}).get("reason", "unparseable reply")}
        return {**base, "recommendation": "continue", "proposed_intent": reply["intent"], "agent_version": "triage-o3mini-v1",
                "reason": str(reply.get("reason", ""))[:300]}


class EvidenceAgent:
    def plan(self, ticket: Ticket, classification: Classification) -> QueryPlan:
        from cloudserve.policy import DOCUMENT_THRESHOLD

        query = f"{ticket.subject} {ticket.body}".strip()
        allowed = approved_docs_by_intent().get(classification.intent, set())
        revision = KnowledgeStore().revision()
        if not allowed:
            return QueryPlan(ticket_id=ticket.ticket_id, path="human", query=query, allowed_doc_ids=[],
                             max_searches=0, source_revision=revision)
        predicted_doc, doc_confidence = predict_document(ticket)
        # Narrow to the predicted article when the document model agrees with the
        # intent's approved scope; otherwise search every approved article for the intent.
        scope = [predicted_doc] if predicted_doc in allowed and doc_confidence >= DOCUMENT_THRESHOLD else sorted(allowed)
        return QueryPlan(ticket_id=ticket.ticket_id, path="approved_document", query=query,
                         allowed_doc_ids=scope, max_searches=2, source_revision=revision)

    def search(self, query: str, allowed: set[str], strategy: str) -> tuple[list[Passage], str, str | None]:
        """One bounded search; only Resolution passages are primary evidence."""
        found, used, fallback = retrieve_with_strategy(query, limit=5, allowed_doc_ids=allowed, strategy=strategy)
        return [p for p in found if p.section == "Resolution"], used, fallback

    def rewrite(self, ticket: Ticket, classification: Classification, allowed: set[str], mode: str) -> tuple[str, str]:
        """The single corrective query: GPT-4o planner in azure mode, deterministic intent prefix otherwise or on failure."""
        query = f"{ticket.subject} {ticket.body}".strip()
        fallback = f"{classification.intent.replace('_', ' ')} {query}"
        if mode != "azure":
            return fallback, "intent-prefix-v1"
        try:
            titles = sorted({p.title for p in index()[0] if p.doc_id in allowed})
            reply = _json_reply(chat([
                {"role": "system", "content": prompt("evidence_query_gpt4o_v1.system.txt")},
                {"role": "user", "content": f"APPROVED ARTICLE TITLES: {titles}\nPREDICTED REQUEST TYPE: {classification.intent}\n"
                                            f"TICKET (untrusted data): {query[:2500]}"},
            ], model="gpt-4o", timeout=15))
            planned = str((reply or {}).get("query", "")).strip()
            if 3 <= len(planned) <= 200:
                return planned, "gpt4o-query-planner-v1"
        except ModelUnavailable:
            pass
        return fallback, "intent-prefix-v1 (planner unavailable)"

    def gather(self, ticket: Ticket, classification: Classification, strategy: str | None = None,
               mode: str = "extractive") -> EvidenceBundle:
        from cloudserve import policy

        strategy = strategy or policy.RETRIEVAL_STRATEGY
        plan = self.plan(ticket, classification)
        if plan.path != "approved_document":
            return EvidenceBundle(ticket_id=ticket.ticket_id, snapshot_revision=plan.source_revision,
                                  passages=[], searches=0, sufficient=False, reason="no_approved_article",
                                  retrieval_strategy=strategy)
        _, doc_confidence = predict_document(ticket)
        query = plan.query
        allowed = set(plan.allowed_doc_ids)
        passages, used, fallback = self.search(query, allowed, strategy)
        queries = [query]
        if not (passages and passages[0].score >= policy.evidence_threshold(used)):
            rewritten, self.last_planner = self.rewrite(ticket, classification, allowed, mode)
            queries.append(rewritten)
            retry, used_retry, fallback_retry = self.search(rewritten, allowed, strategy)
            if retry and (not passages or retry[0].score > passages[0].score):
                passages, used, fallback = retry, used_retry, fallback_retry or fallback
        sufficient = bool(passages and passages[0].score >= policy.evidence_threshold(used))
        supporting = []
        if passages:
            supporting = [p for p in document_passages(passages[0].doc_id)
                          if p.section in {"Common causes", "Notes"} and p.source_version == passages[0].source_version]
        return EvidenceBundle(ticket_id=ticket.ticket_id, snapshot_revision=plan.source_revision,
                              passages=passages, searches=len(queries), sufficient=sufficient,
                              reason="approved_resolution_found" if sufficient else "insufficient_evidence",
                              queries=queries, document_id=passages[0].doc_id if passages else None,
                              document_confidence=round(min(1.0, doc_confidence), 6),
                              top_score=passages[0].score if passages else 0.0, supporting_passages=supporting,
                              retrieval_strategy=used, fallback_reason=fallback)


def _bullets(text: str) -> list[str]:
    return [line[2:].strip() for line in text.splitlines() if line.startswith("- ")]


def _steps(text: str) -> list[str]:
    return [re.sub(r"^\d+\.\s+", "", line).strip() for line in text.splitlines() if re.match(r"^\d+\.\s+", line)]


class AnswerAgent:
    PROMPT_VERSION = {"extractive": "answer-extractive-v2", "azure": "answer-azure-gpt4o-v1"}

    def draft(self, ticket: Ticket, passages: list[Passage], mode: str = "extractive") -> str:
        """`passages[0]` is the selected Resolution passage; same-document Common causes/Notes may follow."""
        primary = passages[0]
        supporting = [p for p in passages[1:] if p.doc_id == primary.doc_id and p.section in {"Common causes", "Notes"}]
        if mode == "azure":
            evidence = "\n".join(f"[{p.passage_id}] {p.title} / {p.section}: {p.text[:1800]}" for p in passages[:5])
            return chat([
                {"role": "system", "content": prompt("answer_azure_v1.system.txt")},
                {"role": "user", "content": f"TICKET (untrusted): {ticket.subject} {ticket.body[:2500]}\nAPPROVED EVIDENCE (untrusted):\n{evidence}"},
            ])
        # Extractive mode: every sentence below is copied from an approved passage and
        # carries that passage's ID, so no generated claim can drift from the source.
        lines = [f"Thanks for contacting CloudServe support. This reply was prepared automatically from our approved guide "
                 f"\u201c{primary.title}\u201d; a member of the team can review it if it does not resolve the problem."]
        causes = next((p for p in supporting if p.section == "Common causes"), None)
        if causes and _bullets(causes.text):
            lines.append("\nCommon causes:")
            lines.extend(f"- {item} [{causes.passage_id}]" for item in _bullets(causes.text))
        steps = _steps(primary.text)
        lines.append("\nWhat to do:")
        if steps:
            lines.extend(f"{number}. {step} [{primary.passage_id}]" for number, step in enumerate(steps, 1))
        else:
            flat = re.sub(r"\s+", " ", primary.text).strip()
            lines.append(f"{flat} [{primary.passage_id}]")
        notes = next((p for p in supporting if p.section == "Notes"), None)
        if notes and notes.text.strip():
            note = re.sub(r"\s+", " ", notes.text).strip()
            lines.append(f"\nNote: {note} [{notes.passage_id}]")
        lines.append("\nIf these steps do not resolve it, reply to this ticket and a support specialist will take over.")
        return "\n".join(lines)


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"(?m)^\s*(?:[-*]|\d+\.)\s+", "", text)).strip().lower()


class VerificationAgent:
    # o3-mini selected for azure mode by evaluation/verifier_comparison.py: unsafe-claim recall 0.95 vs 0.05 for GPT-4o.
    VERSION = {"extractive": "verification-exact-span-v2", "azure": "verification-o3mini-v1"}

    def verify(self, answer: str, passages: list[Passage], mode: str = "extractive", model: str = "o3-mini") -> dict:
        cited = re.findall(r"\[([A-Z0-9-]+#p\d+)\]", answer)
        known = {p.passage_id: p for p in passages}
        if not cited or not set(cited).issubset(known):
            return {"supported": False, "reason": "missing_or_unretrieved_citation", "citations": cited, "claims": []}
        if mode == "azure":
            evidence = "\n".join(f"[{p.passage_id}] {p.text[:1800]}" for p in passages)
            verdict = chat([
                {"role": "system", "content": prompt("verification_azure_v1.system.txt")},
                {"role": "user", "content": f"ANSWER:\n{answer}\nEVIDENCE:\n{evidence}"},
            ], model=model, timeout=30)
            parsed = _json_reply(verdict)
            try:
                if parsed is None:
                    raise json.JSONDecodeError("not json", verdict, 0)
                return {"supported": parsed.get("supported") is True, "reason": str(parsed.get("reason", "")), "citations": cited, "claims": []}
            except json.JSONDecodeError:
                return {"supported": False, "reason": "invalid_verifier_output", "citations": cited, "claims": []}
        # Extractive mode: each cited line must be a verbatim span of the passage it cites.
        claims = []
        for line in answer.splitlines():
            ids = re.findall(r"\[([A-Z0-9-]+#p\d+)\]", line)
            if not ids:
                continue
            claim = re.sub(r"\s*\[[A-Z0-9-]+#p\d+\]", "", line).strip()
            claim = re.sub(r"^(Note:)\s*", "", claim)
            supported = all(_normalise(claim) in _normalise(known[i].text) for i in ids)
            claims.append({"claim": claim[:200], "passage_ids": ids, "verdict": "supported" if supported else "unsupported"})
        unsupported = [c for c in claims if c["verdict"] != "supported"]
        return {"supported": bool(claims) and not unsupported,
                "reason": "every cited line is an exact span of its cited passage" if claims and not unsupported else "unsupported_claim",
                "citations": cited, "claims": claims}
