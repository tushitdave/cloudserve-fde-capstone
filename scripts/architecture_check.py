"""Mechanical hexagonal-boundary and committed-secret check for CI.

Layer rules (Research/02 "hexagonal code structure"):
  domain/         may import only cloudserve.domain and cloudserve.config (no adapters, application,
                  orchestration, ports or api)
  ports/          may import only cloudserve.domain
  adapters/       must not import application, orchestration or api
  application/    must not import api
  orchestration/  must not import api
  anywhere        production code must not import cloudserve.api (except api/ and main.py) or evaluation
Compatibility aliases (old flat module paths that re-point to the new module) are skipped.
"""

import ast
import re
import sys
from pathlib import Path

RULES = {
    "domain": ("cloudserve.adapters", "cloudserve.application", "cloudserve.orchestration", "cloudserve.ports", "cloudserve.api"),
    "ports": ("cloudserve.adapters", "cloudserve.application", "cloudserve.orchestration", "cloudserve.api"),
    "adapters": ("cloudserve.application", "cloudserve.orchestration", "cloudserve.api"),
    "application": ("cloudserve.api",),
    "orchestration": ("cloudserve.api",),
}


def _imports(tree):
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def check(root: Path) -> list[str]:
    problems: list[str] = []
    production = root / "src" / "cloudserve"
    for path in production.rglob("*.py"):
        relative = path.relative_to(root)
        text = path.read_text()
        if "sys.modules[__name__] = _module" in text:
            continue  # compatibility alias
        imports = _imports(ast.parse(text, filename=str(path)))
        inner = path.relative_to(production).parts
        layer = inner[0] if len(inner) > 1 else None
        for name in imports:
            if layer != "api" and path.name != "main.py" and name.startswith(("cloudserve.api", "evaluation")):
                problems.append(f"{relative}: forbidden production import {name}")
            if layer in RULES and name.startswith(RULES[layer]):
                problems.append(f"{relative}: layer '{layer}' must not import {name}")
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
    print("Hexagonal layer boundaries and source credential patterns: OK")
