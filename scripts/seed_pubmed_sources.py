"""Seed PubMed ingestion sources for corroboration of existing entities.

For each entity with at least one cultural association, query PubMed via
E-utilities esearch for "<entity name> <culture>" and enqueue up to
`--per-entity` matching PMIDs as ingestion_sources rows with
source_type='pubmed' and status='pending'. Idempotent on URL.

Usage (inside container):
    docker exec realms-api python -m scripts.seed_pubmed_sources --per-entity 3
"""
from __future__ import annotations

import argparse
import logging
import sys
import time

from sqlalchemy import func, select

from realms.ingestion.pubmed_fetcher import esearch_pmids
from realms.models import Entity, IngestionSource
from realms.utils.database import get_db_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("realms.seed_pubmed")


def _pubmed_url(pmid: str) -> str:
    return f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"


def _build_query(entity: Entity) -> str:
    culture = ""
    if entity.cultural_associations and isinstance(entity.cultural_associations, list):
        culture = str(entity.cultural_associations[0])
    name = (entity.name or "").strip()
    if culture:
        return f"{name} {culture} mythology OR religion OR ethnography"
    return f"{name} mythology OR ethnography"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-entity", type=int, default=3,
                        help="Max PubMed sources to enqueue per entity (default 3)")
    parser.add_argument("--max-entities", type=int, default=None,
                        help="Stop after processing this many entities (for dry-run)")
    parser.add_argument("--min-confidence", type=float, default=0.6,
                        help="Only seed for entities above this consensus_confidence")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be added without writing")
    args = parser.parse_args()

    added = 0
    scanned = 0
    skipped_existing = 0
    skipped_nohits = 0

    with get_db_session() as session:
        stmt = (
            select(Entity)
            .where(Entity.consensus_confidence >= args.min_confidence)
            .order_by(Entity.id.asc())
        )
        if args.max_entities:
            stmt = stmt.limit(args.max_entities)
        entities = list(session.execute(stmt).scalars().all())

        for entity in entities:
            scanned += 1
            query = _build_query(entity)
            try:
                pmids = esearch_pmids(query, retmax=args.per_entity)
            except Exception as exc:  # noqa: BLE001
                log.warning("esearch failed for %r: %s", entity.name, exc)
                continue

            for pmid in pmids:
                url = _pubmed_url(pmid)
                existing = session.execute(
                    select(IngestionSource).where(IngestionSource.url == url)
                ).scalar_one_or_none()
                if existing is not None:
                    skipped_existing += 1
                    continue
                if args.dry_run:
                    log.info("[DRY] would add PMID %s (for %s): %s", pmid, entity.name, query)
                    continue
                row = IngestionSource(
                    source_type="pubmed",
                    source_name=f"PubMed PMID {pmid} (seed: {entity.name})",
                    url=url,
                    ingestion_status="pending",
                    language="en",
                )
                session.add(row)
                session.flush()
                added += 1

            if not pmids:
                skipped_nohits += 1

            # Polite to NCBI: esearch_pmids already sleeps 400ms;
            # add a small per-entity gap to avoid bursts.
            time.sleep(0.2)

        if not args.dry_run:
            session.commit()

    log.info("scanned=%d added=%d existing=%d no_hits=%d",
             scanned, added, skipped_existing, skipped_nohits)
    return 0


if __name__ == "__main__":
    sys.exit(main())
