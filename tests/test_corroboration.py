"""Integration tests for Phase 3 corroboration endpoints."""
from __future__ import annotations

import pytest

from realms.models import Entity, IngestionSource


pytestmark = pytest.mark.integration


def _make_source(db_session, *, stype: str, name: str, url: str | None = None):
    src = IngestionSource(source_type=stype, source_name=name, url=url, ingestion_status="completed")
    db_session.add(src)
    db_session.commit()
    db_session.refresh(src)
    return src


def test_tier_0_when_no_sources(db_session, client):
    e = Entity(name="Orphan", provenance_sources=[])
    db_session.add(e)
    db_session.commit()
    resp = client.get(f"/corroboration/{e.id}")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["tier"] == "tier_0"
    assert data["n_sources"] == 0


def test_tier_1_single_source_type(db_session, client):
    s = _make_source(db_session, stype="wikipedia", name="WP article")
    e = Entity(name="Single", provenance_sources=[s.id])
    db_session.add(e)
    db_session.commit()
    resp = client.get(f"/corroboration/{e.id}")
    data = resp.json()["data"]
    assert data["tier"] == "tier_1"
    assert data["distinct_source_types"] == ["wikipedia"]


def test_tier_3_three_source_types(db_session, client):
    wiki = _make_source(db_session, stype="wikipedia", name="WP")
    pmid = _make_source(db_session, stype="pubmed", name="Paper")
    arc = _make_source(db_session, stype="archive_org", name="Book")
    e = Entity(name="Triangulated", provenance_sources=[wiki.id, pmid.id, arc.id])
    db_session.add(e)
    db_session.commit()
    resp = client.get(f"/corroboration/{e.id}")
    data = resp.json()["data"]
    assert data["tier"] == "tier_3"
    assert set(data["distinct_source_types"]) == {"wikipedia", "pubmed", "archive_org"}
    assert data["n_sources"] == 3


def test_corroboration_stats_aggregates_tiers(db_session, client):
    wiki = _make_source(db_session, stype="wikipedia", name="WP")
    pmid = _make_source(db_session, stype="pubmed", name="Paper")
    e1 = Entity(name="OneSource", provenance_sources=[wiki.id])
    e2 = Entity(name="TwoSources", provenance_sources=[wiki.id, pmid.id])
    db_session.add_all([e1, e2])
    db_session.commit()
    resp = client.get("/corroboration/stats/summary")
    data = resp.json()["data"]
    assert data["total_entities"] == 2
    assert data["tier_counts"].get("tier_1") == 1
    assert data["tier_counts"].get("tier_2") == 1


def test_404_on_missing_entity(client):
    resp = client.get("/corroboration/999999")
    assert resp.status_code == 404
