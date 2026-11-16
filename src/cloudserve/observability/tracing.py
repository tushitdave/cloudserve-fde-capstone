"""OpenTelemetry tracing, per-agent time budgets and stage timing.

Research/02: "Record trace_id, ticket_id, source/index version, classifier/model/
prompt/policy versions, stage timing … Keep raw customer text out of metric labels
and unprotected traces." and Research/10: each agent has a wall-clock timeout and a
failure-to-escalation behaviour.

Every LangGraph node runs inside an OpenTelemetry span carrying only identifiers,
versions, durations and status (never ticket text). Each node also has a time budget
from `policy_v2.json` (`agent_budgets_ms`); a node that exceeds it raises
`AgentTimeout`, which the service turns into a logged `processing_failure` escalation.
Spans are kept in memory for the run (the batch harness writes them to
`traces.jsonl`); set `CLOUDSERVE_OTEL_CONSOLE=1` to also print them.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import threading
import time
from functools import lru_cache

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

SERVICE_NAME = "cloudserve-ticket-pipeline"


class AgentTimeout(TimeoutError):
    def __init__(self, stage: str, budget_ms: int):
        super().__init__(f"{stage} exceeded its {budget_ms} ms budget")
        self.stage = stage
        self.budget_ms = budget_ms


@lru_cache(maxsize=1)
def _provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    provider = TracerProvider(resource=Resource.create({"service.name": SERVICE_NAME}))
    memory = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(memory))
    if os.environ.get("CLOUDSERVE_OTEL_CONSOLE") == "1":
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    return provider, memory


def tracer():
    return _provider()[0].get_tracer("cloudserve")


def finished_spans() -> list[dict]:
    """Return and clear the in-memory spans as plain dicts (identifiers and timings only)."""
    memory = _provider()[1]
    spans = memory.get_finished_spans()
    memory.clear()
    out = []
    for span in spans:
        out.append({"name": span.name, "trace_id": format(span.context.trace_id, "032x"),
                    "span_id": format(span.context.span_id, "016x"),
                    "parent_span_id": format(span.parent.span_id, "016x") if span.parent else None,
                    "duration_ms": round((span.end_time - span.start_time) / 1e6, 3),
                    "status": span.status.status_code.name, "attributes": dict(span.attributes or {})})
    return out


_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=8, thread_name_prefix="agent")
_LOCAL = threading.local()


def run_with_budget(stage: str, budget_ms: int, fn, *args):
    """Run one bounded step; on budget exhaustion the caller escalates (the worker thread is abandoned)."""
    future = _EXECUTOR.submit(fn, *args)
    try:
        return future.result(timeout=budget_ms / 1000)
    except concurrent.futures.TimeoutError as error:
        raise AgentTimeout(stage, budget_ms) from error


def traced_stage(stage: str, agent: str, budget_ms: int, fn, run, attributes: dict | None = None):
    """Run `fn(state)` in a span with a time budget; records the duration on `run.stage_timings_ms`."""
    started = time.perf_counter()
    with tracer().start_as_current_span(f"cloudserve.{stage}") as span:
        span.set_attribute("cloudserve.ticket_id", run.ticket.ticket_id)
        span.set_attribute("cloudserve.trace_id", run.trace_id)
        span.set_attribute("cloudserve.agent", agent)
        span.set_attribute("cloudserve.budget_ms", budget_ms)
        span.set_attribute("cloudserve.mode", run.mode)
        for key, value in (attributes or {}).items():
            span.set_attribute(f"cloudserve.{key}", value)
        try:
            result = run_with_budget(stage, budget_ms, fn)
            span.set_attribute("cloudserve.next", getattr(run, "next", ""))
            return result
        except Exception as error:
            span.set_status(trace.Status(trace.StatusCode.ERROR, type(error).__name__))
            span.set_attribute("cloudserve.error", type(error).__name__)
            raise
        finally:
            run.stage_timings_ms[stage] = round((time.perf_counter() - started) * 1000, 2)


def write_jsonl(path, spans: list[dict]) -> None:
    with open(path, "a") as handle:
        for span in spans:
            handle.write(json.dumps(span) + "\n")
