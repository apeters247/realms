"""Review queue — surface low-confidence or thinly-sourced entities for QA."""
from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import func, select, and_

from realms.models import Entity, EntityRelationship, IngestedEntity
from realms.utils.database import get_db_session

router = APIRouter()


@router.get("/entities")
async def review_entities(
    confidence_max: float = Query(0.75, ge=0.0, le=1.0,
                                   description="Return entities with consensus_confidence below this"),
    single_source_only: bool = Query(False, description="Only entities derived from a single source"),
    isolated_only: bool = Query(False, description="Only entities with no relationships"),
    limit: int = Query(100, ge=1, le=500),
):
    """Candidates for human review: low confidence, thin provenance, or orphaned."""
    with get_db_session() as session:
        stmt = select(Entity)
        stmt = stmt.where(Entity.consensus_confidence <= confidence_max)
        stmt = stmt.order_by(Entity.consensus_confidence.asc(), Entity.id.asc())
        stmt = stmt.limit(limit)
        candidates = list(session.execute(stmt).scalars().all())

        # Optional: filter to single-source
        if single_source_only:
            candidates = [
                e for e in candidates
                if len(e.provenance_sources or []) <= 1
            ]

        # Optional: filter to isolated
        if isolated_only:
            edge_counts = {}
            if candidates:
                ids = [e.id for e in candidates]
                counts_rows = session.execute(
                    select(EntityRelationship.source_entity_id, func.count().label("n"))
                    .where(EntityRelationship.source_entity_id.in_(ids))
                    .group_by(EntityRelationship.source_entity_id)
                ).all()
                edge_counts = {r[0]: r[1] for r in counts_rows}
                counts_rows = session.execute(
                    select(EntityRelationship.target_entity_id, func.count().label("n"))
                    .where(EntityRelationship.target_entity_id.in_(ids))
                    .group_by(EntityRelationship.target_entity_id)
                ).all()
                for r in counts_rows:
                    edge_counts[r[0]] = edge_counts.get(r[0], 0) + r[1]
            candidates = [e for e in candidates if edge_counts.get(e.id, 0) == 0]

        payload = []
        for e in candidates:
            n_sources = len(e.provenance_sources or [])
            n_extractions = len(e.extraction_instances or [])
            payload.append({
                "id": e.id,
                "name": e.name,
                "entity_type": e.entity_type,
                "alignment": e.alignment,
                "realm": e.realm,
                "consensus_confidence": e.consensus_confidence or 0.0,
                "n_sources": n_sources,
                "n_extractions": n_extractions,
                "cultural_associations": e.cultural_associations or [],
                "description": e.description,
                "flags": [
                    *(["low_confidence"] if (e.consensus_confidence or 0.0) < 0.7 else []),
                    *(["single_source"] if n_sources <= 1 else []),
                ],
            })
        return {"data": payload, "meta": {"count": len(payload)}}


@router.get("/stats")
async def review_stats():
    """Summary counts for QA dashboards."""
    with get_db_session() as session:
        total = session.execute(select(func.count(Entity.id))).scalar_one()
        low_conf = session.execute(
            select(func.count(Entity.id)).where(Entity.consensus_confidence < 0.7)
        ).scalar_one()
        very_low_conf = session.execute(
            select(func.count(Entity.id)).where(Entity.consensus_confidence < 0.5)
        ).scalar_one()
        # entities with only 1 source
        single_source = session.execute(
            select(func.count(Entity.id)).where(
                func.jsonb_array_length(func.coalesce(Entity.provenance_sources, func.cast("[]", Entity.provenance_sources.type))) <= 1
            )
        ).scalar_one()

        # isolated (no outgoing or incoming edges)
        rel_q = session.execute(select(func.count(func.distinct(EntityRelationship.source_entity_id)))).scalar_one()
        rel_t = session.execute(select(func.count(func.distinct(EntityRelationship.target_entity_id)))).scalar_one()
        # combine source+target distinct set via UNION
        connected_ids = session.execute(
            select(EntityRelationship.source_entity_id).distinct().union(
                select(EntityRelationship.target_entity_id).distinct()
            )
        ).all()
        connected_count = len(set(r[0] for r in connected_ids))
        isolated = total - connected_count

        return {
            "data": {
                "total_entities": total,
                "low_confidence": low_conf,          # < 0.7
                "very_low_confidence": very_low_conf,  # < 0.5
                "single_source_entities": single_source,
                "isolated_entities": isolated,
                "connected_entities": connected_count,
            }
        }
