"""Review queue — surface low-confidence entities, and Phase 4 write actions."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update

from realms.api.dependencies import require_review_token
from realms.models import Entity, EntityRelationship, IngestedEntity, ReviewAction
from realms.utils.database import get_db_session

router = APIRouter()

# Whitelist of entity fields a reviewer is allowed to edit.
EDITABLE_FIELDS = {
    "name", "entity_type", "alignment", "realm", "description",
    "powers", "domains", "cultural_associations", "geographical_associations",
    "first_documented_year", "evidence_period_start", "evidence_period_end",
    "historical_notes",
}


def _snapshot_field(entity: Entity, field: str) -> Any:
    return getattr(entity, field, None)


def _log_action(
    session, *, entity_id: int, reviewer: str, action: str,
    field: str | None = None, old_value: Any = None,
    new_value: Any = None, note: str | None = None,
) -> None:
    session.add(ReviewAction(
        entity_id=entity_id,
        reviewer=reviewer,
        action=action,
        field=field,
        old_value=old_value,
        new_value=new_value,
        note=note,
    ))


@router.get("/entities")
async def review_entities(
    confidence_max: float = Query(0.75, ge=0.0, le=1.0,
                                   description="Return entities with consensus_confidence below this"),
    single_source_only: bool = Query(False, description="Only entities derived from a single source"),
    isolated_only: bool = Query(False, description="Only entities with no relationships"),
    limit: int = Query(100, ge=1, le=500),
):
    """Candidates for human review: low confidence, thin provenance, or orphaned."""
    with get_db_session() as session:
        stmt = select(Entity)
        stmt = stmt.where(Entity.consensus_confidence <= confidence_max)
        stmt = stmt.order_by(Entity.consensus_confidence.asc(), Entity.id.asc())
        stmt = stmt.limit(limit)
        candidates = list(session.execute(stmt).scalars().all())

        # Optional: filter to single-source
        if single_source_only:
            candidates = [
                e for e in candidates
                if len(e.provenance_sources or []) <= 1
            ]

        # Optional: filter to isolated
        if isolated_only:
            edge_counts = {}
            if candidates:
                ids = [e.id for e in candidates]
                counts_rows = session.execute(
                    select(EntityRelationship.source_entity_id, func.count().label("n"))
                    .where(EntityRelationship.source_entity_id.in_(ids))
                    .group_by(EntityRelationship.source_entity_id)
                ).all()
                edge_counts = {r[0]: r[1] for r in counts_rows}
                counts_rows = session.execute(
                    select(EntityRelationship.target_entity_id, func.count().label("n"))
                    .where(EntityRelationship.target_entity_id.in_(ids))
                    .group_by(EntityRelationship.target_entity_id)
                ).all()
                for r in counts_rows:
                    edge_counts[r[0]] = edge_counts.get(r[0], 0) + r[1]
            candidates = [e for e in candidates if edge_counts.get(e.id, 0) == 0]

        payload = []
        for e in candidates:
            n_sources = len(e.provenance_sources or [])
            n_extractions = len(e.extraction_instances or [])
            payload.append({
                "id": e.id,
                "name": e.name,
                "entity_type": e.entity_type,
                "alignment": e.alignment,
                "realm": e.realm,
                "consensus_confidence": e.consensus_confidence or 0.0,
                "n_sources": n_sources,
                "n_extractions": n_extractions,
                "cultural_associations": e.cultural_associations or [],
                "description": e.description,
                "flags": [
                    *(["low_confidence"] if (e.consensus_confidence or 0.0) < 0.7 else []),
                    *(["single_source"] if n_sources <= 1 else []),
                ],
            })
        return {"data": payload, "meta": {"count": len(payload)}}


@router.get("/stats")
async def review_stats():
    """Summary counts for QA dashboards."""
    with get_db_session() as session:
        total = session.execute(select(func.count(Entity.id))).scalar_one()
        low_conf = session.execute(
            select(func.count(Entity.id)).where(Entity.consensus_confidence < 0.7)
        ).scalar_one()
        very_low_conf = session.execute(
            select(func.count(Entity.id)).where(Entity.consensus_confidence < 0.5)
        ).scalar_one()
        # entities with only 1 source
        single_source = session.execute(
            select(func.count(Entity.id)).where(
                func.jsonb_array_length(func.coalesce(Entity.provenance_sources, func.cast("[]", Entity.provenance_sources.type))) <= 1
            )
        ).scalar_one()

        # isolated (no outgoing or incoming edges)
        rel_q = session.execute(select(func.count(func.distinct(EntityRelationship.source_entity_id)))).scalar_one()
        rel_t = session.execute(select(func.count(func.distinct(EntityRelationship.target_entity_id)))).scalar_one()
        # combine source+target distinct set via UNION
        connected_ids = session.execute(
            select(EntityRelationship.source_entity_id).distinct().union(
                select(EntityRelationship.target_entity_id).distinct()
            )
        ).all()
        connected_count = len(set(r[0] for r in connected_ids))
        isolated = total - connected_count

        return {
            "data": {
                "total_entities": total,
                "low_confidence": low_conf,          # < 0.7
                "very_low_confidence": very_low_conf,  # < 0.5
                "single_source_entities": single_source,
                "isolated_entities": isolated,
                "connected_entities": connected_count,
            }
        }


# ------------- Phase 4 write endpoints (bearer-gated) -------------


class EditPayload(BaseModel):
    field: str = Field(..., description="Entity column to update")
    value: Any = Field(..., description="New value (type must match the column)")
    note: str | None = Field(None, description="Reviewer rationale")


class LinkPayload(BaseModel):
    system: str = Field(..., description="wikidata | viaf | wordnet")
    external_id: str = Field(..., description="Raw identifier, e.g. Q123 or 12345")
    note: str | None = None


@router.get("/actions")
async def list_actions(
    entity_id: int | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """Recent audit trail entries, optionally filtered by entity."""
    with get_db_session() as session:
        stmt = select(ReviewAction).order_by(ReviewAction.created_at.desc()).limit(limit)
        if entity_id is not None:
            stmt = stmt.where(ReviewAction.entity_id == entity_id)
        rows = list(session.execute(stmt).scalars().all())
        return {"data": [
            {
                "id": r.id,
                "entity_id": r.entity_id,
                "reviewer": r.reviewer,
                "action": r.action,
                "field": r.field,
                "old_value": r.old_value,
                "new_value": r.new_value,
                "note": r.note,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]}


@router.post("/entities/{entity_id}/approve")
async def approve_entity(
    entity_id: int,
    note: str | None = Body(None, embed=True),
    reviewer: str = Depends(require_review_token),
):
    with get_db_session() as session:
        entity = session.get(Entity, entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="entity not found")
        old_status = entity.review_status
        old_confidence = entity.consensus_confidence
        entity.review_status = "approved"
        if (entity.consensus_confidence or 0) < 0.95:
            entity.consensus_confidence = 0.95
        _log_action(
            session, entity_id=entity.id, reviewer=reviewer, action="approve",
            old_value={"review_status": old_status, "consensus_confidence": old_confidence},
            new_value={"review_status": "approved", "consensus_confidence": entity.consensus_confidence},
            note=note,
        )
        session.commit()
        return {"data": {"id": entity.id, "review_status": entity.review_status}}


@router.post("/entities/{entity_id}/reject")
async def reject_entity(
    entity_id: int,
    note: str | None = Body(None, embed=True),
    reviewer: str = Depends(require_review_token),
):
    with get_db_session() as session:
        entity = session.get(Entity, entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="entity not found")
        old_status = entity.review_status
        entity.review_status = "rejected"
        entity.consensus_confidence = 0.0
        _log_action(
            session, entity_id=entity.id, reviewer=reviewer, action="reject",
            old_value={"review_status": old_status},
            new_value={"review_status": "rejected"},
            note=note,
        )
        session.commit()
        return {"data": {"id": entity.id, "review_status": entity.review_status}}


@router.patch("/entities/{entity_id}")
async def edit_entity(
    entity_id: int,
    payload: EditPayload,
    reviewer: str = Depends(require_review_token),
):
    if payload.field not in EDITABLE_FIELDS:
        raise HTTPException(
            status_code=400,
            detail=f"field {payload.field!r} is not editable via review. "
                   f"Allowed: {sorted(EDITABLE_FIELDS)}",
        )
    with get_db_session() as session:
        entity = session.get(Entity, entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="entity not found")
        old = _snapshot_field(entity, payload.field)
        setattr(entity, payload.field, payload.value)
        _log_action(
            session, entity_id=entity.id, reviewer=reviewer, action="edit",
            field=payload.field,
            old_value={payload.field: old},
            new_value={payload.field: payload.value},
            note=payload.note,
        )
        session.commit()
        return {"data": {"id": entity.id, "field": payload.field, "value": payload.value}}


@router.post("/entities/{entity_id}/merge_into/{target_id}")
async def merge_entity(
    entity_id: int,
    target_id: int,
    note: str | None = Body(None, embed=True),
    reviewer: str = Depends(require_review_token),
):
    """Move all relationships from ``entity_id`` to ``target_id`` and soft-delete source.

    Idempotent: if already rejected/merged, returns current state without error.
    """
    if entity_id == target_id:
        raise HTTPException(status_code=400, detail="cannot merge entity into itself")
    with get_db_session() as session:
        src = session.get(Entity, entity_id)
        tgt = session.get(Entity, target_id)
        if src is None or tgt is None:
            raise HTTPException(status_code=404, detail="source or target not found")

        # Re-parent outgoing relationships
        session.execute(
            update(EntityRelationship)
            .where(EntityRelationship.source_entity_id == entity_id)
            .values(source_entity_id=target_id)
        )
        # Re-parent incoming relationships
        session.execute(
            update(EntityRelationship)
            .where(EntityRelationship.target_entity_id == entity_id)
            .values(target_entity_id=target_id)
        )
        # Merge provenance_sources (unique preserving order)
        src_sources = list(src.provenance_sources or [])
        tgt_sources = list(tgt.provenance_sources or [])
        merged = tgt_sources + [s for s in src_sources if s not in tgt_sources]
        tgt.provenance_sources = merged
        # Soft-delete source
        src.review_status = "rejected"
        src.consensus_confidence = 0.0
        _log_action(
            session, entity_id=src.id, reviewer=reviewer, action="merge_into",
            new_value={"target_id": target_id, "merged_sources": len(merged)},
            note=note,
        )
        _log_action(
            session, entity_id=tgt.id, reviewer=reviewer, action="merge_receive",
            new_value={"merged_from": src.id, "provenance_count": len(merged)},
            note=note,
        )
        session.commit()
        return {"data": {"merged": src.id, "into": tgt.id, "provenance_count": len(merged)}}


@router.post("/entities/{entity_id}/suggest")
async def suggest_for_entity(
    entity_id: int,
    reviewer: str = Depends(require_review_token),
):
    """Ask the LLM for field-level correction suggestions. Read-only from the DB side.

    Token-gated because this spends money (OpenRouter call).
    """
    from realms.ingestion.review_suggester import suggest_for_entity as _suggest

    with get_db_session() as session:
        entity = session.get(Entity, entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="entity not found")
        # Snapshot current consensus
        current = {
            "name": entity.name, "entity_type": entity.entity_type,
            "alignment": entity.alignment, "realm": entity.realm,
            "description": entity.description,
            "powers": entity.powers, "domains": entity.domains,
            "cultural_associations": entity.cultural_associations,
        }
        # Pull matching extractions by normalized name
        ex_rows = session.execute(
            select(IngestedEntity).where(
                func.lower(IngestedEntity.entity_name_normalized)
                == (entity.name or "").lower()
            ).limit(20)
        ).scalars().all()
        extractions = [
            {
                "source_id": e.source_id,
                "extraction_confidence": e.extraction_confidence,
                "raw": e.raw_extracted_data,
                "quote": e.quote_context,
            }
            for e in ex_rows
        ]

    try:
        suggestion = _suggest(current, extractions)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"suggester failed: {exc}")

    return {"data": {
        "entity_id": entity_id,
        "suggested_fields": suggestion.suggested_fields,
        "conflicts_detected": suggestion.conflicts_detected,
        "confidence": suggestion.confidence,
        "rationale": suggestion.rationale,
        "model": suggestion.model,
    }}


@router.post("/entities/{entity_id}/link")
async def link_external_id(
    entity_id: int,
    payload: LinkPayload,
    reviewer: str = Depends(require_review_token),
):
    """Phase 6 — attach an external system identifier to an entity."""
    system = payload.system.lower().strip()
    if system not in {"wikidata", "viaf", "wordnet", "geonames"}:
        raise HTTPException(status_code=400, detail=f"unknown system: {system}")
    with get_db_session() as session:
        entity = session.get(Entity, entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="entity not found")
        old = dict(entity.external_ids or {})
        new_map = dict(old)
        new_map[system] = payload.external_id
        entity.external_ids = new_map
        _log_action(
            session, entity_id=entity.id, reviewer=reviewer, action="external_link",
            field=system,
            old_value={"external_ids": old},
            new_value={"external_ids": new_map},
            note=payload.note,
        )
        session.commit()
        return {"data": {"id": entity.id, "external_ids": entity.external_ids}}


@router.post("/entities/{entity_id}/unlink")
async def unlink_external_id(
    entity_id: int,
    system: str = Body(..., embed=True),
    reviewer: str = Depends(require_review_token),
):
    system = system.lower().strip()
    with get_db_session() as session:
        entity = session.get(Entity, entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="entity not found")
        old = dict(entity.external_ids or {})
        if system not in old:
            return {"data": {"id": entity.id, "external_ids": old}}
        new_map = {k: v for k, v in old.items() if k != system}
        entity.external_ids = new_map
        _log_action(
            session, entity_id=entity.id, reviewer=reviewer, action="external_unlink",
            field=system,
            old_value={"external_ids": old},
            new_value={"external_ids": new_map},
        )
        session.commit()
        return {"data": {"id": entity.id, "external_ids": entity.external_ids}}
