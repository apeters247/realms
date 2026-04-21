"""Data export endpoints (CSV / JSON / BibTeX / CSL-JSON dumps of public data)."""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from datetime import datetime, timezone
from typing import Iterable

from fastapi import APIRouter, HTTPException, Request
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


# -------------- citation formats for a single entity --------------

def _bib_key(name: str, entity_id: int) -> str:
    """Slugified BibTeX key: realms:<slug>-<id>."""
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:60] or f"e{entity_id}"
    return f"realms-{slug}-{entity_id}"


def _first_three_sentences(text: str | None) -> str:
    if not text:
        return ""
    # Trim to ~400 chars; honour sentence boundaries.
    snippet = text[:480]
    parts = re.split(r"(?<=[.!?])\s+", snippet)
    return " ".join(parts[:3]).strip()


def _build_entity_payload(entity: Entity, canonical_url: str) -> dict:
    return {
        "id": entity.id,
        "name": entity.name,
        "entity_type": entity.entity_type,
        "alignment": entity.alignment,
        "realm": entity.realm,
        "description": entity.description,
        "powers": entity.powers or [],
        "domains": entity.domains or [],
        "cultural_associations": entity.cultural_associations or [],
        "geographical_associations": entity.geographical_associations or [],
        "alternate_names": entity.alternate_names or {},
        "external_ids": entity.external_ids or {},
        "first_documented_year": entity.first_documented_year,
        "evidence_period_start": entity.evidence_period_start,
        "evidence_period_end": entity.evidence_period_end,
        "consensus_confidence": float(entity.consensus_confidence or 0.0),
        "canonical_url": canonical_url,
    }


def _canonical_url(request: Request, path: str) -> str:
    """Build an absolute canonical URL. Honours X-Forwarded-Proto/Host when set."""
    host = request.headers.get("x-forwarded-host") or request.url.netloc
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    return f"{proto}://{host}{path}"


@router.get("/entity/{entity_id}.csl.json")
async def export_entity_csl(entity_id: int, request: Request):
    """CSL-JSON format suitable for Zotero / Mendeley / Pandoc."""
    with get_db_session() as session:
        entity = session.get(Entity, entity_id)
        if entity is None:
            raise HTTPException(404, detail="entity not found")
        slug = re.sub(r"[^a-z0-9]+", "-", entity.name.lower()).strip("-")[:80]
        canonical = _canonical_url(request, f"/app/entity/{slug}/")
        item = {
            "id": f"realms-{entity.id}",
            "type": "entry-encyclopedia",
            "title": entity.name,
            "container-title": "REALMS — Research Entity Archive for Light and Metaphysical Spirit Hierarchies",
            "URL": canonical,
            "abstract": _first_three_sentences(entity.description or ""),
            "note": "CC-BY-4.0",
        }
        if entity.first_documented_year is not None:
            yr = entity.first_documented_year
            item["issued"] = {"date-parts": [[abs(yr) if yr >= 0 else -abs(yr)]]}
        return Response(
            content=json.dumps([item], ensure_ascii=False, indent=2),
            media_type="application/vnd.citationstyles.csl+json",
        )


@router.get("/entity/{entity_id}.json")
async def export_entity_json(entity_id: int, request: Request):
    with get_db_session() as session:
        entity = session.get(Entity, entity_id)
        if entity is None:
            raise HTTPException(404, detail="entity not found")
        slug = re.sub(r"[^a-z0-9]+", "-", entity.name.lower()).strip("-")[:80]
        canonical = _canonical_url(request, f"/app/entity/{slug}/")
        payload = _build_entity_payload(entity, canonical)
        return {"data": payload, "meta": {"format": "realms-entity/1", "license": "CC-BY-4.0"}}


