"""Outbox dispatcher: deliver decided customer messages at most once, with retry and dead-letter.

Research/03: "Persist decision and delivery intent before send; protect retry with an
idempotency/outbox identifier." The delivery intent is written in the same SQLite
transaction as the decision (`Store.save`). This dispatcher sends due items through a
channel sender. The sender receives the stable `delivery_id`, so a downstream channel
can deduplicate. A sent item is never re-sent. A failed item is retried with
exponential backoff and moved to `dead_letter` after `max_attempts`.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from cloudserve.reliability import backoff_seconds


class FileChannelSender:
    """Local stand-in for the four live channels: appends each delivery to a JSONL file."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def __call__(self, delivery: dict) -> None:
        with open(self.path, "a") as handle:
            handle.write(json.dumps({"delivery_id": delivery["delivery_id"], "channel": delivery["channel"],
                                     "kind": delivery["kind"], "ticket_id": delivery["ticket_id"]}) + "\n")


def dispatch(store, sender, max_attempts: int = 5, now=time.time, limit: int = 1000) -> dict:
    sent = failed = dead = 0
    for delivery in store.due_deliveries(now(), limit):
        try:
            sender(delivery)
        except Exception as error:  # channel outage: retry later, never crash the run
            attempt = delivery["attempts"] + 1
            is_dead = attempt >= max_attempts
            store.mark_failed(delivery["delivery_id"], f"{type(error).__name__}: {error}",
                              now() + backoff_seconds(attempt), is_dead)
            failed += 1
            dead += is_dead
            continue
        sent += store.mark_delivered(delivery["delivery_id"])
    return {"sent": sent, "failed": failed, "dead_lettered": dead, "status": store.outbox_counts()}
