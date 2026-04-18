"""
Entities API Endpoints
Read-only access to spiritual entity records
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from pydantic import BaseModel
from realms.models.schemas import EntityResponse, EntityDetail, EntitySummary
from realms.services.entity_service import EntityService
from realms.utils.database import get_db_session

router = APIRouter()

@router.get("/", response_model=List[EntitySummary])
async def list_entities(
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    alignment: Optional[str] = Query(None, description="Filter by alignment"),
    realm: Optional[str] = Query(None, description="Filter by realm"),
    hierarchy_level_min: Optional[int] = Query(None, ge=1, le=10),
    hierarchy_level_max: Optional[int] = Query(None, ge=1, le=10),
    confidence_min: Optional[float] = Query(None, ge=0.0, le=1.0),
    culture_id: Optional[int] = Query(None, gt=0),
    region_id: Optional[int] = Query(None, gt=0),
    power: Optional[str] = Query(None, description="Filter by power name"),
    domain: Optional[str] = Query(None, description="Filter by domain"),
    q: Optional[str] = Query(None, description="General search query"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    sort: str = Query("-consensus_confidence,name", description="Sort order (prefix - for descending)")
):
    """List entities with filtering and pagination"""
    try:
        with get_db_session() as session:
            service = EntityService(session)
            entities, total = service.list_entities(
                entity_type=entity_type,
                alignment=alignment,
                realm=realm,
                hierarchy_level_min=hierarchy_level_min,
                hierarchy_level_max=hierarchy_level_max,
                confidence_min=confidence_min,
                culture_id=culture_id,
                region_id=region_id,
                power=power,
                domain=domain,
                q=q,
                page=page,
                per_page=per_page,
                sort=sort
            )
            
            # In a real implementation, we'd return pagination headers
            # For now, we'll include in a custom header or metadata
            return entities
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{entity_id}", response_model=EntityDetail)
async def get_entity(entity_id: int):
    """Get detailed information about a specific entity"""
    try:
        with get_db_session() as session:
            service = EntityService(session)
            entity = service.get_entity(entity_id)
            if not entity:
                raise HTTPException(status_code=404, detail="Entity not found")
            return entity
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{entity_id}/relationships")
async def get_entity_relationships(entity_id: int):
    """Get all relationships for a specific entity"""
    try:
        with get_db_session() as session:
            service = EntityService(session)
            relationships = service.get_entity_relationships(entity_id)
            return {"data": relationships}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{entity_id}/plant-connections")
async def get_entity_plant_connections(entity_id: int):
    """Get plant connections for a specific entity"""
    try:
        with get_db_session() as session:
            service = EntityService(session)
            connections = service.get_entity_plant_connections(entity_id)
            return {"data": connections}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))