@router.get("/entity/{entity_id}.bib")
async def export_entity_bibtex(entity_id: int, request: Request):
    with get_db_session() as session:
        entity = session.get(Entity, entity_id)
        if entity is None:
            raise HTTPException(404, detail="entity not found")
        slug = re.sub(r"[^a-z0-9]+", "-", entity.name.lower()).strip("-")[:80]
        canonical = _canonical_url(request, f"/app/entity/{slug}/")
        key = _bib_key(entity.name, entity.id)

        year_line = ""
        if entity.first_documented_year is not None:
            year_line = f"  year         = {{{entity.first_documented_year}}},\n"
        note = _first_three_sentences(entity.description)
        culture = (entity.cultural_associations or [""])[0]

        bib = (
            f"@misc{{{key},\n"
            f"  title        = {{{_escape_bibtex(entity.name)}}},\n"
            f"  author       = {{REALMS}},\n"
            f"  howpublished = {{REALMS — Research Entity Archive for Light and Metaphysical Spirit Hierarchies}},\n"
            f"  url          = {{{canonical}}},\n"
            f"{year_line}"
            f"  note         = {{{_escape_bibtex(note)}{' · ' + _escape_bibtex(culture) if culture else ''}}},\n"
            f"  license      = {{CC-BY-4.0}}\n"
            f"}}\n"
        )
        return Response(content=bib, media_type="application/x-bibtex")


def _escape_bibtex(s: str) -> str:
    if not s:
        return ""
    return (s.replace("\\", r"\\")
             .replace("{", r"\{").replace("}", r"\}")
             .replace("%", r"\%").replace("&", r"\&")
             .replace("$", r"\$").replace("#", r"\#"))



# -------------- full dataset dump --------------

_README_BODY = """# REALMS Knowledge Base — Full Dataset Dump

**Generated:** {generated}
**Entities:** {entities}
**Relationships:** {relationships}
**Sources:** {sources}
**Cultures / traditions:** {cultures}
**License:** CC-BY-4.0 — reuse with attribution.

## Files in this archive

- ``entities.json`` — every entity with description, alternate names, powers, domains, cultural + geographical associations, temporal fields, external IDs, and consensus confidence.
- ``entities.csv`` — flat CSV, same data.
- ``relationships.csv`` — typed + co-occurrence edges.
- ``cultures.json`` — traditions metadata.
- ``sources.json`` — source catalogue (Wikipedia, archive.org, PubMed) with URLs, DOIs, fetch timestamps.
- ``LICENSE.txt`` — CC-BY-4.0 text.
- ``CITATION.cff`` — machine-readable citation format.

## Attribution

```
REALMS — Research Entity Archive for Light and Metaphysical Spirit Hierarchies.
{generated}. https://realms.cloud/. Licensed CC-BY-4.0.
```

## How the data is built

See https://<your-realms-domain>/about/methodology/ for the four-stage
extraction + verification pipeline. Every field in ``entities.json`` has
at least one source quote backing it (visible on the entity page);
corpus-level integrity is measured nightly by an independent oracle
sampler and published at ``/integrity/stats``.

## Scope

- **Tier 1 (classical religious + indigenous traditions)** — deities,
  orishas, kami, yakshas, angels, spirits, ancestors.
- **Tier 2 (regional folklore + culturally-attested cryptids)** —
  wendigo, leshy, aswang, kelpie, chullachaqui, kitsune, and kin.

Tier 3 (modern entheogenic visionary) and Tier 4 (modern occult /
fiction / UFO-adjacent) content is explicitly excluded.
"""


_CITATION_CFF = """cff-version: 1.2.0
message: "If you use REALMS in your work, please cite it."
title: "REALMS — Research Entity Archive for Light and Metaphysical Spirit Hierarchies"
type: dataset
url: "https://realms.cloud/"
license: CC-BY-4.0
"""


_LICENSE = """Creative Commons Attribution 4.0 International (CC-BY-4.0)

You are free to:
  Share — copy and redistribute the material in any medium or format
  Adapt — remix, transform, and build upon the material for any purpose, even commercially.

Under the following terms:
  Attribution — You must give appropriate credit, provide a link to the license,
  and indicate if changes were made.

Full text: https://creativecommons.org/licenses/by/4.0/legalcode
"""


