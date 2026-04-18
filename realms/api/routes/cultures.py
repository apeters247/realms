"""Cultures API endpoints."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_cultures():
    """Stub: replaced in Task 11."""
    return {"data": [], "pagination": {"total": 0, "page": 1, "per_page": 50, "total_pages": 0}}


@router.get("/{culture_id}")
async def get_culture(culture_id: int):
    """Stub: replaced in Task 11."""
    return {"data": None}
