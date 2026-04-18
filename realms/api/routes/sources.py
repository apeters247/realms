"""Sources + extractions API endpoints."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_sources():
    """Stub: replaced in Task 13."""
    return {"data": [], "pagination": {"total": 0, "page": 1, "per_page": 50, "total_pages": 0}}


@router.get("/{source_id}")
async def get_source(source_id: int):
    """Stub: replaced in Task 13."""
    return {"data": None}
