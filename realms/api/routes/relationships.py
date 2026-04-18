"""Relationships API endpoints."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from realms.services.entity_service import compute_pagination
from realms.services.relationship_service import RelationshipService
from realms.utils.database import get_db_session

router = APIRouter()


@router.get("/")
async def list_relationships(
    relationship_type: Optional[str] = Query(None),
    source_entity_id: Optional[int] = Query(None, gt=0),
    target_entity_id: Optional[int] = Query(None, gt=0),
    confidence_min: Optional[float] = Query(None, ge=0.0, le=1.0),
    cultural_context: Optional[str] = Query(None),
    historical_period: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    sort: str = Query("-confidence"),
):
    with get_db_session() as session:
        service = RelationshipService(session)
        rels, total = service.list_relationships(
            relationship_type=relationship_type,
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            confidence_min=confidence_min,
            cultural_context=cultural_context,
            historical_period=historical_period,
            page=page, per_page=per_page, sort=sort,
        )
        return {"data": rels, "pagination": compute_pagination(total, page, per_page)}


@router.get("/{relationship_id}")
async def get_relationship(relationship_id: int):
    with get_db_session() as session:
        service = RelationshipService(session)
        rel = service.get_relationship(relationship_id)
        if rel is None:
            raise HTTPException(status_code=404, detail="Relationship not found")
        return {"data": rel}
