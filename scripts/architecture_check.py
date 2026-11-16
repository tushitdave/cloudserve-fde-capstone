"""Mechanical source-boundary and committed-secret check for CI."""

import ast
import re
import sys
from pathlib import Path


def check(root: Path) -> list[str]:
    problems: list[str] = []
    production = root / "src" / "cloudserve"
    for path in production.rglob("*.py"):
        relative = path.relative_to(root)
        tree = ast.parse(path.read_text(), filename=str(path))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        if "api/routes" not in str(relative) and path.name != "main.py":
            for name in imports:
                if name.startswith(("cloudserve.api", "evaluation")):
                    problems.append(f"{relative}: forbidden production import {name}")
        if path.name == "contracts.py":
            for name in imports:
                if name.startswith(("cloudserve.storage", "cloudserve.azure", "cloudserve.knowledge_store")):
                    problems.append(f"{relative}: contract depends on adapter {name}")
    source_paths = [root / ".env.example", *production.rglob("*.py"), *(root / "scripts").glob("*.py"),
                    *(root / ".github" / "workflows").glob("*.yml")]
    credential = re.compile(r"(?im)^[ \t]*(?:AZURE_[A-Z0-9_]+_API_KEY|embedding_api_key)[ \t]*=[ \t]*['\"]?[^\s#'\"]{8,}")
    private_key = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
    for path in source_paths:
        if not path.exists():
            continue
        content = path.read_text()
        if credential.search(content) or private_key.search(content):
            problems.append(f"{path.relative_to(root)}: possible committed credential")
    return problems


if __name__ == "__main__":
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    issues = check(base)
    for issue in issues:
        print(issue, file=sys.stderr)
    if issues:
        raise SystemExit(1)
    print("Architecture boundaries and source credential patterns: OK")
