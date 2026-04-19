"""Integration tests for Phase 4 review write endpoints."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from realms.models import Entity, EntityRelationship, IngestionSource, ReviewAction


pytestmark = pytest.mark.integration

TOKEN = "test-review-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture(autouse=True)
def _set_token(monkeypatch):
    monkeypatch.setenv("REALMS_REVIEW_TOKEN", TOKEN)
    monkeypatch.setenv("REALMS_REVIEW_REVIEWER", "test-user")


@pytest.fixture
def fresh_client(test_database_url) -> TestClient:
    """Fresh TestClient that picks up the patched env var."""
    from realms.api.main import app
    with TestClient(app) as c:
        yield c


def _make_entity(db_session, name="Subject", confidence=0.5) -> Entity:
    e = Entity(name=name, consensus_confidence=confidence, review_status="unreviewed")
    db_session.add(e)
    db_session.commit()
    db_session.refresh(e)
    return e


# ---- Auth --------------------------------------------------------------------

def test_approve_without_token_returns_503_when_no_server_token(db_session, client, monkeypatch):
    monkeypatch.delenv("REALMS_REVIEW_TOKEN", raising=False)
    e = _make_entity(db_session)
    r = client.post(f"/review/entities/{e.id}/approve")
    assert r.status_code == 503


def test_approve_without_header_returns_401(db_session, fresh_client):
    e = _make_entity(db_session)
    r = fresh_client.post(f"/review/entities/{e.id}/approve")
    assert r.status_code == 401


def test_approve_with_bad_token_returns_403(db_session, fresh_client):
    e = _make_entity(db_session)
    r = fresh_client.post(
        f"/review/entities/{e.id}/approve",
        headers={"Authorization": "Bearer nope"},
    )
    assert r.status_code == 403


# ---- Approve / Reject -------------------------------------------------------

def test_approve_sets_status_and_logs_action(db_session, fresh_client):
    e = _make_entity(db_session, confidence=0.4)
    r = fresh_client.post(
        f"/review/entities/{e.id}/approve", json={"note": "looks good"},
        headers=AUTH,
    )
    assert r.status_code == 200, r.text
    db_session.expire_all()
    e2 = db_session.get(Entity, e.id)
    assert e2.review_status == "approved"
    assert e2.consensus_confidence >= 0.95
    actions = db_session.query(ReviewAction).filter_by(entity_id=e.id).all()
    assert len(actions) == 1
    assert actions[0].action == "approve"
    assert actions[0].reviewer == "test-user"


def test_reject_sets_confidence_zero(db_session, fresh_client):
    e = _make_entity(db_session, confidence=0.7)
    r = fresh_client.post(
        f"/review/entities/{e.id}/reject", json={"note": "duplicate"},
        headers=AUTH,
    )
    assert r.status_code == 200
    db_session.expire_all()
    e2 = db_session.get(Entity, e.id)
    assert e2.review_status == "rejected"
    assert e2.consensus_confidence == 0.0


# ---- Edit -------------------------------------------------------------------

def test_edit_whitelisted_field(db_session, fresh_client):
    e = _make_entity(db_session)
    r = fresh_client.patch(
        f"/review/entities/{e.id}",
        json={"field": "alignment", "value": "benevolent", "note": "clear from sources"},
        headers=AUTH,
    )
    assert r.status_code == 200, r.text
    db_session.expire_all()
    e2 = db_session.get(Entity, e.id)
    assert e2.alignment == "benevolent"
    action = db_session.query(ReviewAction).filter_by(entity_id=e.id, action="edit").one()
    assert action.field == "alignment"


def test_edit_non_whitelisted_field_rejected(db_session, fresh_client):
    e = _make_entity(db_session)
    r = fresh_client.patch(
        f"/review/entities/{e.id}",
        json={"field": "consensus_confidence", "value": 1.0},
        headers=AUTH,
    )
    assert r.status_code == 400


# ---- Merge ------------------------------------------------------------------

def test_merge_reparents_relationships_and_sources(db_session, fresh_client):
    src_ingest = IngestionSource(source_type="wikipedia", source_name="A")
    tgt_ingest = IngestionSource(source_type="pubmed", source_name="B")
    db_session.add_all([src_ingest, tgt_ingest])
    db_session.commit()
    src = Entity(name="Dup", provenance_sources=[src_ingest.id])
    tgt = Entity(name="Canonical", provenance_sources=[tgt_ingest.id])
    other = Entity(name="Other")
    db_session.add_all([src, tgt, other])
    db_session.commit()
    edge = EntityRelationship(
        source_entity_id=src.id, target_entity_id=other.id,
        relationship_type="parent_of",
    )
    db_session.add(edge)
    db_session.commit()

    r = fresh_client.post(
        f"/review/entities/{src.id}/merge_into/{tgt.id}",
        json={"note": "same deity"},
        headers=AUTH,
    )
    assert r.status_code == 200, r.text
    db_session.expire_all()

    src2 = db_session.get(Entity, src.id)
    tgt2 = db_session.get(Entity, tgt.id)
    edge2 = db_session.get(EntityRelationship, edge.id)

    assert src2.review_status == "rejected"
    assert edge2.source_entity_id == tgt.id
    assert set(tgt2.provenance_sources or []) == {src_ingest.id, tgt_ingest.id}


def test_cannot_merge_into_self(db_session, fresh_client):
    e = _make_entity(db_session)
    r = fresh_client.post(f"/review/entities/{e.id}/merge_into/{e.id}", headers=AUTH)
    assert r.status_code == 400


# ---- External links (Phase 6) ----------------------------------------------

def test_link_external_id_wikidata(db_session, fresh_client):
    e = _make_entity(db_session)
    r = fresh_client.post(
        f"/review/entities/{e.id}/link",
        json={"system": "wikidata", "external_id": "Q12345"},
        headers=AUTH,
    )
    assert r.status_code == 200, r.text
    db_session.expire_all()
    e2 = db_session.get(Entity, e.id)
    assert e2.external_ids.get("wikidata") == "Q12345"


def test_unlink_removes_key(db_session, fresh_client):
    e = _make_entity(db_session)
    e.external_ids = {"wikidata": "Q1", "viaf": "555"}
    db_session.commit()
    r = fresh_client.post(
        f"/review/entities/{e.id}/unlink",
        json={"system": "wikidata"},
        headers=AUTH,
    )
    assert r.status_code == 200
    db_session.expire_all()
    e2 = db_session.get(Entity, e.id)
    assert "wikidata" not in e2.external_ids
    assert e2.external_ids.get("viaf") == "555"


def test_link_rejects_unknown_system(db_session, fresh_client):
    e = _make_entity(db_session)
    r = fresh_client.post(
        f"/review/entities/{e.id}/link",
        json={"system": "bogus", "external_id": "X"},
        headers=AUTH,
    )
    assert r.status_code == 400


# ---- Audit list -------------------------------------------------------------

def test_actions_endpoint_lists_audit_rows(db_session, fresh_client):
    e = _make_entity(db_session)
    fresh_client.post(f"/review/entities/{e.id}/approve", json={"note": "x"}, headers=AUTH)
    fresh_client.patch(
        f"/review/entities/{e.id}",
        json={"field": "realm", "value": "heaven"},
        headers=AUTH,
    )
    r = fresh_client.get(f"/review/actions?entity_id={e.id}")
    assert r.status_code == 200
    payload = r.json()["data"]
    actions = [row["action"] for row in payload]
    assert "approve" in actions and "edit" in actions
