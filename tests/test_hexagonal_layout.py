"""Hexagonal layout: adapters satisfy ports, old import paths alias the moved modules, layers are enforced."""

import subprocess
import sys
from pathlib import Path

from cloudserve import ports

CHECKER = Path(__file__).resolve().parents[1] / "scripts" / "architecture_check.py"


def test_adapters_satisfy_ports(tmp_path):
    from cloudserve.adapters.persistence.knowledge_store import KnowledgeStore
    from cloudserve.adapters.persistence.ticket_store import Store

    assert isinstance(Store(tmp_path / "t.sqlite"), ports.TicketRepository)
    assert isinstance(KnowledgeStore(tmp_path / "k.sqlite"), ports.KnowledgeRepository)


def test_old_paths_are_the_same_module_objects():
    import cloudserve.policy as old_policy
    import cloudserve.service as old_service
    from cloudserve.application.use_cases import process_ticket
    from cloudserve.domain.policies import policy

    assert old_policy is policy and old_service is process_ticket


def test_domain_importing_an_adapter_is_rejected(tmp_path):
    module = tmp_path / "src" / "cloudserve" / "domain" / "bad.py"
    module.parent.mkdir(parents=True)
    module.write_text("from cloudserve.adapters.persistence.ticket_store import Store\n")
    result = subprocess.run([sys.executable, str(CHECKER), str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 1 and "layer 'domain' must not import" in result.stderr
