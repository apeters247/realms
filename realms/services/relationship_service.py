"""Service layer for EntityRelationship queries."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from realms.models import Entity, EntityRelationship, IngestionSource
from realms.services.entity_service import _entity_to_summary


_SORT_COLUMNS = {
    "confidence": EntityRelationship.extraction_confidence,
    "created_at": EntityRelationship.created_at,
}


def _apply_sort(stmt, sort: str):
    for token in sort.split(","):
        token = token.strip()
        if not token:
            continue
        descending = token.startswith("-")
        key = token.lstrip("-")
        col = _SORT_COLUMNS.get(key)
        if col is None:
            continue
        stmt = stmt.order_by(col.desc() if descending else col.asc())
    return stmt


def _rel_to_response(r: EntityRelationship) -> dict:
    return {
        "id": r.id,
        "source_entity_id": r.source_entity_id,
        "target_entity_id": r.target_entity_id,
        "relationship_type": r.relationship_type,
        "description": r.description,
        "strength": r.strength,
        "confidence": r.extraction_confidence or 0.0,
        "cultural_context": r.cultural_context or [],
        "historical_period": r.historical_period or [],
    }


class RelationshipService:
    def __init__(self, session: Session):
        self.session = session

    def list_relationships(
        self,
        relationship_type: Optional[str] = None,
        source_entity_id: Optional[int] = None,
        target_entity_id: Optional[int] = None,
        confidence_min: Optional[float] = None,
        cultural_context: Optional[str] = None,
        historical_period: Optional[str] = None,
        page: int = 1,
        per_page: int = 50,
        sort: str = "-confidence",
    ) -> tuple[list[dict], int]:
        stmt = select(EntityRelationship)
        if relationship_type:
            stmt = stmt.where(EntityRelationship.relationship_type == relationship_type)
        if source_entity_id is not None:
            stmt = stmt.where(EntityRelationship.source_entity_id == source_entity_id)
        if target_entity_id is not None:
            stmt = stmt.where(EntityRelationship.target_entity_id == target_entity_id)
        if confidence_min is not None:
            stmt = stmt.where(EntityRelationship.extraction_confidence >= confidence_min)
        if cultural_context:
            stmt = stmt.where(EntityRelationship.cultural_context.op("?")(cultural_context))
        if historical_period:
            stmt = stmt.where(EntityRelationship.historical_period.op("?")(historical_period))

        total = self.session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = _apply_sort(stmt, sort).offset((page - 1) * per_page).limit(per_page)
        rows = self.session.execute(stmt).scalars().all()
        return [_rel_to_response(r) for r in rows], total

    def get_relationship(self, relationship_id: int) -> Optional[dict]:
        rel = self.session.get(EntityRelationship, relationship_id)
        if rel is None:
            return None
        source = self.session.get(Entity, rel.source_entity_id)
        target = self.session.get(Entity, rel.target_entity_id)

        source_ids = list(rel.provenance_sources or [])
        provenance_sources: list[dict] = []
        if source_ids:
            src_rows = self.session.execute(
                select(IngestionSource).where(IngestionSource.id.in_(source_ids))
            ).scalars().all()
            provenance_sources = [
                {"id": s.id, "source_name": s.source_name, "credibility_score": s.credibility_score or 0.0}
                for s in src_rows
            ]

        resp = _rel_to_response(rel)
        resp.update({
            "source_entity": _entity_to_summary(source) if source else None,
            "target_entity": _entity_to_summary(target) if target else None,
            "provenance_sources": provenance_sources,
            "extraction_details": [],
        })
        return resp
