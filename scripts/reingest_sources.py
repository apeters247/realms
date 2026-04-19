"""Reset sources to 'pending' so the ingestor re-processes them with the current
prompt version.

Typical use after bumping PROMPT_VERSION:

    docker exec realms-api python -m scripts.reingest_sources --only-completed

The ingestor will pick them up on its next poll cycle. Cached Wikipedia text
(data/raw/<sha>.txt) is reused — only the LLM calls happen again.
"""
from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy import update

from realms.models import IngestionSource
from realms.utils.database import get_db_session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("realms.reingest")


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-queue ingestion sources.")
    parser.add_argument("--only-completed", action="store_true",
                        help="Only reset sources with status 'completed' (default).")
    parser.add_argument("--all", action="store_true",
                        help="Reset ALL sources regardless of status.")
    parser.add_argument("--id", type=int, default=None,
                        help="Reset only the given source id.")
    args = parser.parse_args()

    with get_db_session() as session:
        stmt = update(IngestionSource).values(
            ingestion_status="pending",
            error_log=None,
            processed_at=None,
        )
        if args.id is not None:
            stmt = stmt.where(IngestionSource.id == args.id)
        elif args.all:
            pass
        else:
            stmt = stmt.where(IngestionSource.ingestion_status == "completed")
        result = session.execute(stmt)
        session.commit()
        log.info("Reset %d sources to pending", result.rowcount)
    return 0


if __name__ == "__main__":
    sys.exit(main())
