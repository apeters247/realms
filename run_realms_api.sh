#!/bin/bash
# REALMS API Server Runner
# 
# Usage:
#   ./run_realms_api.sh              # Run with default settings
#   ./run_realms_api.sh --port 8080  # Run on custom port
#
# Environment variables:
#   - PORT: API server port (default: 8001)
#   - HOST: API server host (default: 0.0.0.0)
#   - WORKERS: Number of uvicorn workers (default: 1)
#   - LOG_LEVEL: Logging level (default: info)

set -e

# Default configuration
PORT="${PORT:-8001}"
HOST="${HOST:-0.0.0.0}"
WORKERS="${WORKERS:-1}"
LOG_LEVEL="${LOG_LEVEL:-info}"

echo "=========================================="
echo "REALMS API Server"
echo "=========================================="
echo "Host:        $HOST"
echo "Port:        $PORT"
echo "Workers:     $WORKERS"
echo "Log Level:   $LOG_LEVEL"
echo "=========================================="

# Ensure data directories exist
mkdir -p data/logs data/reports

# Run the API server
exec uvicorn realms.api.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --workers "$WORKERS" \
    --log-level "$LOG_LEVEL" \
    --access-log \
    "$@"