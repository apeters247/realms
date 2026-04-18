#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8001}"
LOG_LEVEL="${LOG_LEVEL:-info}"

mkdir -p data/logs data/reports

# Bootstrap DB schema (idempotent)
python -m scripts.bootstrap_realms_db

# Launch API
exec uvicorn realms.api.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --log-level "$LOG_LEVEL"
