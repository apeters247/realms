"""Ingestion + sync metrics endpoints."""
from fastapi import APIRouter
from sqlalchemy import func, select

from realms.models import Entity, IngestedEntity, IngestionSource
from realms.utils.database import get_db_session

router = APIRouter()


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
