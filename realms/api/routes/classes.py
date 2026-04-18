"""Entity Classes API endpoints."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from realms.services.class_service import ClassService
from realms.services.entity_service import compute_pagination
from realms.utils.database import get_db_session

router = APIRouter()


@router.get("/")
async def list_entity_classes(
    category_id: Optional[int] = Query(None, gt=0),
    hierarchy_level_min: Optional[int] = Query(None, ge=1, le=10),
    hierarchy_level_max: Optional[int] = Query(None, ge=1, le=10),
    confidence_min: Optional[float] = Query(None, ge=0.0, le=1.0),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    sort: str = Query("name"),
):
    with get_db_session() as session:
        service = ClassService(session)
        classes, total = service.list_entity_classes(
            category_id=category_id,
            hierarchy_level_min=hierarchy_level_min,
            hierarchy_level_max=hierarchy_level_max,
            confidence_min=confidence_min,
            q=q, page=page, per_page=per_page, sort=sort,
        )
        return {"data": classes, "pagination": compute_pagination(total, page, per_page)}


@router.get("/{class_id}")
async def get_entity_class(class_id: int):
    with get_db_session() as session:
        service = ClassService(session)
        entity_class = service.get_entity_class(class_id)
        if entity_class is None:
            raise HTTPException(status_code=404, detail="Entity class not found")
        return {"data": entity_class}


@router.get("/{class_id}/entities")
async def get_entities_in_class(
    class_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
):
    with get_db_session() as session:
        service = ClassService(session)
        entities, total = service.get_entities_in_class(class_id, page, per_page)
        return {"data": entities, "pagination": compute_pagination(total, page, per_page)}
