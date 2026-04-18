"""Service layer for EntityClass queries."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from realms.models import Entity, EntityClass, IngestionSource
from realms.services.entity_service import _entity_to_summary


_SORT_COLUMNS = {
    "name": EntityClass.name,
    "hierarchy_level": EntityClass.hierarchy_level,
    "confidence_score": EntityClass.confidence_score,
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


def _class_to_response(c: EntityClass) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "category_id": c.category_id,
        "description": c.description,
        "core_powers": c.core_powers or [],
        "associated_plants": c.associated_plants or [],
        "hierarchy_level": c.hierarchy_level,
        "hierarchy_name": c.hierarchy_name,
        "confidence_score": c.confidence_score or 0.0,
    }


class ClassService:
    def __init__(self, session: Session):
        self.session = session

    def list_entity_classes(
        self,
        category_id: Optional[int] = None,
        hierarchy_level_min: Optional[int] = None,
        hierarchy_level_max: Optional[int] = None,
        confidence_min: Optional[float] = None,
        q: Optional[str] = None,
        page: int = 1,
        per_page: int = 50,
        sort: str = "name",
    ) -> tuple[list[dict], int]:
        stmt = select(EntityClass)
        if category_id is not None:
            stmt = stmt.where(EntityClass.category_id == category_id)
        if hierarchy_level_min is not None:
            stmt = stmt.where(EntityClass.hierarchy_level >= hierarchy_level_min)
        if hierarchy_level_max is not None:
            stmt = stmt.where(EntityClass.hierarchy_level <= hierarchy_level_max)
        if confidence_min is not None:
            stmt = stmt.where(EntityClass.confidence_score >= confidence_min)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(EntityClass.name.ilike(like), EntityClass.description.ilike(like)))

        total = self.session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = _apply_sort(stmt, sort).offset((page - 1) * per_page).limit(per_page)
        rows = self.session.execute(stmt).scalars().all()
        return [_class_to_response(c) for c in rows], total

    def get_entity_class(self, class_id: int) -> Optional[dict]:
        entity_class = self.session.get(EntityClass, class_id)
        if entity_class is None:
            return None

        entities = self.session.execute(
            select(Entity).where(Entity.entity_class_id == class_id)
        ).scalars().all()

        source_ids = list(entity_class.provenance_sources or [])
        provenance_sources: list[dict] = []
        if source_ids:
            src_rows = self.session.execute(
                select(IngestionSource).where(IngestionSource.id.in_(source_ids))
            ).scalars().all()
            provenance_sources = [
                {"id": s.id, "source_name": s.source_name, "credibility_score": s.credibility_score or 0.0}
                for s in src_rows
            ]

        resp = _class_to_response(entity_class)
        resp.update({
            "entities": [_entity_to_summary(e) for e in entities],
            "provenance_sources": provenance_sources,
        })
        return resp

    def get_entities_in_class(
        self, class_id: int, page: int = 1, per_page: int = 50
    ) -> tuple[list[dict], int]:
        stmt = select(Entity).where(Entity.entity_class_id == class_id)
        total = self.session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = stmt.order_by(Entity.name.asc()).offset((page - 1) * per_page).limit(per_page)
        rows = self.session.execute(stmt).scalars().all()
        return [_entity_to_summary(e) for e in rows], total
