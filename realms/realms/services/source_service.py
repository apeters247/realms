"""Service layer for IngestionSource + IngestedEntity queries."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from realms.models import IngestedEntity, IngestionSource


def _source_to_response(s: IngestionSource) -> dict:
    return {
        "id": s.id,
        "source_type": s.source_type,
        "source_name": s.source_name,
        "authors": s.authors or [],
        "publication_year": s.publication_year,
        "journal_or_venue": s.journal_or_venue,
        "volume_issue": s.volume_issue,
        "pages": s.pages,
        "doi": s.doi,
        "isbn": s.isbn,
        "url": s.url,
        "access_date": s.access_date.isoformat() if s.access_date else None,
        "retrieval_method": s.retrieval_method,
        "language": s.language,
        "original_language": s.original_language,
        "translation_info": s.translation_info,
        "credibility_score": s.credibility_score or 0.0,
        "peer_reviewed": bool(s.peer_reviewed),
        "citation_count": s.citation_count or 0,
        "altmetrics": s.altmetrics,
        "ingestion_status": s.ingestion_status,
        "ingested_at": s.ingested_at.isoformat() if s.ingested_at else None,
        "processed_at": s.processed_at.isoformat() if s.processed_at else None,
        "error_log": s.error_log,
        "raw_content_hash": s.raw_content_hash,
        "storage_path": s.storage_path,
        "access_restrictions": s.access_restrictions,
        "ethical_considerations": s.ethical_considerations,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _extraction_to_response(e: IngestedEntity) -> dict:
    return {
        "id": e.id,
        "source_id": e.source_id,
        "extraction_method": e.extraction_method,
        "llm_model_used": e.llm_model_used,
        "llm_temperature": e.llm_temperature,
        "llm_prompt_version": e.llm_prompt_version,
        "raw_extracted_data": e.raw_extracted_data or {},
        "normalized_data": e.normalized_data or {},
        "entity_name_raw": e.entity_name_raw,
        "entity_name_normalized": e.entity_name_normalized,
        "extraction_confidence": e.extraction_confidence or 0.0,
        "extraction_context": e.extraction_context,
        "page_number": e.page_number,
        "section_title": e.section_title,
        "quote_context": e.quote_context,
        "status": e.status,
        "reviewer_notes": e.reviewer_notes,
        "reviewed_by": e.reviewed_by,
        "reviewed_at": e.reviewed_at.isoformat() if e.reviewed_at else None,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


class SourceService:
    def __init__(self, session: Session):
        self.session = session

    def list_sources(
        self,
        source_type: Optional[str] = None,
        publication_year_min: Optional[int] = None,
        publication_year_max: Optional[int] = None,
        peer_reviewed: Optional[bool] = None,
        credibility_min: Optional[float] = None,
        ingestion_status: Optional[str] = None,
        q: Optional[str] = None,
        page: int = 1,
        per_page: int = 50,
        sort: str = "-publication_year",
    ) -> tuple[list[dict], int]:
        stmt = select(IngestionSource)
        if source_type:
            stmt = stmt.where(IngestionSource.source_type == source_type)
        if publication_year_min is not None:
            stmt = stmt.where(IngestionSource.publication_year >= publication_year_min)
        if publication_year_max is not None:
            stmt = stmt.where(IngestionSource.publication_year <= publication_year_max)
        if peer_reviewed is not None:
            stmt = stmt.where(IngestionSource.peer_reviewed == peer_reviewed)
        if credibility_min is not None:
            stmt = stmt.where(IngestionSource.credibility_score >= credibility_min)
        if ingestion_status:
            stmt = stmt.where(IngestionSource.ingestion_status == ingestion_status)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(
                IngestionSource.source_name.ilike(like),
                IngestionSource.doi.ilike(like),
            ))

        total = self.session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

        descending = sort.startswith("-")
        key = sort.lstrip("-")
        col = getattr(IngestionSource, key, IngestionSource.publication_year)
        stmt = stmt.order_by(col.desc() if descending else col.asc())
        stmt = stmt.offset((page - 1) * per_page).limit(per_page)
        rows = self.session.execute(stmt).scalars().all()
        return [_source_to_response(s) for s in rows], total

    def get_source(self, source_id: int) -> Optional[dict]:
        source = self.session.get(IngestionSource, source_id)
        if source is None:
            return None
        ext_rows = self.session.execute(
            select(IngestedEntity).where(IngestedEntity.source_id == source_id)
        ).scalars().all()

        resp = _source_to_response(source)
        resp.update({
            "ingested_entities": [
                {
                    "id": e.id,
                    "entity_name_normalized": e.entity_name_normalized,
                    "extraction_confidence": e.extraction_confidence or 0.0,
                    "status": e.status,
                }
                for e in ext_rows
            ],
            "extraction_statistics": {
                "count": len(ext_rows),
                "avg_confidence": (
                    sum(e.extraction_confidence or 0.0 for e in ext_rows) / len(ext_rows)
                    if ext_rows else 0.0
                ),
            },
        })
        return resp

    def get_extraction(self, extraction_id: int) -> Optional[dict]:
        ext = self.session.get(IngestedEntity, extraction_id)
        if ext is None:
            return None
        return _extraction_to_response(ext)
