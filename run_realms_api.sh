#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8001}"
LOG_LEVEL="${LOG_LEVEL:-info}"

mkdir -p data/logs data/reports

# Bootstrap DB schema (idempotent) and apply any pending migrations
python -m scripts.bootstrap_realms_db
if [ -f /app/alembic.ini ]; then
    alembic upgrade head || echo "alembic upgrade failed — continuing"
fi

# Launch API
exec uvicorn realms.api.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --log-level "$LOG_LEVEL"
