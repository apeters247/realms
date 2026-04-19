"""Service layer for Culture queries."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from realms.models import Culture, Entity, IngestionSource
from realms.services.entity_service import _entity_to_summary


def _culture_to_response(c: Culture) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "language_family": c.language_family,
        "region": c.region,
        "countries": c.countries or [],
        "description": c.description,
        "tradition_type": c.tradition_type,
        "primary_plants": c.primary_plants or [],
    }


class CultureService:
    def __init__(self, session: Session):
        self.session = session

    def list_cultures(
        self,
        region: Optional[str] = None,
        tradition_type: Optional[str] = None,
        language_family: Optional[str] = None,
        q: Optional[str] = None,
        page: int = 1,
        per_page: int = 50,
        sort: str = "name",
    ) -> tuple[list[dict], int]:
        stmt = select(Culture)
        if region:
            stmt = stmt.where(Culture.region == region)
        if tradition_type:
            stmt = stmt.where(Culture.tradition_type == tradition_type)
        if language_family:
            stmt = stmt.where(Culture.language_family == language_family)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(Culture.name.ilike(like), Culture.description.ilike(like)))

        total = self.session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

        descending = sort.startswith("-")
        key = sort.lstrip("-")
        col = getattr(Culture, key, Culture.name)
        stmt = stmt.order_by(col.desc() if descending else col.asc())
        stmt = stmt.offset((page - 1) * per_page).limit(per_page)
        rows = self.session.execute(stmt).scalars().all()
        return [_culture_to_response(c) for c in rows], total

    def get_culture(self, culture_id: int) -> Optional[dict]:
        culture = self.session.get(Culture, culture_id)
        if culture is None:
            return None

        entities = self.session.execute(
            select(Entity).where(Entity.cultural_associations.op("?")(culture.name))
        ).scalars().all()

        source_ids = list(culture.sources or [])
        sources: list[dict] = []
        if source_ids:
            src_rows = self.session.execute(
                select(IngestionSource).where(IngestionSource.id.in_(source_ids))
            ).scalars().all()
            sources = [
                {"id": s.id, "source_name": s.source_name, "credibility_score": s.credibility_score or 0.0}
                for s in src_rows
            ]

        resp = _culture_to_response(culture)
        resp.update({
            "entities": [_entity_to_summary(e) for e in entities],
            "entity_pantheon": culture.entity_pantheon or {},
            "sources": sources,
        })
        return resp
