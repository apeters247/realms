"""Service layer for aggregate stats."""
from __future__ import annotations

from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from realms.models import Entity, IngestedEntity, IngestionSource


class StatsService:
    def __init__(self, session: Session):
        self.session = session

    def get_stats(self) -> dict:
        total_entities = self.session.execute(select(func.count(Entity.id))).scalar_one() or 0
        by_type = dict(
            self.session.execute(
                select(Entity.entity_type, func.count(Entity.id))
                .where(Entity.entity_type.is_not(None))
                .group_by(Entity.entity_type)
            ).all()
        )
        by_realm = dict(
            self.session.execute(
                select(Entity.realm, func.count(Entity.id))
                .where(Entity.realm.is_not(None))
                .group_by(Entity.realm)
            ).all()
        )
        by_alignment = dict(
            self.session.execute(
                select(Entity.alignment, func.count(Entity.id))
                .where(Entity.alignment.is_not(None))
                .group_by(Entity.alignment)
            ).all()
        )

        culture_counter: Counter[str] = Counter()
        for e in self.session.execute(select(Entity)).scalars().all():
            for name in (e.cultural_associations or []):
                culture_counter[name] += 1

        avg_conf = self.session.execute(select(func.avg(Entity.consensus_confidence))).scalar() or 0.0
        sources_processed = self.session.execute(
            select(func.count(IngestionSource.id)).where(IngestionSource.ingestion_status == "completed")
        ).scalar_one() or 0
        total_extractions = self.session.execute(select(func.count(IngestedEntity.id))).scalar_one() or 0
        last_updated = self.session.execute(select(func.max(Entity.updated_at))).scalar()

        return {
            "total_entities": total_entities,
            "by_type": by_type,
            "by_realm": by_realm,
            "by_alignment": by_alignment,
            "by_culture": dict(culture_counter),
            "avg_confidence": float(avg_conf),
            "sources_processed": sources_processed,
            "total_extractions": total_extractions,
            "last_updated": last_updated.isoformat() if last_updated else None,
        }
