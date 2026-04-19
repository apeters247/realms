"""Integration tests for Phase 5 timeline + temporal fields."""
from __future__ import annotations

import pytest

from realms.ingestion.extractor import ExtractedEntity
from realms.ingestion.normalizer import _find_existing, _normalize_name, upsert_entities
from realms.models import Entity


pytestmark = pytest.mark.integration


def _mk_extraction(
    name: str = "Test", *,
    first_attested: int | None = None,
    start: int | None = None,
    end: int | None = None,
    notes: str | None = None,
    confidence: float = 0.8,
) -> ExtractedEntity:
    return ExtractedEntity(
        name=name,
        entity_type=None,
        alignment=None,
        realm=None,
        description=None,
        powers=[],
        domains=[],
        cultural_associations=[],
        geographical_associations=[],
        alternate_names={},
        confidence=confidence,
        quote_context="",
        roles={},
        first_attested_year=first_attested,
        evidence_period_start=start,
        evidence_period_end=end,
        historical_notes=notes,
    )


def test_upsert_stores_temporal_fields(db_session):
    ex = _mk_extraction("Ra", first_attested=-2600, start=-2600, end=600, notes="Old Kingdom to late antiquity")
    upsert_entities(db_session, [ex], source_id=0, extraction_ids_by_name={"ra": 0})
    e = db_session.query(Entity).filter(Entity.name.ilike("Ra")).one()
    assert e.first_documented_year == -2600
    assert e.evidence_period_start == -2600
    assert e.evidence_period_end == 600
    assert "Old Kingdom" in (e.historical_notes or "")


def test_upsert_merge_keeps_earliest_and_widest(db_session):
    ex1 = _mk_extraction("Athena", first_attested=-700, start=-700, end=400)
    upsert_entities(db_session, [ex1], source_id=1, extraction_ids_by_name={"athena": 0})
    ex2 = _mk_extraction("Athena", first_attested=-800, start=-800, end=500, notes="Hellenistic continuation")
    upsert_entities(db_session, [ex2], source_id=2, extraction_ids_by_name={"athena": 0})
    e = db_session.query(Entity).filter(Entity.name.ilike("Athena")).one()
    # earliest first_attested
    assert e.first_documented_year == -800
    # widest period
    assert e.evidence_period_start == -800
    assert e.evidence_period_end == 500
    # notes preserved (first one wins; not overwritten by empty first-seen ext)
    assert "Hellenistic" in (e.historical_notes or "")


def test_timeline_entities_window_inclusive(db_session, client):
    db_session.add_all([
        Entity(name="Sumerian", first_documented_year=-3000, evidence_period_start=-3000, evidence_period_end=-2000),
        Entity(name="Egyptian", first_documented_year=-2600),
        Entity(name="Christian", first_documented_year=100),
    ])
    db_session.commit()
    r = client.get("/timeline/entities?start_year=-3500&end_year=-2000")
    assert r.status_code == 200, r.text
    names = [row["name"] for row in r.json()["data"]]
    assert "Sumerian" in names
    assert "Egyptian" in names
    assert "Christian" not in names


def test_timeline_entities_no_window_requires_dated(db_session, client):
    db_session.add(Entity(name="UndatedEntity"))
    db_session.add(Entity(name="DatedEntity", first_documented_year=500))
    db_session.commit()
    r = client.get("/timeline/entities")
    names = [row["name"] for row in r.json()["data"]]
    assert names == ["DatedEntity"]


def test_timeline_summary_buckets(db_session, client):
    db_session.add_all([
        Entity(name="A", first_documented_year=-500),   # 6th century BCE
        Entity(name="B", first_documented_year=-450),   # 5th century BCE
        Entity(name="C", first_documented_year=100),    # 2nd century CE
        Entity(name="D", first_documented_year=150),    # 2nd century CE
    ])
    db_session.commit()
    r = client.get("/timeline/summary")
    data = r.json()["data"]
    assert data["total_dated"] == 4
    # verify at least one bucket has the expected label
    buckets = {b["century"]: b["count"] for b in data["buckets"]}
    assert buckets.get("2nd century CE") == 2
    assert sum(buckets.values()) == 4


def test_extractor_coerces_nonsense_years_to_none():
    """_coerce_entity should drop clearly-impossible years."""
    from realms.ingestion.extractor import _coerce_entity
    e = _coerce_entity({
        "name": "Thing",
        "first_attested_year": 999999,  # out of plausible range
        "evidence_period_start": "not a number",
    })
    assert e is not None
    assert e.first_attested_year is None
    assert e.evidence_period_start is None


def test_extractor_accepts_negative_bce_years():
    from realms.ingestion.extractor import _coerce_entity
    e = _coerce_entity({
        "name": "Old",
        "first_attested_year": -2500,
        "evidence_period_start": -2500,
        "evidence_period_end": 1000,
    })
    assert e.first_attested_year == -2500
    assert e.evidence_period_end == 1000
