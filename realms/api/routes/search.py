"""Search API endpoints."""
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from realms.services.entity_service import compute_pagination
from realms.services.search_service import SearchService
from realms.utils.database import get_db_session

router = APIRouter()


class AdvancedSearchRequest(BaseModel):
    filters: dict[str, Any] = {}
    sort: str = "-consensus_confidence"
    page: int = 1
    per_page: int = 50


@router.get("/")
async def global_search(q: str = Query("")):
    with get_db_session() as session:
        service = SearchService(session)
        return {"data": service.global_search(q)}


@router.get("/similar")
async def similar_entities(
    q: str = Query(..., min_length=1),
    threshold: float = Query(0.2, ge=0.05, le=0.95),
    limit: int = Query(20, ge=1, le=100),
):
    """Trigram-similarity search: 'xapiri' matches 'Xapiripë', etc."""
    with get_db_session() as session:
        service = SearchService(session)
        return {"data": service.similar_entities(q, limit=limit, threshold=threshold)}


@router.post("/advanced")
async def advanced_search(req: AdvancedSearchRequest):
    with get_db_session() as session:
        service = SearchService(session)
        entities, total = service.advanced_entity_search(
            filters=req.filters, sort=req.sort, page=req.page, per_page=req.per_page,
        )
        return {"data": entities, "pagination": compute_pagination(total, req.page, req.per_page)}
