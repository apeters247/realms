"""Ingestion + sync metrics endpoints."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from sqlalchemy import func, or_, select

from realms.models import Entity, EntityRelationship, IngestedEntity, IngestionSource
from realms.utils.database import get_db_session

router = APIRouter()


@router.get("/activity")
async def recent_activity(minutes: int = Query(30, ge=1, le=720)):
    """Recent changes: sources processed, entities/extractions created, new edges."""
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    with get_db_session() as session:
        sources = session.execute(
            select(IngestionSource)
            .where(or_(
                IngestionSource.processed_at >= since,
                IngestionSource.updated_at >= since,
            ))
            .order_by(IngestionSource.updated_at.desc())
            .limit(20)
        ).scalars().all()
        new_extractions = session.execute(
            select(func.count(IngestedEntity.id)).where(IngestedEntity.created_at >= since)
        ).scalar_one()
        new_entities = session.execute(
            select(func.count(Entity.id)).where(Entity.created_at >= since)
        ).scalar_one()
        new_edges = session.execute(
            select(func.count(EntityRelationship.id)).where(EntityRelationship.created_at >= since)
        ).scalar_one()
        recent_semantic = session.execute(
            select(EntityRelationship)
            .where(EntityRelationship.created_at >= since)
            .where(EntityRelationship.relationship_type != "co_occurs_with")
            .order_by(EntityRelationship.created_at.desc())
            .limit(20)
        ).scalars().all()

        return {
            "data": {
                "window_minutes": minutes,
                "new_extractions": new_extractions,
                "new_entities": new_entities,
                "new_edges": new_edges,
                "sources": [
                    {
                        "id": s.id,
                        "source_name": s.source_name,
                        "status": s.ingestion_status,
                        "processed_at": s.processed_at.isoformat() if s.processed_at else None,
                    }
                    for s in sources
                ],
                "recent_semantic_edges": [
                    {
                        "id": r.id,
                        "source_entity_id": r.source_entity_id,
                        "target_entity_id": r.target_entity_id,
                        "relationship_type": r.relationship_type,
                        "confidence": r.extraction_confidence or 0.0,
                        "description": (r.description or "")[:200],
                    }
                    for r in recent_semantic
                ],
            }
        }


@router.get("/ingestion")
async def ingestion_metrics():
    with get_db_session() as session:
        status_counts = dict(
            session.execute(
                select(IngestionSource.ingestion_status, func.count(IngestionSource.id))
                .group_by(IngestionSource.ingestion_status)
            ).all()
        )
        extraction_count = session.execute(select(func.count(IngestedEntity.id))).scalar_one()
        entity_count = session.execute(select(func.count(Entity.id))).scalar_one()
        avg_conf = session.execute(select(func.avg(Entity.consensus_confidence))).scalar() or 0.0
        last_processed = session.execute(
            select(func.max(IngestionSource.processed_at))
        ).scalar()

        return {
            "data": {
                "sources_by_status": status_counts,
                "extractions_total": extraction_count,
                "entities_total": entity_count,
                "avg_entity_confidence": float(avg_conf),
                "last_processed_at": last_processed.isoformat() if last_processed else None,
            }
        }
