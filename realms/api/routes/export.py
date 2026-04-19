"""Data export endpoints (CSV / JSON dumps of public data)."""
from __future__ import annotations

import csv
import io
import json
from typing import Iterable

from fastapi import APIRouter
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select

from realms.models import Culture, Entity, EntityRelationship, GeographicRegion, IngestionSource
from realms.utils.database import get_db_session

router = APIRouter()


def _jsonify(v) -> str:
    if v is None:
        return ""
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def _rows_to_csv(header: list[str], rows: Iterable[list]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
    w.writerow(header)
    for r in rows:
        w.writerow([_jsonify(v) for v in r])
    return buf.getvalue()


# -------------- entities --------------

def _entity_rows():
    with get_db_session() as session:
        rows = session.execute(select(Entity).order_by(Entity.id)).scalars().all()
        for e in rows:
            yield [
                e.id, e.name, e.entity_type, e.alignment, e.realm,
                e.hierarchy_level, e.hierarchy_name,
                e.description,
                e.alternate_names, e.powers, e.domains,
                e.cultural_associations, e.geographical_associations,
                e.provenance_sources, e.consensus_confidence,
                e.created_at.isoformat() if e.created_at else None,
                e.updated_at.isoformat() if e.updated_at else None,
            ]


ENTITY_HEADER = [
    "id", "name", "entity_type", "alignment", "realm",
    "hierarchy_level", "hierarchy_name", "description",
    "alternate_names", "powers", "domains",
    "cultural_associations", "geographical_associations",
    "provenance_sources", "consensus_confidence", "created_at", "updated_at",
]


@router.get("/entities.csv")
async def export_entities_csv():
    body = _rows_to_csv(ENTITY_HEADER, _entity_rows())
    return Response(
        content=body, media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=realms_entities.csv"},
    )


@router.get("/entities.json")
async def export_entities_json():
    with get_db_session() as session:
        rows = session.execute(select(Entity).order_by(Entity.id)).scalars().all()
        payload = [
            {
                "id": e.id,
                "name": e.name,
                "entity_type": e.entity_type,
                "alignment": e.alignment,
                "realm": e.realm,
                "hierarchy_level": e.hierarchy_level,
                "hierarchy_name": e.hierarchy_name,
                "description": e.description,
                "alternate_names": e.alternate_names or {},
                "powers": e.powers or [],
                "domains": e.domains or [],
                "cultural_associations": e.cultural_associations or [],
                "geographical_associations": e.geographical_associations or [],
                "provenance_sources": e.provenance_sources or [],
                "consensus_confidence": e.consensus_confidence or 0.0,
                "created_at": e.created_at.isoformat() if e.created_at else None,
                "updated_at": e.updated_at.isoformat() if e.updated_at else None,
            }
            for e in rows
        ]
        return {"data": payload, "meta": {"count": len(payload)}}


# -------------- relationships --------------

def _rel_rows():
    with get_db_session() as session:
        rows = session.execute(select(EntityRelationship).order_by(EntityRelationship.id)).scalars().all()
        for r in rows:
            yield [
                r.id, r.source_entity_id, r.target_entity_id,
                r.relationship_type, r.description, r.strength,
                r.extraction_confidence, r.cultural_context,
                r.historical_period, r.provenance_sources,
                r.created_at.isoformat() if r.created_at else None,
            ]


@router.get("/relationships.csv")
async def export_relationships_csv():
    header = [
        "id", "source_entity_id", "target_entity_id", "relationship_type",
        "description", "strength", "confidence", "cultural_context",
        "historical_period", "provenance_sources", "created_at",
    ]
    body = _rows_to_csv(header, _rel_rows())
    return Response(
        content=body, media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=realms_relationships.csv"},
    )


# -------------- cultures --------------

@router.get("/cultures.json")
async def export_cultures_json():
    with get_db_session() as session:
        rows = session.execute(select(Culture).order_by(Culture.id)).scalars().all()
        payload = [
            {
                "id": c.id, "name": c.name, "language_family": c.language_family,
                "region": c.region, "countries": c.countries or [],
                "description": c.description, "tradition_type": c.tradition_type,
                "primary_plants": c.primary_plants or [],
            }
            for c in rows
        ]
        return {"data": payload, "meta": {"count": len(payload)}}


# -------------- sources --------------

@router.get("/sources.json")
async def export_sources_json():
    with get_db_session() as session:
        rows = session.execute(select(IngestionSource).order_by(IngestionSource.id)).scalars().all()
        payload = [
            {
                "id": s.id, "source_type": s.source_type, "source_name": s.source_name,
                "authors": s.authors or [], "publication_year": s.publication_year,
                "doi": s.doi, "url": s.url,
                "credibility_score": s.credibility_score or 0.0,
                "peer_reviewed": bool(s.peer_reviewed),
                "ingestion_status": s.ingestion_status,
                "processed_at": s.processed_at.isoformat() if s.processed_at else None,
            }
            for s in rows
        ]
        return {"data": payload, "meta": {"count": len(payload)}}
