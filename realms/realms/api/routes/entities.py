"""Entities API endpoints (read-only)."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from realms.services.entity_service import EntityService, compute_pagination
from realms.utils.database import get_db_session

router = APIRouter()


@router.get("/")
async def list_entities(
    entity_type: Optional[str] = Query(None),
    alignment: Optional[str] = Query(None),
    realm: Optional[str] = Query(None),
    hierarchy_level_min: Optional[int] = Query(None, ge=1, le=10),
    hierarchy_level_max: Optional[int] = Query(None, ge=1, le=10),
    confidence_min: Optional[float] = Query(None, ge=0.0, le=1.0),
    culture_id: Optional[int] = Query(None, gt=0),
    region_id: Optional[int] = Query(None, gt=0),
    power: Optional[str] = Query(None),
    domain: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    sort: str = Query("-consensus_confidence,name"),
):
    """List entities with filtering and pagination."""
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
            sort=sort,
        )
        return {"data": entities, "pagination": compute_pagination(total, page, per_page)}


@router.get("/{entity_id}")
async def get_entity(entity_id: int):
    """Get detailed information about a specific entity."""
    with get_db_session() as session:
        service = EntityService(session)
        entity = service.get_entity(entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="Entity not found")
        return {"data": entity}


@router.get("/{entity_id}/relationships")
async def get_entity_relationships(entity_id: int):
    """Get outgoing relationships for a specific entity."""
    with get_db_session() as session:
        service = EntityService(session)
        return {"data": service.get_entity_relationships(entity_id)}


@router.get("/{entity_id}/plant-connections")
async def get_entity_plant_connections(entity_id: int):
    """Get plant-spirit connections for a specific entity."""
    with get_db_session() as session:
        service = EntityService(session)
        return {"data": service.get_entity_plant_connections(entity_id)}
