#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
CS_PYTHON="${CLOUDSERVE_PYTHON:-python3}"
"$CS_PYTHON" scripts/architecture_check.py
PYTHONPATH=src:. "$CS_PYTHON" -m pytest -q
npm --prefix frontend run build
