"""Phase 6 — read-only view of external identifiers.

Write endpoints live under /review/entities/{id}/link|unlink and require
the review token.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from realms.models import Entity
from realms.utils.database import get_db_session

router = APIRouter()


# Authority URL templates per system.
_URL_TEMPLATES = {
    "wikidata": "https://www.wikidata.org/wiki/{id}",
    "viaf": "https://viaf.org/viaf/{id}",
    "wordnet": "http://wordnet-rdf.princeton.edu/lemma/{id}",
    "geonames": "https://www.geonames.org/{id}",
}


@router.get("/{entity_id}")
async def entity_external_links(entity_id: int):
    with get_db_session() as session:
        entity = session.get(Entity, entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="entity not found")
        links = []
        for system, ext_id in (entity.external_ids or {}).items():
            template = _URL_TEMPLATES.get(system)
            url = template.format(id=ext_id) if template else None
            links.append({
                "system": system,
                "external_id": ext_id,
                "url": url,
            })
        return {"data": {
            "entity_id": entity.id,
            "name": entity.name,
            "links": links,
        }}
