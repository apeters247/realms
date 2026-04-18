"""Insert a minimal reproducible dataset for dev and tests.

Run only against dev/test databases. Safe to re-run: uses name-based
lookups so it won't duplicate data.
"""
from __future__ import annotations

import logging
import sys

from sqlalchemy import select

from realms.models import (
    Culture,
    Entity,
    EntityCategory,
    EntityClass,
    EntityRelationship,
    GeographicRegion,
    IngestedEntity,
    IngestionSource,
    PlantSpiritConnection,
)
from realms.utils.database import get_db_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("realms.seed")


def _get_or_create(session, model, filters: dict, defaults: dict):
    """Fetch by filters or insert with filters+defaults."""
    stmt = select(model)
    for key, value in filters.items():
        stmt = stmt.where(getattr(model, key) == value)
    instance = session.execute(stmt).scalar_one_or_none()
    if instance is not None:
        return instance
    params = {**filters, **defaults}
    instance = model(**params)
    session.add(instance)
    session.flush()
    return instance


def seed(session) -> dict:
    """Populate minimum viable fixtures. Returns created IDs."""
    amazon = _get_or_create(
        session, GeographicRegion,
        {"name": "Amazon Basin"},
        {
            "region_type": "tropical",
            "countries": ["BR", "PE", "CO", "EC", "BO"],
            "center_latitude": -3.4653,
            "center_longitude": -62.2159,
        },
    )
    yanomami = _get_or_create(
        session, Culture,
        {"name": "Yanomami"},
        {
            "language_family": "Yanomaman",
            "region": "Upper Amazon",
            "countries": ["BR", "VE"],
            "tradition_type": "shamanism",
            "primary_plants": ["Banisteriopsis caapi", "Virola theiodora"],
        },
    )
    shipibo = _get_or_create(
        session, Culture,
        {"name": "Shipibo-Konibo"},
        {
            "language_family": "Panoan",
            "region": "Upper Amazon",
            "countries": ["PE"],
            "tradition_type": "vegetalismo",
            "primary_plants": ["Banisteriopsis caapi", "Psychotria viridis"],
        },
    )

    source = _get_or_create(
        session, IngestionSource,
        {"source_name": "The Falling Sky: Words of a Yanomami Shaman"},
        {
            "source_type": "book",
            "authors": [{"name": "Davi Kopenawa", "affiliation": "Yanomami shaman"}],
            "publication_year": 2013,
            "credibility_score": 0.95,
            "peer_reviewed": True,
            "ingestion_status": "completed",
        },
    )

    plant_cat = _get_or_create(
        session, EntityCategory,
        {"name": "plant_spirit"},
        {"description": "Plant-associated teacher spirits", "icon_emoji": "\U0001f33f"},
    )
    animal_cat = _get_or_create(
        session, EntityCategory,
        {"name": "animal_ally"},
        {"description": "Animal-form ally spirits", "icon_emoji": "\U0001f406"},
    )

    chullachaqui_class = _get_or_create(
        session, EntityClass,
        {"name": "Chullachaqui"},
        {
            "category_id": plant_cat.id,
            "description": "Forest guardian spirit in Amazonian mestizo tradition",
            "core_powers": ["protection", "misdirection", "plant_teaching"],
            "hierarchy_level": 5,
            "hierarchy_name": "guardian",
            "confidence_score": 0.85,
        },
    )
    xapiri_class = _get_or_create(
        session, EntityClass,
        {"name": "Xapirip\u00eb"},
        {
            "category_id": animal_cat.id,
            "description": "Ancestral animal spirits of Yanomami shamans",
            "core_powers": ["healing", "divination", "plant_teaching"],
            "hierarchy_level": 8,
            "hierarchy_name": "shamanic spirit",
            "confidence_score": 0.90,
        },
    )

    extraction_chullachaqui = _get_or_create(
        session, IngestedEntity,
        {"entity_name_normalized": "Chullachaqui", "source_id": source.id},
        {
            "extraction_method": "llm_prompt_v1",
            "llm_model_used": "deepseek-chat",
            "llm_temperature": 0.1,
            "llm_prompt_version": "v1",
            "entity_name_raw": "chullachaqui",
            "extraction_confidence": 0.88,
            "status": "confirmed",
        },
    )
    extraction_xapiri = _get_or_create(
        session, IngestedEntity,
        {"entity_name_normalized": "Xapirip\u00eb", "source_id": source.id},
        {
            "extraction_method": "llm_prompt_v1",
            "llm_model_used": "deepseek-chat",
            "llm_temperature": 0.1,
            "llm_prompt_version": "v1",
            "entity_name_raw": "xapirip\u00eb",
            "extraction_confidence": 0.92,
            "status": "confirmed",
        },
    )

    chullachaqui = _get_or_create(
        session, Entity,
        {"name": "Chullachaqui"},
        {
            "entity_class_id": chullachaqui_class.id,
            "entity_type": "plant_spirit",
            "alignment": "neutral",
            "realm": "forest",
            "hierarchy_level": 5,
            "hierarchy_name": "guardian",
            "description": "A shapeshifting forest guardian with one foot smaller than the other.",
            "alternate_names": {"Quechua": ["chullachaki"], "Spanish": ["due\u00f1o del monte"]},
            "powers": ["protection", "misdirection", "plant_teaching"],
            "domains": ["forest_health", "plant_knowledge"],
            "cultural_associations": ["Shipibo-Konibo"],
            "geographical_associations": ["Amazon Basin"],
            "provenance_sources": [source.id],
            "extraction_instances": [extraction_chullachaqui.id],
            "consensus_confidence": 0.88,
        },
    )
    xapiri = _get_or_create(
        session, Entity,
        {"name": "Xapirip\u00eb"},
        {
            "entity_class_id": xapiri_class.id,
            "entity_type": "animal_ally",
            "alignment": "beneficial",
            "realm": "forest",
            "hierarchy_level": 8,
            "hierarchy_name": "shamanic spirit",
            "description": "Tiny humanoid ancestral spirits that teach Yanomami shamans.",
            "alternate_names": {"Yanomami": ["xapiri", "xapirip\u00eb"]},
            "powers": ["healing", "protection", "divination", "plant_teaching"],
            "domains": ["forest_health", "spirit_world_access"],
            "cultural_associations": ["Yanomami"],
            "geographical_associations": ["Amazon Basin"],
            "provenance_sources": [source.id],
            "extraction_instances": [extraction_xapiri.id],
            "consensus_confidence": 0.95,
        },
    )

    _get_or_create(
        session, EntityRelationship,
        {
            "source_entity_id": xapiri.id,
            "target_entity_id": chullachaqui.id,
            "relationship_type": "allied_with",
        },
        {
            "description": "Cooperate in healing ceremonies in the Amazon",
            "strength": "moderate",
            "extraction_confidence": 0.8,
            "provenance_sources": [source.id],
            "cultural_context": ["Yanomami"],
        },
    )
    _get_or_create(
        session, PlantSpiritConnection,
        {"entity_id": xapiri.id, "compound_id": None, "relationship_type": "teacher_of"},
        {
            "preparation_method": "ayahuasca brew",
            "context_description": "Teaches shamans through ayahuasca ceremonies",
            "cultural_association": ["Yanomami", "Shipibo-Konibo"],
            "geographical_association": ["Amazon Basin"],
            "provenance_sources": [source.id],
            "extraction_confidence": 0.9,
        },
    )

    session.commit()
    ids = {
        "region_amazon": amazon.id,
        "culture_yanomami": yanomami.id,
        "culture_shipibo": shipibo.id,
        "source_falling_sky": source.id,
        "category_plant": plant_cat.id,
        "category_animal": animal_cat.id,
        "class_chullachaqui": chullachaqui_class.id,
        "class_xapiri": xapiri_class.id,
        "entity_chullachaqui": chullachaqui.id,
        "entity_xapiri": xapiri.id,
    }
    log.info("Seed complete: %s", ids)
    return ids


def main() -> int:
    with get_db_session() as session:
        seed(session)
    return 0


if __name__ == "__main__":
    sys.exit(main())
