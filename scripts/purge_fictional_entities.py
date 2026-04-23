"""Delete entities whose description reveals fictional/entertainment origin.

Complements purge_hallucinations.py (which checks cultural_associations).
This script checks the description field for unambiguous fictional media signals.

Usage:
    docker exec realms-api python -m scripts.purge_fictional_entities
    docker exec realms-api python -m scripts.purge_fictional_entities --apply
"""
from __future__ import annotations

import argparse
import logging

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from realms.models import Entity, EntityRelationship, IngestedEntity
from realms.utils.database import get_db_session

log = logging.getLogger("realms.purge_fictional")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

FICTIONAL_SIGNALS = [
    "marvel comics",
    "dc comics",
    "fictional character",
    "fictional group",
    "fictional being",
    "abs-cbn",
    "telefantasya",
    "silicon knights",
    "comic book",
    "video game",
    "animated series",
    "television series",
    "novel by",
    "film by",
    "movie character",
]


def find_fictional_entities(session: Session) -> list[tuple[int, str, str]]:
    """Return list of (entity_id, name, matched_signal) for fictional entities."""
    entities = session.execute(select(Entity).where(Entity.description.isnot(None))).scalars().all()
    matches = []
    for e in entities:
        desc = (e.description or "").lower()
        for signal in FICTIONAL_SIGNALS:
            if signal in desc:
                matches.append((e.id, e.name, signal))
                break
    return matches


def purge_entities(session: Session, entity_ids: list[int]) -> dict:
    """Delete entities and cascade to relationships and ingested_entities.

    EntityRelationship rows cascade automatically via the FK ondelete=CASCADE,
    but we issue an explicit DELETE first so the rowcount is accurate for
    reporting. IngestedEntity rows are matched by entity_name_normalized.
    """
    if not entity_ids:
        return {"entities": 0, "relationships": 0, "extractions": 0}

    # Collect entity names before deletion for extractions cascade.
    names = session.execute(
        select(Entity.name).where(Entity.id.in_(entity_ids))
    ).scalars().all()

    rel_result = session.execute(
        delete(EntityRelationship).where(
            (EntityRelationship.source_entity_id.in_(entity_ids)) |
            (EntityRelationship.target_entity_id.in_(entity_ids))
        )
    )
    ext_result = session.execute(
        delete(IngestedEntity).where(
            IngestedEntity.entity_name_raw.in_(names) |
            IngestedEntity.entity_name_normalized.in_(names)
        )
    )
    ent_result = session.execute(
        delete(Entity).where(Entity.id.in_(entity_ids))
    )
    return {
        "entities": ent_result.rowcount,
        "relationships": rel_result.rowcount,
        "extractions": ext_result.rowcount,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually delete (default: dry-run)")
    args = parser.parse_args()

    with get_db_session() as session:
        matches = find_fictional_entities(session)
        log.info("Found %d fictional entities", len(matches))
        for eid, name, signal in matches:
            log.info("  [%d] %r -> matched signal: %r", eid, name, signal)

        if not args.apply:
            log.info("Dry-run mode — pass --apply to delete")
            return

        entity_ids = [m[0] for m in matches]
        counts = purge_entities(session, entity_ids)
        session.commit()
        log.info(
            "Purged: %d entities, %d relationships, %d extractions",
            counts["entities"], counts["relationships"], counts["extractions"],
        )


if __name__ == "__main__":
    main()
