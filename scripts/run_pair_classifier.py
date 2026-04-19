"""Classify existing co_occurs_with edges into semantic relationship types.

Run as a one-shot job:
  docker exec realms-api python -m scripts.run_pair_classifier --limit 100

For each co_occurs_with edge this script:
  1. Finds the chunk(s) where both endpoint entities were extracted
  2. Calls the OpenRouter pair classifier (Gemini Flash default)
  3. If the classifier returns a non-unknown label with confidence >= threshold,
     updates the edge in-place with the new relationship_type
  4. Otherwise leaves the co_occurs_with edge unchanged (so a future re-run can retry)
"""
from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from typing import Iterable

from sqlalchemy import and_, select, update
from sqlalchemy.orm import Session

from realms.ingestion.pair_classifier import ClassificationResult, classify_pair
from realms.models import Entity, EntityRelationship, IngestedEntity
from realms.utils.database import get_db_session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("realms.pair_classifier")


def _fetch_co_occur_edges(
    session: Session, limit: int | None, skip_ids: set[int]
) -> list[EntityRelationship]:
    stmt = (
        select(EntityRelationship)
        .where(EntityRelationship.relationship_type == "co_occurs_with")
        .order_by(EntityRelationship.id.asc())
    )
    rows = list(session.execute(stmt).scalars().all())
    rows = [r for r in rows if r.id not in skip_ids]
    if limit is not None:
        rows = rows[:limit]
    return rows


def _collect_passages(session: Session, entity_a: Entity, entity_b: Entity) -> list[str]:
    """Return distinct chunk texts where BOTH entities were extracted.

    Join on ingested_entities.source_id + extraction_context (chunk identity).
    """
    ext_a = session.execute(
        select(IngestedEntity).where(
            IngestedEntity.entity_name_normalized.ilike(entity_a.name)
        )
    ).scalars().all()
    ext_b = session.execute(
        select(IngestedEntity).where(
            IngestedEntity.entity_name_normalized.ilike(entity_b.name)
        )
    ).scalars().all()

    by_chunk_a: dict[tuple[int | None, str | None], str] = {}
    for e in ext_a:
        key = (e.source_id, e.extraction_context)
        if key[1]:
            by_chunk_a[key] = e.extraction_context or ""
    by_chunk_b: dict[tuple[int | None, str | None], str] = {}
    for e in ext_b:
        key = (e.source_id, e.extraction_context)
        if key[1]:
            by_chunk_b[key] = e.extraction_context or ""

    shared = set(by_chunk_a.keys()) & set(by_chunk_b.keys())
    return [by_chunk_a[k] for k in sorted(shared) if by_chunk_a[k]]


def _apply_classification(
    session: Session, edge: EntityRelationship, result: ClassificationResult,
    *, min_confidence: float, dry_run: bool,
) -> str:
    if result.label == "unknown" or result.confidence < min_confidence:
        return "skipped"
    if dry_run:
        log.info("  DRY RUN: would classify #%d as %s (conf=%.2f): %r",
                 edge.id, result.label, result.confidence, result.quote[:80])
        return "dryrun"
    stmt = (
        update(EntityRelationship)
        .where(EntityRelationship.id == edge.id)
        .values(
            relationship_type=result.label,
            description=result.quote or edge.description,
            extraction_confidence=max(edge.extraction_confidence or 0.0, result.confidence),
            strength="strong" if result.confidence >= 0.85 else "moderate",
        )
    )
    session.execute(stmt)
    session.commit()
    return "updated"


def run(args: argparse.Namespace) -> int:
    stats = defaultdict(int)
    with get_db_session() as session:
        edges = _fetch_co_occur_edges(session, args.limit, skip_ids=set())
        log.info("Classifying %d co_occurs_with edges (min_conf=%.2f, dry_run=%s)",
                 len(edges), args.min_confidence, args.dry_run)

        for i, edge in enumerate(edges, 1):
            a = session.get(Entity, edge.source_entity_id)
            b = session.get(Entity, edge.target_entity_id)
            if a is None or b is None:
                log.warning("edge #%d: missing entity, skipping", edge.id)
                stats["missing_entity"] += 1
                continue

            passages = _collect_passages(session, a, b)
            if not passages:
                log.debug("edge #%d (%s, %s): no shared chunks", edge.id, a.name, b.name)
                stats["no_passages"] += 1
                continue

            result = classify_pair(a.name, b.name, passages)
            stats[result.label] += 1

            action = _apply_classification(
                session, edge, result,
                min_confidence=args.min_confidence,
                dry_run=args.dry_run,
            )
            stats[f"action:{action}"] += 1

            log.info(
                "[%4d/%4d] #%d (%s → %s) label=%s conf=%.2f model=%s action=%s",
                i, len(edges), edge.id,
                a.name[:20], b.name[:20],
                result.label, result.confidence, result.model, action,
            )

    log.info("Pair classifier summary: %s", dict(stats))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify co_occurs_with edges into semantic types.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max number of edges to process (default: all).")
    parser.add_argument("--min-confidence", type=float, default=0.7,
                        help="Minimum classifier confidence to rewrite the edge (default 0.7).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Do not modify the DB; just log what would change.")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
