import pytest
from sqlalchemy import select
from realms.models import Entity, EntityRelationship, IngestedEntity, IngestionSource
from scripts.purge_fictional_entities import find_fictional_entities, purge_entities

pytestmark = pytest.mark.integration


@pytest.fixture()
def seeded_source(db_session):
    s = IngestionSource(source_type="wikipedia", source_name="test", url="https://example.com",
                        ingestion_status="completed")
    db_session.add(s)
    db_session.flush()
    return s.id


@pytest.fixture()
def fictional_entity(db_session, seeded_source):
    e = Entity(
        name="Iron Fist",
        description="Iron Fist is a fictional character appearing in Marvel Comics.",
        consensus_confidence=0.8,
        provenance_sources=[seeded_source],
        extraction_instances=[],
    )
    db_session.add(e)
    db_session.flush()
    return e


@pytest.fixture()
def real_entity(db_session, seeded_source):
    e = Entity(
        name="Ogoun",
        description="Ogoun is the Yoruba and Vodou spirit of iron, warfare, and labour.",
        consensus_confidence=0.8,
        provenance_sources=[seeded_source],
        extraction_instances=[],
    )
    db_session.add(e)
    db_session.flush()
    return e


def test_find_fictional_entities_matches_marvel(db_session, fictional_entity, real_entity):
    matches = find_fictional_entities(db_session)
    ids = [m[0] for m in matches]
    assert fictional_entity.id in ids
    assert real_entity.id not in ids


def test_find_fictional_entities_returns_signal(db_session, fictional_entity):
    matches = find_fictional_entities(db_session)
    match = next(m for m in matches if m[0] == fictional_entity.id)
    assert "marvel comics" in match[2].lower()


def test_purge_entities_deletes_fictional(db_session, fictional_entity, real_entity):
    purge_entities(db_session, [fictional_entity.id])
    db_session.commit()
    survivor = db_session.execute(select(Entity).where(Entity.id == real_entity.id)).scalar_one_or_none()
    deleted = db_session.execute(select(Entity).where(Entity.id == fictional_entity.id)).scalar_one_or_none()
    assert survivor is not None
    assert deleted is None


def test_purge_entities_cascades_relationships(db_session, fictional_entity, real_entity):
    rel = EntityRelationship(
        source_entity_id=fictional_entity.id,
        target_entity_id=real_entity.id,
        relationship_type="allied_with",
        strength="weak",
        extraction_confidence=0.5,
    )
    db_session.add(rel)
    db_session.flush()
    purge_entities(db_session, [fictional_entity.id])
    db_session.commit()
    remaining = db_session.execute(
        select(EntityRelationship).where(
            (EntityRelationship.source_entity_id == fictional_entity.id) |
            (EntityRelationship.target_entity_id == fictional_entity.id)
        )
    ).scalars().all()
    assert len(remaining) == 0
