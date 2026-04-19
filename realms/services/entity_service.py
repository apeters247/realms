"""Service layer for Entity queries."""
from __future__ import annotations

import math
from typing import Optional

from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.orm import Session

from realms.models import Entity, EntityRelationship, IngestedEntity, IngestionSource, PlantSpiritConnection


# Map outgoing relationship_type → label to display when viewing the *target* entity
INVERSE_REL_LABELS = {
    "parent_of": "child_of",
    "child_of": "parent_of",
    "teacher_of": "student_of",
    "student_of": "teacher_of",
    "serves": "served_by",
    "ruled_by": "rules",
    "aspect_of": "has_aspect",
    "manifests_as": "manifested_by",
    "created_by": "creator_of",
    # symmetric — keep label
    "consort_of": "consort_of",
    "sibling_of": "sibling_of",
    "allied_with": "allied_with",
    "enemy_of": "enemy_of",
    "syncretized_with": "syncretized_with",
    "co_occurs_with": "co_occurs_with",
    "associated_with": "associated_with",
}


_SORT_COLUMNS = {
    "name": Entity.name,
    "consensus_confidence": Entity.consensus_confidence,
    "hierarchy_level": Entity.hierarchy_level,
    "created_at": Entity.created_at,
}


def _apply_sort(stmt, sort: str):
    """Parse comma-separated sort spec like '-consensus_confidence,name'."""
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


def _entity_to_summary(e: Entity) -> dict:
    return {
        "id": e.id,
        "name": e.name,
        "entity_type": e.entity_type,
        "alignment": e.alignment,
        "realm": e.realm,
        "hierarchy_level": e.hierarchy_level,
        "hierarchy_name": e.hierarchy_name,
        "powers": e.powers or [],
        "domains": e.domains or [],
        "consensus_confidence": e.consensus_confidence or 0.0,
        "cultural_associations": e.cultural_associations or [],
        "geographical_associations": e.geographical_associations or [],
    }


