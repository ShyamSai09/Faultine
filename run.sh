#!/usr/bin/env bash
# Faultline — start the API + the embedded Hindsight memory engine.
set -euo pipefail
cd "$(dirname "$0")"

[ -f .env ] || { echo "No .env found. Copy .env.example to .env and add an LLM key."; exit 1; }
[ -d .venv ] || { echo "No .venv. Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"; exit 1; }

exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 "$@"