@router.get("/dataset.zip")
async def export_dataset_zip():
    """Streaming ZIP of the entire public corpus.

    Generated on-demand (no server cache yet). For a 2000-entity corpus
    the zip is ~5MB; for 10k entities, ~25MB. If this grows too large
    we'll add a nightly pre-built cache, but on-demand is fine at
    launch scale.
    """
    with get_db_session() as session:
        entities = session.execute(select(Entity).order_by(Entity.id)).scalars().all()
        rels = session.execute(
            select(EntityRelationship).order_by(EntityRelationship.id)
        ).scalars().all()
        cultures = session.execute(select(Culture).order_by(Culture.id)).scalars().all()
        sources = session.execute(
            select(IngestionSource).order_by(IngestionSource.id)
        ).scalars().all()

        entities_json = [
            {
                "id": e.id, "name": e.name, "entity_type": e.entity_type,
                "alignment": e.alignment, "realm": e.realm,
                "description": e.description,
                "alternate_names": e.alternate_names or {},
                "powers": e.powers or [], "domains": e.domains or [],
                "cultural_associations": e.cultural_associations or [],
                "geographical_associations": e.geographical_associations or [],
                "external_ids": e.external_ids or {},
                "first_documented_year": e.first_documented_year,
                "evidence_period_start": e.evidence_period_start,
                "evidence_period_end": e.evidence_period_end,
                "consensus_confidence": float(e.consensus_confidence or 0.0),
                "provenance_sources": e.provenance_sources or [],
            }
            for e in entities
        ]

        rels_csv = io.StringIO()
        cw = csv.writer(rels_csv, quoting=csv.QUOTE_MINIMAL)
        cw.writerow(["id", "source_entity_id", "target_entity_id",
                     "relationship_type", "description", "strength",
                     "confidence"])
        for r in rels:
            cw.writerow([r.id, r.source_entity_id, r.target_entity_id,
                         r.relationship_type, _jsonify(r.description),
                         r.strength or "",
                         r.extraction_confidence or ""])

        cultures_json = [
            {"id": c.id, "name": c.name, "region": c.region,
             "language_family": c.language_family,
             "tradition_type": c.tradition_type,
             "description": c.description}
            for c in cultures
        ]

        sources_json = [
            {"id": s.id, "source_type": s.source_type,
             "source_name": s.source_name,
             "url": s.url, "doi": s.doi,
             "peer_reviewed": bool(s.peer_reviewed),
             "credibility_score": float(s.credibility_score or 0.0),
             "ingestion_status": s.ingestion_status,
             "processed_at": s.processed_at.isoformat() if s.processed_at else None}
            for s in sources
        ]

        ent_csv = io.StringIO()
        cw2 = csv.writer(ent_csv, quoting=csv.QUOTE_MINIMAL)
        cw2.writerow(["id", "name", "entity_type", "alignment", "realm",
                      "description", "cultural_associations",
                      "geographical_associations", "consensus_confidence",
                      "first_documented_year"])
        for e in entities_json:
            cw2.writerow([
                e["id"], e["name"], e["entity_type"] or "",
                e["alignment"] or "", e["realm"] or "",
                (e["description"] or "").replace("\n", " "),
                _jsonify(e["cultural_associations"]),
                _jsonify(e["geographical_associations"]),
                e["consensus_confidence"],
                e["first_documented_year"] or "",
            ])

    generated = datetime.now(timezone.utc).isoformat()
    readme = _README_BODY.format(
        generated=generated,
        entities=len(entities),
        relationships=len(rels),
        sources=len(sources),
        cultures=len(cultures),
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr("README.md", readme)
        zf.writestr("LICENSE.txt", _LICENSE)
        zf.writestr("CITATION.cff", _CITATION_CFF)
        zf.writestr("entities.json",
                    json.dumps(entities_json, ensure_ascii=False, indent=2))
        zf.writestr("entities.csv", ent_csv.getvalue())
        zf.writestr("relationships.csv", rels_csv.getvalue())
        zf.writestr("cultures.json",
                    json.dumps(cultures_json, ensure_ascii=False, indent=2))
        zf.writestr("sources.json",
                    json.dumps(sources_json, ensure_ascii=False, indent=2))

    buf.seek(0)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M")
    return Response(
        content=buf.read(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="realms-{stamp}.zip"',
            "Cache-Control": "public, max-age=3600",
        },
    )
