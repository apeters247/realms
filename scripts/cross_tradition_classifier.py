"""Rerun the pair-classifier, but only on co_occurs_with edges that cross
traditions. Cross-tradition co-occurrence is where syncretism + equivalence
relations hide most often, and it's the edge type the graph desperately
needs for visible crossover.

Implementation:
  * Select edges with relationship_type='co_occurs_with' where the two
    endpoints' primary cultural_associations differ.
  * For each, call the existing pair-classifier (which we've pointed at
    a free-tier model via REALMS_PAIR_MODEL).
  * Apply the classification only when confidence ≥ min-confidence AND
    the predicted label is one of {syncretized_with, equivalent_to,
    cognate_of, parent_of, consort_of, aspect_of}.

Env overrides you can set before running:
    REALMS_PAIR_MODEL=nvidia/nemotron-3-super-120b-a12b:free
    REALMS_PAIR_FALLBACK=openai/gpt-oss-120b:free

Usage:
    docker exec realms-api python -m scripts.cross_tradition_classifier --limit 300
    docker exec -d realms-api python -m scripts.cross_tradition_classifier
"""
from __future__ import annotations

import argparse
import json
import logging
from collections import Counter, defaultdict

from sqlalchemy import and_, or_, select, update

from realms.ingestion.pair_classifier import classify_pair
from realms.models import Entity, EntityRelationship, IngestedEntity
from realms.utils.database import get_db_session

log = logging.getLogger("realms.cross_tradition")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


SEMANTIC_TARGETS = {
    "syncretized_with", "equivalent_to", "cognate_of", "counterpart_of",
    "parent_of", "child_of", "consort_of", "sibling_of", "aspect_of",
    "manifests_as", "teacher_of", "student_of", "ally_of", "enemy_of",
}


def _primary_culture(e: Entity) -> str | None:
    if not e.cultural_associations:
        return None
    cs = e.cultural_associations
    if isinstance(cs, list) and cs:
        return str(cs[0])
    return None


def _pull_cross_tradition_edges(limit: int | None, skip_classified: bool):
    """Yield co_occurs_with edges whose endpoints are in different traditions."""
    with get_db_session() as session:
        # We pull all co_occurs_with edges, then filter in Python because
        # computing "primary culture" across a cross join is awkward SQL.
        q = (
            select(EntityRelationship)
            .where(EntityRelationship.relationship_type == "co_occurs_with")
            .order_by(EntityRelationship.extraction_confidence.desc().nulls_last())
        )
        if limit is not None:
            # Cap the scan; we'll stop emitting once we've seen "limit" cross-trad edges.
            q = q.limit(limit * 10)
        rows = session.execute(q).scalars().all()

    emitted = 0
    for edge in rows:
        if limit is not None and emitted >= limit:
            return
        with get_db_session() as session:
            a = session.get(Entity, edge.source_entity_id)
            b = session.get(Entity, edge.target_entity_id)
        if a is None or b is None:
            continue
        if a.review_status in {"merged", "out_of_scope"}:
            continue
        if b.review_status in {"merged", "out_of_scope"}:
            continue
        ca = _primary_culture(a)
        cb = _primary_culture(b)
        if not ca or not cb or ca == cb:
            continue  # same tradition or missing
        yield (edge, a, b, ca, cb)
        emitted += 1


def _shared_passages(session, a_id: int, b_id: int, max_passages: int = 3) -> list[str]:
    """Find extraction passages where both entities co-occurred."""
    # Find source_ids where entity a was extracted.
    a_sources = {
        r[0] for r in session.execute(
            select(IngestedEntity.source_id)
            .where(IngestedEntity.entity_name_normalized.ilike(""))
            # We'll match by normalized name via the entity itself.
        ).all()
    }
    # Simpler: use the extraction_context from ingested_entities joined on
    # entity_name matching either entity name.
    rows = session.execute(
        select(IngestedEntity.source_id, IngestedEntity.extraction_context,
               IngestedEntity.entity_name_normalized)
        .where(IngestedEntity.extraction_context.isnot(None))
        .order_by(IngestedEntity.created_at.desc())
        .limit(2000)
    ).all()

    a_sources_by_ctx: dict[int, str] = {}
    b_sources: set[int] = set()
    name_a = _name_of(session, a_id)
    name_b = _name_of(session, b_id)
    if not name_a or not name_b:
        return []
    for src_id, ctx, ext_name in rows:
        if not ctx:
            continue
        if ext_name and ext_name.lower() == name_a.lower():
            a_sources_by_ctx[src_id] = ctx
        elif ext_name and ext_name.lower() == name_b.lower():
            b_sources.add(src_id)
    shared = [
        a_sources_by_ctx[s] for s in a_sources_by_ctx
        if s in b_sources
    ]
    return shared[:max_passages]


_name_cache: dict[int, str | None] = {}


def _name_of(session, eid: int) -> str | None:
    if eid in _name_cache:
        return _name_cache[eid]
    e = session.get(Entity, eid)
    n = e.name if e else None
    _name_cache[eid] = n
    return n


def run(limit: int | None, min_conf: float, dry_run: bool) -> dict:
    stats: Counter = Counter()
    applied = 0
    scanned = 0
    no_passage = 0

    for edge, a, b, ca, cb in _pull_cross_tradition_edges(limit=limit, skip_classified=False):
        scanned += 1
        with get_db_session() as session:
            passages = _shared_passages(session, a.id, b.id, max_passages=3)
        if not passages:
            no_passage += 1
            continue
        try:
            result = classify_pair(a.name, b.name, passages)
        except Exception as exc:  # noqa: BLE001
            log.warning("classify_pair %d×%d: %s", a.id, b.id, exc)
            stats["error"] += 1
            continue
        stats[result.label] += 1
        if (result.label in SEMANTIC_TARGETS
                and result.confidence >= min_conf):
            if not dry_run:
                with get_db_session() as session:
                    session.execute(
                        update(EntityRelationship)
                        .where(EntityRelationship.id == edge.id)
                        .values(
                            relationship_type=result.label,
                            extraction_confidence=result.confidence,
                            description=(
                                f"classified(cross-tradition): {result.label} "
                                f"[{ca}↔{cb}]"
                            ),
                            strength="strong" if result.confidence >= 0.9 else "moderate",
                        )
                    )
                    session.commit()
            applied += 1
            log.info("[%4d] %s ↔ %s → %s (%.2f)  %s↔%s  model=%s",
                     scanned, a.name[:18], b.name[:18], result.label,
                     result.confidence, ca[:14], cb[:14], result.model)
        if scanned % 20 == 0:
            log.info("progress: scanned=%d applied=%d no_passage=%d",
                     scanned, applied, no_passage)

    return {
        "scanned": scanned,
        "applied": applied,
        "no_passage": no_passage,
        "labels": dict(stats),
        "dry_run": dry_run,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=500,
                   help="Max cross-tradition edges to scan (default 500)")
    p.add_argument("--min-confidence", type=float, default=0.75)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    summary = run(limit=args.limit, min_conf=args.min_confidence,
                  dry_run=args.dry_run)
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
