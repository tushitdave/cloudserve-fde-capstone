import pytest

from cloudserve import azure
from cloudserve.config import runtime_dir
from cloudserve.service import TicketService


def test_extract_mode_starts_without_azure_config(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDSERVE_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("CLOUDSERVE_MODEL_MODE", "extractive")
    assert runtime_dir() == tmp_path
    result = TicketService().process({"ticket_id": "CONFIG-1", "channel": "chat", "body": "I need help."})
    assert result.terminal_state in {"sent", "escalated"}


def test_missing_azure_secrets_fail_clearly_without_network(monkeypatch):
    monkeypatch.setattr(azure, "setting", lambda *args: "")
    with pytest.raises(azure.ModelUnavailable, match="gpt-4o is not configured"):
        azure.chat([{"role": "user", "content": "Hello"}])
    with pytest.raises(azure.ModelUnavailable, match="embedding deployment is not configured"):
        azure.embed(["Hello"])
