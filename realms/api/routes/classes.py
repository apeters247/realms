"""
Entity Classes API Endpoints
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from realms.models.schemas import EntityClassResponse, EntityClassDetail
from realms.services.class_service import ClassService
from realms.utils.database import get_db_session

router = APIRouter()

@router.get("/", response_model=List[EntityClassResponse])
async def list_entity_classes(
    category_id: Optional[int] = Query(None, gt=0),
    hierarchy_level_min: Optional[int] = Query(None, ge=1, le=10),
    hierarchy_level_max: Optional[int] = Query(None, ge=1, le=10),
    confidence_min: Optional[float] = Query(None, ge=0.0, le=1.0),
    q: Optional[str] = Query(None, description="Search query"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    sort: str = Query("name")
):
    """List entity classes with filtering"""
    try:
        with get_db_session() as session:
            service = ClassService(session)
            classes, total = service.list_entity_classes(
                category_id=category_id,
                hierarchy_level_min=hierarchy_level_min,
                hierarchy_level_max=hierarchy_level_max,
                confidence_min=confidence_min,
                q=q,
                page=page,
                per_page=per_page,
                sort=sort
            )
            return classes
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{class_id}", response_model=EntityClassDetail)
async def get_entity_class(class_id: int):
    """Get detailed information about an entity class"""
    try:
        with get_db_session() as session:
            service = ClassService(session)
            entity_class = service.get_entity_class(class_id)
            if not entity_class:
                raise HTTPException(status_code=404, detail="Entity class not found")
            return entity_class
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{class_id}/entities")
async def get_entities_in_class(
    class_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100)
):
    """Get all entities belonging to a specific class"""
    try:
        with get_db_session() as session:
            service = ClassService(session)
            entities, total = service.get_entities_in_class(class_id, page, per_page)
            return {"data": entities}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))