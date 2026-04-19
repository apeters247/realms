"""Seed Internet Archive ingestion sources from a curated YAML list.

Unlike PubMed, archive.org items are added by explicit curator decision —
the content is ethnographic monographs, folklore collections, and missionary
records. The config lives in data/archive_seeds.yaml.

Usage (inside container):
    docker exec realms-api python -m scripts.seed_archive_sources
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml
from sqlalchemy import select

from realms.models import IngestionSource
from realms.utils.database import get_db_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("realms.seed_archive")

SEED_FILE = Path(__file__).resolve().parents[1] / "data" / "archive_seeds.yaml"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not SEED_FILE.exists():
        log.error("Seed file not found: %s", SEED_FILE)
        return 1

    doc = yaml.safe_load(SEED_FILE.read_text())
    items = doc.get("items", []) or []

    added = 0
    skipped = 0
    with get_db_session() as session:
        for item in items:
            identifier = item.get("identifier")
            if not identifier:
                continue
            url = f"https://archive.org/details/{identifier}"
            existing = session.execute(
                select(IngestionSource).where(IngestionSource.url == url)
            ).scalar_one_or_none()
            if existing is not None:
                skipped += 1
                continue
            if args.dry_run:
                log.info("[DRY] would add archive.org %s", identifier)
                continue
            row = IngestionSource(
                source_type="archive_org",
                source_name=item.get("title") or identifier,
                url=url,
                authors=item.get("authors") or None,
                publication_year=item.get("year"),
                journal_or_venue=item.get("publisher"),
                ingestion_status="pending",
                language=item.get("language", "en"),
                peer_reviewed=bool(item.get("peer_reviewed", False)),
            )
            session.add(row)
            added += 1

        if not args.dry_run:
            session.commit()

    log.info("added=%d skipped=%d", added, skipped)
    return 0


if __name__ == "__main__":
    sys.exit(main())
