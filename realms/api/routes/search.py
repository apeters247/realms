"""Search API endpoints."""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class AdvancedSearchRequest(BaseModel):
    filters: dict = {}
    sort: str = "-consensus_confidence"
    page: int = 1
    per_page: int = 50


@router.get("/")
async def global_search(q: str = ""):
    """Stub: replaced in Task 14."""
    return {"data": {"entities": [], "entity_classes": [], "cultures": [], "sources": []}}


@router.post("/advanced")
async def advanced_search(req: AdvancedSearchRequest):
    """Stub: replaced in Task 14."""
    return {"data": [], "pagination": {"total": 0, "page": req.page, "per_page": req.per_page, "total_pages": 0}}