class EntityService:
    """Read-only queries over entities."""

    def __init__(self, session: Session):
        self.session = session

    def list_entities(
        self,
        entity_type: Optional[str] = None,
        alignment: Optional[str] = None,
        realm: Optional[str] = None,
        hierarchy_level_min: Optional[int] = None,
        hierarchy_level_max: Optional[int] = None,
        confidence_min: Optional[float] = None,
        culture_id: Optional[int] = None,
        region_id: Optional[int] = None,
        power: Optional[str] = None,
        domain: Optional[str] = None,
        q: Optional[str] = None,
        page: int = 1,
        per_page: int = 50,
        sort: str = "-consensus_confidence,name",
    ) -> tuple[list[dict], int]:
        stmt = select(Entity)

        if entity_type:
            stmt = stmt.where(Entity.entity_type == entity_type)
        if alignment:
            stmt = stmt.where(Entity.alignment == alignment)
        if realm:
            stmt = stmt.where(Entity.realm == realm)
        if hierarchy_level_min is not None:
            stmt = stmt.where(Entity.hierarchy_level >= hierarchy_level_min)
        if hierarchy_level_max is not None:
            stmt = stmt.where(Entity.hierarchy_level <= hierarchy_level_max)
        if confidence_min is not None:
            stmt = stmt.where(Entity.consensus_confidence >= confidence_min)
        if power:
            stmt = stmt.where(Entity.powers.op("?")(power))
        if domain:
            stmt = stmt.where(Entity.domains.op("?")(domain))
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                or_(
                    Entity.name.ilike(like),
                    Entity.description.ilike(like),
                    cast(Entity.alternate_names, Text).ilike(like),
                )
            )

        total = self.session.execute(
            select(func.count()).select_from(stmt.subquery())
        ).scalar_one()

        stmt = _apply_sort(stmt, sort)
        stmt = stmt.offset((page - 1) * per_page).limit(per_page)

        rows = self.session.execute(stmt).scalars().all()
        return [_entity_to_summary(e) for e in rows], total

    def get_entity(self, entity_id: int) -> Optional[dict]:
        entity = self.session.get(Entity, entity_id)
        if entity is None:
            return None

        rels_out = self.session.execute(
            select(EntityRelationship).where(EntityRelationship.source_entity_id == entity_id)
        ).scalars().all()
        rels_in = self.session.execute(
            select(EntityRelationship).where(EntityRelationship.target_entity_id == entity_id)
        ).scalars().all()

        relationships: dict[str, list[dict]] = {}
        for rel in rels_out:
            target = self.session.get(Entity, rel.target_entity_id)
            relationships.setdefault(rel.relationship_type, []).append({
                "entity_id": rel.target_entity_id,
                "entity_name": target.name if target else None,
                "relationship_type": rel.relationship_type,
                "description": rel.description,
                "confidence": rel.extraction_confidence or 0.0,
                "sources": rel.provenance_sources or [],
                "cultural_context": rel.cultural_context or [],
                "direction": "out",
            })
        for rel in rels_in:
            inverse_label = INVERSE_REL_LABELS.get(rel.relationship_type, rel.relationship_type)
            # Skip symmetric duplicates (already added as outgoing)
            if inverse_label == rel.relationship_type and rel.source_entity_id in (
                r["entity_id"] for rtype in relationships.values() for r in rtype
            ):
                continue
            source = self.session.get(Entity, rel.source_entity_id)
            relationships.setdefault(inverse_label, []).append({
                "entity_id": rel.source_entity_id,
                "entity_name": source.name if source else None,
                "relationship_type": inverse_label,
                "description": rel.description,
                "confidence": rel.extraction_confidence or 0.0,
                "sources": rel.provenance_sources or [],
                "cultural_context": rel.cultural_context or [],
                "direction": "in",
            })

        pc_rows = self.session.execute(
            select(PlantSpiritConnection).where(PlantSpiritConnection.entity_id == entity_id)
        ).scalars().all()
        plant_connections = [
            {
                "compound_id": pc.compound_id,
                "compound_name": None,
                "relationship_type": pc.relationship_type,
                "preparation": pc.preparation_method,
                "confidence": pc.extraction_confidence or 0.0,
                "sources": pc.provenance_sources or [],
                "cultural_context": pc.cultural_association or [],
            }
            for pc in pc_rows
        ]

        source_ids = list(entity.provenance_sources or [])
        sources: list[dict] = []
        if source_ids:
            src_rows = self.session.execute(
                select(IngestionSource).where(IngestionSource.id.in_(source_ids))
            ).scalars().all()
            sources = [
                {
                    "id": s.id,
                    "source_name": s.source_name,
                    "source_type": s.source_type,
                    "authors": s.authors or [],
                    "publication_year": s.publication_year,
                    "credibility_score": s.credibility_score or 0.0,
                }
                for s in src_rows
            ]

        extraction_ids = list(entity.extraction_instances or [])
        extraction_details: list[dict] = []
        if extraction_ids:
            ext_rows = self.session.execute(
                select(IngestedEntity).where(IngestedEntity.id.in_(extraction_ids))
            ).scalars().all()
            extraction_details = [
                {
                    "ingested_entity_id": ie.id,
                    "extraction_method": ie.extraction_method,
                    "llm_model": ie.llm_model_used,
                    "llm_temperature": ie.llm_temperature,
                    "raw_quote": ie.quote_context,
                    "confidence": ie.extraction_confidence or 0.0,
                }
                for ie in ext_rows
            ]

        summary = _entity_to_summary(entity)
        summary.update({
            "description": entity.description,
            "alternate_names": entity.alternate_names or {},
            "relationships": relationships,
            "plant_connections": plant_connections,
            "sources": sources,
            "extraction_details": extraction_details,
            "first_documented_year": entity.first_documented_year,
            "evidence_period_start": entity.evidence_period_start,
            "evidence_period_end": entity.evidence_period_end,
            "historical_notes": entity.historical_notes,
            "external_ids": entity.external_ids or {},
            "review_status": entity.review_status,
            "created_at": entity.created_at.isoformat() if entity.created_at else None,
            "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
        })
        return summary

    def get_entity_relationships(self, entity_id: int) -> list[dict]:
        rows = self.session.execute(
            select(EntityRelationship).where(EntityRelationship.source_entity_id == entity_id)
        ).scalars().all()
        return [
            {
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
            for r in rows
        ]

    def get_entity_plant_connections(self, entity_id: int) -> list[dict]:
        rows = self.session.execute(
            select(PlantSpiritConnection).where(PlantSpiritConnection.entity_id == entity_id)
        ).scalars().all()
        return [
            {
                "id": pc.id,
                "entity_id": pc.entity_id,
                "compound_id": pc.compound_id,
                "relationship_type": pc.relationship_type,
                "preparation_method": pc.preparation_method,
                "context_description": pc.context_description,
                "cultural_association": pc.cultural_association or [],
                "geographical_association": pc.geographical_association or [],
                "confidence": pc.extraction_confidence or 0.0,
            }
            for pc in rows
        ]


def compute_pagination(total: int, page: int, per_page: int) -> dict:
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": math.ceil(total / per_page) if per_page else 0,
    }
