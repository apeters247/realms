"""Load data/seed_sources.yaml into ingestion_sources table (idempotent)."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import yaml
from sqlalchemy import select

from realms.models import IngestionSource
from realms.utils.database import get_db_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("realms.seed_sources")

SEED_FILE = Path(__file__).resolve().parents[1] / "data" / "seed_sources.yaml"


def main() -> int:
    if not SEED_FILE.exists():
        log.error("Seed file not found: %s", SEED_FILE)
        return 1

    doc = yaml.safe_load(SEED_FILE.read_text())
    sources = doc.get("sources", [])

    added = 0
    skipped = 0
    with get_db_session() as session:
        for src in sources:
            existing = session.execute(
                select(IngestionSource).where(IngestionSource.url == src["url"])
            ).scalar_one_or_none()
            if existing is not None:
                skipped += 1
                continue
            row = IngestionSource(
                source_type="internet",
                source_name=src["name"],
                url=src["url"],
                retrieval_method="wikipedia_rest_api",
                language="en",
                credibility_score=0.70,
                peer_reviewed=False,
                ingestion_status="pending",
                ethical_considerations=(
                    f"Tradition: {src.get('tradition', 'unknown')}. "
                    "Wikipedia is a tertiary source; cross-reference with primary ethnography."
                ),
            )
            session.add(row)
            added += 1
        session.commit()

    log.info("Seed sources: added=%d skipped=%d total=%d", added, skipped, len(sources))
    return 0


if __name__ == "__main__":
    sys.exit(main())
