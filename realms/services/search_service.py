"""Service layer for global and advanced search."""
from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from realms.models import Culture, Entity, EntityClass, IngestionSource
from realms.services.class_service import _class_to_response
from realms.services.culture_service import _culture_to_response
from realms.services.entity_service import EntityService, _entity_to_summary
from realms.services.source_service import _source_to_response


class SearchService:
    def __init__(self, session: Session):
        self.session = session

    def global_search(self, q: str, limit: int = 20) -> dict[str, list[dict]]:
        if not q:
            return {"entities": [], "entity_classes": [], "cultures": [], "sources": []}
        like = f"%{q}%"
        entities = self.session.execute(
            select(Entity).where(or_(Entity.name.ilike(like), Entity.description.ilike(like))).limit(limit)
        ).scalars().all()
        classes = self.session.execute(
            select(EntityClass).where(or_(EntityClass.name.ilike(like), EntityClass.description.ilike(like))).limit(limit)
        ).scalars().all()
        cultures = self.session.execute(
            select(Culture).where(or_(Culture.name.ilike(like), Culture.description.ilike(like))).limit(limit)
        ).scalars().all()
        sources = self.session.execute(
            select(IngestionSource).where(IngestionSource.source_name.ilike(like)).limit(limit)
        ).scalars().all()
        return {
            "entities": [_entity_to_summary(e) for e in entities],
            "entity_classes": [_class_to_response(c) for c in classes],
            "cultures": [_culture_to_response(c) for c in cultures],
            "sources": [_source_to_response(s) for s in sources],
        }

    def advanced_entity_search(
        self,
        filters: dict[str, Any],
        sort: str = "-consensus_confidence",
        page: int = 1,
        per_page: int = 50,
    ) -> tuple[list[dict], int]:
        svc = EntityService(self.session)
        return svc.list_entities(
            entity_type=filters.get("entity_type"),
            alignment=filters.get("alignment"),
            realm=filters.get("realm"),
            hierarchy_level_min=filters.get("hierarchy_level_min"),
            hierarchy_level_max=filters.get("hierarchy_level_max"),
            confidence_min=filters.get("confidence_min"),
            power=filters.get("power"),
            domain=filters.get("domain"),
            q=filters.get("q"),
            page=page,
            per_page=per_page,
            sort=sort,
        )
