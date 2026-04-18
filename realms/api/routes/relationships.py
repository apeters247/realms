"""
Relationships API Endpoints
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from realms.models.schemas import RelationshipResponse, RelationshipDetail
from realms.services.relationship_service import RelationshipService
from realms.utils.database import get_db_session

router = APIRouter()

@router.get("/", response_model=List[RelationshipResponse])
async def list_relationships(
    relationship_type: Optional[str] = Query(None, description="Filter by relationship type"),
    source_entity_id: Optional[int] = Query(None, gt=0),
    target_entity_id: Optional[int] = Query(None, gt=0),
    confidence_min: Optional[float] = Query(None, ge=0.0, le=1.0),
    cultural_context: Optional[str] = Query(None),
    historical_period: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    sort: str = Query("-confidence")
):
    """List relationships with filtering"""
    try:
        with get_db_session() as session:
            service = RelationshipService(session)
            relationships, total = service.list_relationships(
                relationship_type=relationship_type,
                source_entity_id=source_entity_id,
                target_entity_id=target_entity_id,
                confidence_min=confidence_min,
                cultural_context=cultural_context,
                historical_period=historical_period,
                page=page,
                per_page=per_page,
                sort=sort
            )
            return relationships
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{relationship_id}", response_model=RelationshipDetail)
async def get_relationship(relationship_id: int):
    """Get detailed information about a specific relationship"""
    try:
        with get_db_session() as session:
            service = RelationshipService(session)
            relationship = service.get_relationship(relationship_id)
            if not relationship:
                raise HTTPException(status_code=404, detail="Relationship not found")
            return relationship
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))