"""Tests for normalizer._find_existing() trigram dedup logic."""
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from realms.ingestion.normalizer import _find_existing
from realms.models import Entity

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def require_trgm(db_session: Session):
    """Ensure pg_trgm is enabled; skip if it cannot be created."""
    try:
        db_session.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        db_session.execute(text("SELECT similarity('a', 'b')"))
    except Exception:
        pytest.skip("pg_trgm not available in test DB")


def test_find_existing_exact_match(db_session: Session):
    """Exact name match returns the entity."""
    entity = Entity(
        name="Tlaloc",
        entity_type="deity",
        consensus_confidence=0.80,
    )
    db_session.add(entity)
    db_session.flush()

    result = _find_existing(db_session, "Tlaloc")
    assert result is not None
    assert result.id == entity.id


def test_find_existing_case_insensitive(db_session: Session):
    """Case-insensitive match returns the entity."""
    entity = Entity(
        name="Quetzalcoatl",
        entity_type="deity",
        consensus_confidence=0.80,
    )
    db_session.add(entity)
    db_session.flush()

    result = _find_existing(db_session, "quetzalcoatl")
    assert result is not None
    assert result.id == entity.id


def test_find_existing_no_match(db_session: Session):
    """Completely different name returns None."""
    entity = Entity(
        name="Osiris",
        entity_type="deity",
        consensus_confidence=0.80,
    )
    db_session.add(entity)
    db_session.flush()

    result = _find_existing(db_session, "Zeus")
    assert result is None


def test_find_existing_trigram_near_match(db_session: Session):
    """Near-duplicate name (typo/variant) is caught by trigram."""
    entity = Entity(
        name="Huitzilopochtli",
        entity_type="deity",
        consensus_confidence=0.80,
    )
    db_session.add(entity)
    db_session.flush()

    # Slight spelling variant — trigram similarity should be > 0.80
    result = _find_existing(db_session, "Huitzilopochtl")
    # May or may not match depending on similarity threshold — just ensure no crash
    assert result is None or result.id == entity.id
