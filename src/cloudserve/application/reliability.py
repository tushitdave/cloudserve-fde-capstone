"""Bounded retry with exponential backoff and jitter (Research/02 governed ingestion:
"Transient failures retry with exponential backoff and jitter; exhausted work goes to a
dead-letter state and review queue"; Research/03: delivery protected by an outbox).
"""

from __future__ import annotations

import random
import sqlite3
import time

from cloudserve.adapters.azure.openai_client import ModelUnavailable
from cloudserve.config import setting

RETRYABLE = (ModelUnavailable, sqlite3.OperationalError, TimeoutError, ConnectionError, OSError)


def backoff_seconds(attempt: int, base: float | None = None, cap: float = 30.0, rng: random.Random | None = None) -> float:
    """Full-jitter exponential backoff: uniform(0, min(cap, base * 2**attempt))."""
    base = float(setting("CLOUDSERVE_BACKOFF_BASE_S", "0.5")) if base is None else base
    ceiling = min(cap, base * (2 ** attempt))
    return (rng or random).uniform(0, ceiling)


def failure_category(error: BaseException) -> str:
    if isinstance(error, ModelUnavailable):
        return "model_unavailable"
    if isinstance(error, sqlite3.OperationalError):
        return "storage_busy"
    if isinstance(error, (TimeoutError, ConnectionError)):
        return "transient_network"
    if isinstance(error, OSError):
        return "io_error"
    return "permanent"


def with_retries(fn, max_attempts: int = 3, sleep=time.sleep, on_retry=None):
    """Call fn(); retry only retryable errors. Returns (value, attempts). Re-raises the last error when exhausted."""
    for attempt in range(max_attempts):
        try:
            return fn(), attempt + 1
        except RETRYABLE as error:
            if attempt == max_attempts - 1:
                raise
            if on_retry:
                on_retry(attempt + 1, error)
            sleep(backoff_seconds(attempt))
    raise RuntimeError("unreachable")
