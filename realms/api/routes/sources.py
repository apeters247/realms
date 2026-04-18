"""Sources and extractions API endpoints."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from realms.services.entity_service import compute_pagination
from realms.services.source_service import SourceService
from realms.utils.database import get_db_session

router = APIRouter()
extractions_router = APIRouter()


@router.get("/")
async def list_sources(
    source_type: Optional[str] = Query(None),
    publication_year_min: Optional[int] = Query(None),
    publication_year_max: Optional[int] = Query(None),
    peer_reviewed: Optional[bool] = Query(None),
    credibility_min: Optional[float] = Query(None, ge=0.0, le=1.0),
    ingestion_status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    sort: str = Query("-publication_year"),
):
    with get_db_session() as session:
        service = SourceService(session)
        sources, total = service.list_sources(
            source_type=source_type,
            publication_year_min=publication_year_min,
            publication_year_max=publication_year_max,
            peer_reviewed=peer_reviewed,
            credibility_min=credibility_min,
            ingestion_status=ingestion_status,
            q=q, page=page, per_page=per_page, sort=sort,
        )
        return {"data": sources, "pagination": compute_pagination(total, page, per_page)}


@router.get("/{source_id}")
async def get_source(source_id: int):
    with get_db_session() as session:
        service = SourceService(session)
        source = service.get_source(source_id)
        if source is None:
            raise HTTPException(status_code=404, detail="Source not found")
        return {"data": source}


@extractions_router.get("/{extraction_id}")
async def get_extraction(extraction_id: int):
    with get_db_session() as session:
        service = SourceService(session)
        ext = service.get_extraction(extraction_id)
        if ext is None:
            raise HTTPException(status_code=404, detail="Extraction not found")
        return {"data": ext}
