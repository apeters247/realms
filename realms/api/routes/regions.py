"""Geographic regions API endpoints."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_regions():
    """Stub: replaced in Task 12."""
    return {"data": [], "pagination": {"total": 0, "page": 1, "per_page": 50, "total_pages": 0}}


@router.get("/{region_id}")
async def get_region(region_id: int):
    """Stub: replaced in Task 12."""
    return {"data": None}
