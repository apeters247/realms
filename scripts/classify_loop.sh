#!/usr/bin/env bash
# Long-running wrapper around classify_all_cooccurrence.py that:
#   - starts the classifier,
#   - exits cleanly when it hits the daily cap (via stopped_reason=daily_cap),
#   - sleeps 15 min, retries,
#   - loops indefinitely, making steady daily progress through the 97k
#     co-occurrence edge backlog.
#
# Run detached:
#   docker exec -d realms-api bash /app/scripts/classify_loop.sh
#
# Stop:
#   docker exec realms-api pkill -f classify_loop.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="/app/data/classify_loop.log"
echo "[$(date -Is)] classify_loop starting" >> "$LOG"

while true; do
    echo "[$(date -Is)] launching classifier (cross-tradition pass)" >> "$LOG"
    # --cross-tradition-only first (fastest to meaningful graph improvement),
    # sleep 4.5s between edges so we stay under 16 req/min free-tier cap,
    # resume from last checkpoint.
    python -m scripts.classify_all_cooccurrence \
        --cross-tradition-only \
        --sleep-ms 4500 \
        --min-confidence 0.72 \
        2>&1 | tee -a "$LOG"

    # Whatever the reason, sleep 15 min before the next attempt.
    # If it was the daily cap, we'll hit the reset at UTC midnight-ish.
    # If it was a crash, 15 min is enough to recover.
    echo "[$(date -Is)] classifier exited, sleeping 900s" >> "$LOG"
    sleep 900
done
