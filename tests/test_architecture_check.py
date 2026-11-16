import subprocess
import sys
from pathlib import Path


CHECKER = Path(__file__).resolve().parents[1] / "scripts" / "architecture_check.py"


def test_architecture_check_passes_project():
    result = subprocess.run([sys.executable, str(CHECKER)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_architecture_check_rejects_forbidden_import_and_secret(tmp_path):
    module = tmp_path / "src" / "cloudserve" / "sample.py"
    module.parent.mkdir(parents=True)
    module.write_text("import cloudserve.api.routes.tickets\n")
    (tmp_path / ".env.example").write_text("AZURE_GPT_4o_API_KEY=examplebutshouldnotcommit123\n")
    result = subprocess.run([sys.executable, str(CHECKER), str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 1
    assert "forbidden production import" in result.stderr
    assert "possible committed credential" in result.stderr
