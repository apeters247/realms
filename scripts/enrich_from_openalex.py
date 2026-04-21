"""For every entity in the DB, search OpenAlex for peer-reviewed scholarship.

Writes new IngestionSource rows (source_type='journal') — the existing
worker picks them up and extracts entities from their abstracts.

Usage:
  # Preview what it would do (doesn't write).
  docker exec realms-api python -m scripts.enrich_from_openalex --dry-run --limit 5

  # Run it in the background for all entities.
  docker exec -d realms-api python -m scripts.enrich_from_openalex --per-entity 3

  # Skip entities that already have at least one journal source.
  docker exec realms-api python -m scripts.enrich_from_openalex --skip-enriched
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from typing import Iterable

from sqlalchemy import distinct, func, select

from realms.ingestion.openalex_fetcher import enrich_entity
from realms.models import Entity, IngestedEntity, IngestionSource
from realms.utils.database import get_db_session

log = logging.getLogger("realms.enrich_openalex")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _existing_source_urls() -> set[str]:
    with get_db_session() as session:
        urls = session.execute(
            select(IngestionSource.url).where(IngestionSource.url.isnot(None))
        ).scalars().all()
    return {u.strip().lower() for u in urls if u}


def _entities_without_journals() -> set[int]:
    """Entity IDs that have no journal-source extractions."""
    with get_db_session() as session:
        stmt = (
            select(IngestedEntity.entity_name_normalized)
            .join(IngestionSource, IngestedEntity.source_id == IngestionSource.id)
            .where(IngestionSource.source_type == "journal")
        )
        covered_names = {r for r in session.execute(stmt).scalars().all() if r}
        all_ents = session.execute(
            select(Entity.id, Entity.name)
        ).all()
        return {eid for eid, name in all_ents if (name or "").strip() not in covered_names}


def _iter_entities(limit: int | None, skip_enriched: bool, min_confidence: float = 0.7):
    with get_db_session() as session:
        stmt = (
            select(Entity.id, Entity.name, Entity.cultural_associations,
                   Entity.consensus_confidence)
            .where(Entity.consensus_confidence >= min_confidence)
            .order_by(Entity.consensus_confidence.desc())
        )
        rows = session.execute(stmt).all()

    target_ids = _entities_without_journals() if skip_enriched else None

    count = 0
    for eid, name, culture, conf in rows:
        if skip_enriched and target_ids is not None and eid not in target_ids:
            continue
        tradition = None
        if isinstance(culture, list) and culture:
            tradition = str(culture[0])
        yield eid, name, tradition, conf
        count += 1
        if limit is not None and count >= limit:
            return


def run(
    per_entity: int,
    limit: int | None,
    dry_run: bool,
    skip_enriched: bool,
    min_confidence: float,
) -> dict:
    seen_urls = _existing_source_urls()
    added = 0
    skipped = 0
    errors = 0
    start = time.time()

    for i, (eid, name, tradition, conf) in enumerate(
        _iter_entities(limit=limit, skip_enriched=skip_enriched, min_confidence=min_confidence),
        start=1,
    ):
        try:
            rows = list(enrich_entity(name, tradition, per_entity=per_entity))
        except Exception as exc:  # noqa: BLE001
            log.warning("enrich %d/%s: %s", eid, name, exc)
            errors += 1
            continue

        if not rows:
            skipped += 1
            continue

        new_rows = []
        for r in rows:
            key = (r.get("url") or "").strip().lower()
            if key and key in seen_urls:
                continue
            if key:
                seen_urls.add(key)
            new_rows.append(r)

        if not new_rows:
            skipped += 1
            continue

        if not dry_run:
            with get_db_session() as session:
                for r in new_rows:
                    session.add(IngestionSource(**r))
                session.commit()

        added += len(new_rows)
        if i % 20 == 0:
            log.info("[%d] %s → %d sources so far (added=%d skipped=%d err=%d)",
                     i, name, len(new_rows), added, skipped, errors)
        # Gentle pacing — OpenAlex polite pool is generous but still capped.
        time.sleep(0.15)

    elapsed = time.time() - start
    return {
        "entities_processed": i if 'i' in locals() else 0,
        "sources_added": added,
        "entities_skipped": skipped,
        "errors": errors,
        "dry_run": dry_run,
        "elapsed_seconds": round(elapsed, 1),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--per-entity", type=int, default=3,
                   help="max journal sources to add per entity")
    p.add_argument("--limit", type=int, default=None,
                   help="process at most N entities")
    p.add_argument("--min-confidence", type=float, default=0.7,
                   help="skip entities below this consensus_confidence")
    p.add_argument("--skip-enriched", action="store_true",
                   help="skip entities that already have ≥1 journal source")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    summary = run(
        per_entity=args.per_entity,
        limit=args.limit,
        dry_run=args.dry_run,
        skip_enriched=args.skip_enriched,
        min_confidence=args.min_confidence,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
