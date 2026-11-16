#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
CS_PYTHON="${CLOUDSERVE_PYTHON:-python3}"
CS_INPUT="${1:-data/supplied/development_tickets.json}"
CS_OUTPUT="${2:-evaluation/reports/local-run}"
PYTHONPATH=src:. "$CS_PYTHON" -m evaluation.harness --input "$CS_INPUT" --output "$CS_OUTPUT" --mode extractive
