"""Compare claim verifiers: deterministic exact-span vs GPT-4o vs o3-mini (P6-03).

No human-labelled claims exist yet, so the test set is constructed: for calibration-split
tickets the system's own extractive draft is the *supported* case, and the same draft with
one fabricated but plausible claim attached to a cited line is the *unsupported* case.
Metrics: unsafe-claim recall (corrupted drafts blocked), false-block rate (clean drafts
blocked), and latency. This measures the verifier, not answer quality.

    PYTHONPATH=src:. python -m evaluation.verifier_comparison --tickets 20
"""

import argparse
import concurrent.futures
import json
import re
import time
from pathlib import Path

from cloudserve.agents import AnswerAgent, EvidenceAgent, VerificationAgent
from cloudserve.azure import ModelUnavailable
from cloudserve.classifier import classify, split_rows
from cloudserve.contracts import Ticket

OUTPUT = Path(__file__).resolve().parents[1] / "data" / "manifests" / "verifier_comparison_v1.json"
FABRICATIONS = [
    "This change also resets every API key in your organisation.",
    "Support can raise this limit to unlimited on request at no cost.",
    "The setting takes effect only after a 24-hour waiting period.",
    "You must delete and recreate the service before trying this.",
]


def corrupt(draft: str, k: int) -> str:
    lines = draft.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^\d+\. ", line) and "[" in line:
            text, cite = line.rsplit(" [", 1)
            lines[i] = f"{text} {FABRICATIONS[k % len(FABRICATIONS)]} [{cite}"
            return "\n".join(lines)
    return draft + f"\n{FABRICATIONS[k % len(FABRICATIONS)]}"


def build_cases(n: int) -> list[dict]:
    _, calibration = split_rows()
    evidence, answer = EvidenceAgent(), AnswerAgent()
    cases = []
    for row in calibration:
        if len(cases) >= n:
            break
        if not row["labels"]["answerable_from_docs"] or row["labels"]["must_not_auto_respond"]:
            continue
        ticket = Ticket.model_validate({k: v for k, v in row.items() if k not in ("labels", "history", "customer_name")})
        bundle = evidence.gather(ticket, classify(ticket))
        if not bundle.sufficient:
            continue
        passages = [bundle.passages[0], *bundle.supporting_passages]
        draft = answer.draft(ticket, passages, "extractive")
        cases.append({"ticket_id": row["ticket_id"], "passages": passages, "clean": draft, "corrupted": corrupt(draft, len(cases))})
    return cases


def run_verifier(label: str, verify, cases: list[dict]) -> dict:
    def judge(text, passages):
        started = time.perf_counter()
        try:
            supported = verify(text, passages)["supported"]
        except ModelUnavailable:
            supported = False  # fail closed
        return supported, (time.perf_counter() - started) * 1000

    jobs = [(c["clean"], c["passages"]) for c in cases] + [(c["corrupted"], c["passages"]) for c in cases]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        outcomes = list(pool.map(lambda job: judge(*job), jobs))
    n = len(cases)
    clean, corrupted = outcomes[:n], outcomes[n:]
    latencies = sorted(ms for _, ms in outcomes)
    return {"cases": n, "unsafe_claim_recall": round(sum(not ok for ok, _ in corrupted) / n, 4),
            "false_block_rate": round(sum(not ok for ok, _ in clean) / n, 4),
            "latency_ms_median": round(latencies[len(latencies) // 2], 1), "latency_ms_max": round(latencies[-1], 1)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickets", type=int, default=20)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    cases = build_cases(args.tickets)
    verifier = VerificationAgent()
    report = {"schema_version": "1.0", "method": __doc__.strip().splitlines()[2:6], "results": {
        "exact_span_deterministic": run_verifier("exact", lambda t, p: verifier.verify(t, p, "extractive"), cases),
        "gpt-4o": run_verifier("gpt-4o", lambda t, p: verifier.verify(t, p, "azure", model="gpt-4o"), cases),
        "o3-mini": run_verifier("o3-mini", lambda t, p: verifier.verify(t, p, "azure", model="o3-mini"), cases),
    }}
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    for name, values in report["results"].items():
        print(name, values)


if __name__ == "__main__":
    main()
