"""Geographic regions API endpoints."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from realms.services.entity_service import compute_pagination
from realms.services.region_service import RegionService
from realms.utils.database import get_db_session

router = APIRouter()


@router.get("/")
async def list_regions(
    region_type: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    sort: str = Query("name"),
):
    with get_db_session() as session:
        service = RegionService(session)
        regions, total = service.list_regions(
            region_type=region_type, q=q, page=page, per_page=per_page, sort=sort,
        )
        return {"data": regions, "pagination": compute_pagination(total, page, per_page)}


@router.get("/{region_id}")
async def get_region(region_id: int):
    with get_db_session() as session:
        service = RegionService(session)
        region = service.get_region(region_id)
        if region is None:
            raise HTTPException(status_code=404, detail="Region not found")
        return {"data": region}
