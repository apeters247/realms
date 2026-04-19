"""Unit + integration tests for Phase 6 external linker."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from realms.models import Entity
from realms.services.external_linker import (
    ExternalCandidate,
    VIAFMatcher,
    WikidataMatcher,
    auto_accept_decision,
)


pytestmark = pytest.mark.integration


# ---- auto_accept_decision unit tests --------------------------------------

def test_auto_accept_empty_returns_none():
    assert auto_accept_decision([]) is None


def test_auto_accept_single_above_threshold():
    c = ExternalCandidate("wikidata", "Q1", "X", None, 0.9, {})
    assert auto_accept_decision([c]) is c


def test_auto_accept_single_below_threshold():
    c = ExternalCandidate("wikidata", "Q1", "X", None, 0.7, {})
    assert auto_accept_decision([c]) is None


def test_auto_accept_requires_gap_over_runner_up():
    # Top 0.9 but runner-up 0.85 → gap factor is 1.06, not 2x → reject.
    top = ExternalCandidate("wikidata", "Q1", "Top", None, 0.9, {})
    runner = ExternalCandidate("wikidata", "Q2", "Runner", None, 0.85, {})
    assert auto_accept_decision([top, runner]) is None


def test_auto_accept_passes_with_clear_top():
    top = ExternalCandidate("wikidata", "Q1", "Top", None, 0.95, {})
    runner = ExternalCandidate("wikidata", "Q2", "Runner", None, 0.3, {})
    assert auto_accept_decision([top, runner]) is top


# ---- WikidataMatcher mocked call ------------------------------------------

_FAKE_WIKIDATA_RESPONSE = {
    "results": {
        "bindings": [
            {
                "item": {"value": "http://www.wikidata.org/entity/Q34201"},
                "itemLabel": {"value": "Zeus"},
                "itemDescription": {"value": "Greek god of the sky and thunder"},
            },
            {
                "item": {"value": "http://www.wikidata.org/entity/Q111"},
                "itemLabel": {"value": "Zeus (asteroid)"},
                "itemDescription": {"value": "asteroid"},
            },
        ]
    }
}


def test_wikidata_matcher_parses_bindings():
    with patch("realms.services.external_linker.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _FAKE_WIKIDATA_RESPONSE
        mock_resp.raise_for_status = lambda: None
        mock_get.return_value = mock_resp

        m = WikidataMatcher(polite_delay=0)
        candidates = m.match("Zeus", description="Greek sky god")
        assert len(candidates) == 2
        zeus = next(c for c in candidates if c.external_id == "Q34201")
        assert zeus.label == "Zeus"
        assert "thunder" in (zeus.description or "")
        # Confidence should be boosted by description + word overlap ("Greek", "sky")
        assert zeus.confidence > 0.85


def test_wikidata_matcher_handles_empty_response():
    with patch("realms.services.external_linker.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": {"bindings": []}}
        mock_resp.raise_for_status = lambda: None
        mock_get.return_value = mock_resp
        m = WikidataMatcher(polite_delay=0)
        assert m.match("DoesNotExist") == []


def test_wikidata_matcher_raises_on_rate_limit():
    with patch("realms.services.external_linker.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_get.return_value = mock_resp
        m = WikidataMatcher(polite_delay=0)
        with pytest.raises(RuntimeError, match="rate-limited"):
            m.match("Zeus")


# ---- VIAFMatcher mocked ----------------------------------------------------

_FAKE_VIAF_RESPONSE = {
    "searchRetrieveResponse": {
        "records": [
            {"record": {"recordData": {
                "viafID": "12345",
                "mainHeadings": {"data": [{"text": "Zeus, -1000"}]},
            }}},
        ]
    }
}


def test_viaf_matcher_parses_json():
    with patch("realms.services.external_linker.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _FAKE_VIAF_RESPONSE
        mock_resp.raise_for_status = lambda: None
        mock_get.return_value = mock_resp
        m = VIAFMatcher(polite_delay=0)
        candidates = m.match("Zeus")
        assert len(candidates) == 1
        assert candidates[0].external_id == "12345"
        assert candidates[0].system == "viaf"


# ---- API /external-links endpoint -----------------------------------------

def test_external_links_returns_empty_for_unlinked(db_session, client):
    e = Entity(name="Unlinked")
    db_session.add(e)
    db_session.commit()
    r = client.get(f"/external-links/{e.id}")
    assert r.status_code == 200
    assert r.json()["data"]["links"] == []


def test_external_links_builds_authority_urls(db_session, client):
    e = Entity(name="Test", external_ids={"wikidata": "Q34201", "viaf": "12345"})
    db_session.add(e)
    db_session.commit()
    r = client.get(f"/external-links/{e.id}")
    data = r.json()["data"]
    by_sys = {link["system"]: link for link in data["links"]}
    assert by_sys["wikidata"]["url"] == "https://www.wikidata.org/wiki/Q34201"
    assert by_sys["viaf"]["url"] == "https://viaf.org/viaf/12345"


def test_external_links_404_on_missing_entity(client):
    r = client.get("/external-links/999999")
    assert r.status_code == 404
