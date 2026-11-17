"""Ports: the interfaces the application and orchestration layers depend on.

Adapters implement them (SQLite persistence, Chroma/TF-IDF retrieval, scikit-learn
classifier, Azure OpenAI, channel senders). They are structural `Protocol`s, so an
adapter satisfies a port by shape; `tests/test_hexagonal_layout.py` checks that the
production adapters do.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from cloudserve.domain.models.contracts import Classification, HumanResolution, Passage, Ticket, TicketResult


@runtime_checkable
class TicketRepository(Protocol):
    def get(self, ticket_id: str) -> tuple[str, TicketResult] | None: ...
    def save(self, input_hash: str, result: TicketResult, events: list[tuple[str, dict]], tenant_id: str = ..., channel: str = ...) -> None: ...
    def events(self, ticket_id: str) -> list[dict]: ...
    def resolve_escalation(self, resolution: HumanResolution) -> HumanResolution: ...
    def due_deliveries(self, now: float, limit: int = ...) -> list[dict]: ...
    def mark_delivered(self, delivery_id: str) -> bool: ...


@runtime_checkable
class KnowledgeRepository(Protocol):
    def active_documents(self) -> list[dict]: ...
    def revision(self) -> int: ...
    def stage(self, job_id: str, doc: dict, source_hash: str, status: str, intake: dict, steward: dict) -> dict: ...
    def publish(self, job_id: str, operator: str) -> dict: ...


class Retriever(Protocol):
    def __call__(self, query: str, limit: int, allowed_doc_ids: set[str] | None, strategy: str,
                 role: str = ...) -> tuple[list[Passage], str, str | None]: ...


class IntentClassifier(Protocol):
    def __call__(self, ticket: Ticket) -> Classification: ...


class LanguageModel(Protocol):
    def __call__(self, messages: list[dict], model: str = ..., timeout: int = ...) -> str: ...


class ChannelSender(Protocol):
    def __call__(self, delivery: dict) -> None: ...
