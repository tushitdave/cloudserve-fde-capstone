"""Isolated live-demo injection showing that an unsupported promise is blocked."""

import json
import tempfile
from pathlib import Path

from cloudserve.config import supplied
from cloudserve.service import TicketService


if __name__ == "__main__":
    row = next(item for item in json.loads(supplied("development_tickets.json").read_text()) if item["ticket_id"] == "DEV-0026")
    with tempfile.TemporaryDirectory(prefix="cloudserve-guardrail-") as directory:
        service = TicketService(Path(directory) / "demo.sqlite")
        service.answer.draft = lambda _ticket, passages, _mode: f"A refund has been issued. [{passages[0].passage_id}]"
        result = service.process({key: value for key, value in row.items() if key not in {"labels", "history", "customer_name"}}, mode="extractive")
        print(json.dumps({"ticket_id": result.ticket_id, "terminal_state": result.terminal_state,
                          "guardrail_findings": result.guardrail_findings,
                          "customer_message": result.customer_message,
                          "decision_reason_codes": result.decision.reason_codes}, indent=2))
