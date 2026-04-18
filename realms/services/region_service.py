"""Service layer for GeographicRegion queries."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from realms.models import Entity, GeographicRegion, IngestionSource
from realms.services.entity_service import _entity_to_summary


def _region_to_response(r: GeographicRegion) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "region_type": r.region_type,
        "countries": r.countries or [],
        "center_latitude": r.center_latitude,
        "center_longitude": r.center_longitude,
        "boundary_geojson": r.boundary_geojson,
        "cultural_overlap": r.cultural_overlap or [],
        "endemic_entities": r.endemic_entities or [],
        "shared_entities": r.shared_entities or [],
    }


class RegionService:
    def __init__(self, session: Session):
        self.session = session

    def list_regions(
        self,
        region_type: Optional[str] = None,
        q: Optional[str] = None,
        page: int = 1,
        per_page: int = 50,
        sort: str = "name",
    ) -> tuple[list[dict], int]:
        stmt = select(GeographicRegion)
        if region_type:
            stmt = stmt.where(GeographicRegion.region_type == region_type)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(GeographicRegion.name.ilike(like))

        total = self.session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        descending = sort.startswith("-")
        col = GeographicRegion.name
        stmt = stmt.order_by(col.desc() if descending else col.asc())
        stmt = stmt.offset((page - 1) * per_page).limit(per_page)
        rows = self.session.execute(stmt).scalars().all()
        return [_region_to_response(r) for r in rows], total

    def get_region(self, region_id: int) -> Optional[dict]:
        region = self.session.get(GeographicRegion, region_id)
        if region is None:
            return None

        entities = self.session.execute(
            select(Entity).where(Entity.geographical_associations.op("?")(region.name))
        ).scalars().all()

        source_ids = list(region.sources or [])
        sources: list[dict] = []
        if source_ids:
            src_rows = self.session.execute(
                select(IngestionSource).where(IngestionSource.id.in_(source_ids))
            ).scalars().all()
            sources = [
                {"id": s.id, "source_name": s.source_name, "credibility_score": s.credibility_score or 0.0}
                for s in src_rows
            ]

        resp = _region_to_response(region)
        resp.update({
            "entities": [_entity_to_summary(e) for e in entities],
            "sources": sources,
        })
        return resp
