"""Cultures API endpoints."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from realms.services.culture_service import CultureService
from realms.services.entity_service import compute_pagination
from realms.utils.database import get_db_session

router = APIRouter()


@router.get("/")
async def list_cultures(
    region: Optional[str] = Query(None),
    tradition_type: Optional[str] = Query(None),
    language_family: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    sort: str = Query("name"),
):
    with get_db_session() as session:
        service = CultureService(session)
        cultures, total = service.list_cultures(
            region=region, tradition_type=tradition_type,
            language_family=language_family, q=q,
            page=page, per_page=per_page, sort=sort,
        )
        return {"data": cultures, "pagination": compute_pagination(total, page, per_page)}


@router.get("/{culture_id}")
async def get_culture(culture_id: int):
    with get_db_session() as session:
        service = CultureService(session)
        culture = service.get_culture(culture_id)
        if culture is None:
            raise HTTPException(status_code=404, detail="Culture not found")
        return {"data": culture}
