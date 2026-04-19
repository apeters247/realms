"""Corroboration view: entity provenance broken down by source_type.

Tier scoring measures how many independent source types agree. High-tier
entities have been witnessed in both the popular (Wikipedia), academic
(PubMed), and historical (archive.org) record.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from realms.models import Entity, IngestedEntity, IngestionSource
from realms.utils.database import get_db_session

router = APIRouter()

# tier_N requires at least N distinct source_types.
_TIER_BY_SOURCE_COUNT = {0: "tier_0", 1: "tier_1", 2: "tier_2"}  # 3+ => tier_3


def _tier_for_types(source_types: set[str]) -> str:
    if not source_types:
        return "tier_0"
    if len(source_types) >= 3:
        return "tier_3"
    return _TIER_BY_SOURCE_COUNT.get(len(source_types), "tier_1")


def _sources_for_entity(session, entity: Entity) -> list[IngestionSource]:
    ids = entity.provenance_sources or []
    if not ids:
        return []
    rows = session.execute(
        select(IngestionSource).where(IngestionSource.id.in_(ids))
    ).scalars().all()
    return list(rows)


@router.get("/{entity_id}")
async def entity_corroboration(entity_id: int) -> dict[str, Any]:
    """Entity provenance grouped by source_type with a computed tier."""
    with get_db_session() as session:
        entity = session.get(Entity, entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="entity not found")

        sources = _sources_for_entity(session, entity)
        by_type: dict[str, list[dict]] = defaultdict(list)
        for s in sources:
            by_type[(s.source_type or "unknown").lower()].append({
                "id": s.id,
                "source_name": s.source_name,
                "url": s.url,
                "doi": s.doi,
                "authors": s.authors,
                "publication_year": s.publication_year,
                "journal_or_venue": s.journal_or_venue,
                "peer_reviewed": s.peer_reviewed,
                "credibility_score": s.credibility_score,
                "ingestion_status": s.ingestion_status,
            })

        tier = _tier_for_types(set(by_type.keys()))
        return {
            "data": {
                "entity_id": entity.id,
                "name": entity.name,
                "tier": tier,
                "distinct_source_types": sorted(by_type.keys()),
                "sources_by_type": dict(by_type),
                "n_sources": len(sources),
            }
        }


@router.get("/stats/summary")
async def corroboration_stats() -> dict[str, Any]:
    """Aggregate tier distribution across all entities."""
    with get_db_session() as session:
        entities = session.execute(select(Entity)).scalars().all()
        # Pre-load source_type for every source id in one query
        all_source_ids: set[int] = set()
        for e in entities:
            for sid in (e.provenance_sources or []):
                if isinstance(sid, int):
                    all_source_ids.add(sid)
        type_by_id: dict[int, str] = {}
        if all_source_ids:
            rows = session.execute(
                select(IngestionSource.id, IngestionSource.source_type)
                .where(IngestionSource.id.in_(all_source_ids))
            ).all()
            type_by_id = {r[0]: (r[1] or "unknown").lower() for r in rows}

        tier_counts: dict[str, int] = defaultdict(int)
        type_counts: dict[str, int] = defaultdict(int)
        for e in entities:
            types: set[str] = set()
            for sid in (e.provenance_sources or []):
                if isinstance(sid, int) and sid in type_by_id:
                    types.add(type_by_id[sid])
                    type_counts[type_by_id[sid]] += 1
            tier_counts[_tier_for_types(types)] += 1

        return {
            "data": {
                "total_entities": len(entities),
                "tier_counts": dict(tier_counts),
                "source_type_counts": dict(type_counts),
            }
        }


@router.get("/conflicts/{entity_id}")
async def entity_conflicts(entity_id: int) -> dict[str, Any]:
    """Return per-field disagreements across ingested_entities rows for an entity.

    We don't have a direct FK from ingested_entities → entities, so we match by
    normalized name. This is an approximation and reflects the data model's
    current shape.
    """
    with get_db_session() as session:
        entity = session.get(Entity, entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="entity not found")

        # Pull all extractions whose normalized name matches this entity
        extractions = session.execute(
            select(IngestedEntity).where(
                func.lower(IngestedEntity.entity_name_normalized)
                == (entity.name or "").lower()
            )
        ).scalars().all()

        if not extractions:
            return {"data": {"entity_id": entity_id, "conflicts": []}}

        # Gather values by field from raw_extracted_data
        fields_of_interest = ["alignment", "realm", "entity_type"]
        field_values: dict[str, dict[str, list[int]]] = {f: {} for f in fields_of_interest}
        for ex in extractions:
            data = ex.raw_extracted_data or {}
            if not isinstance(data, dict):
                continue
            for f in fields_of_interest:
                val = data.get(f)
                if val is None or val == "":
                    continue
                field_values[f].setdefault(str(val), []).append(ex.source_id or -1)

        conflicts = []
        for f, vals in field_values.items():
            if len(vals) > 1:
                conflicts.append({
                    "field": f,
                    "values": [
                        {"value": v, "n_sources": len(set(sids)), "source_ids": sorted(set(sids))}
                        for v, sids in vals.items()
                    ],
                })
        return {"data": {"entity_id": entity_id, "conflicts": conflicts}}
