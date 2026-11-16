#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
CS_PYTHON="${CLOUDSERVE_PYTHON:-python3}"
CS_API_PORT="${CLOUDSERVE_API_PORT:-8001}"
PYTHONPATH=src "$CS_PYTHON" -m uvicorn cloudserve.main:app --host 127.0.0.1 --port "$CS_API_PORT" --reload &
CS_API_PID=$!
trap 'kill "$CS_API_PID" 2>/dev/null || true' EXIT INT TERM
npm --prefix frontend run dev -- --host 127.0.0.1
