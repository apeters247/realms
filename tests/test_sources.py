"""Integration tests for /sources and /extractions endpoints."""
import pytest

pytestmark = pytest.mark.integration


def test_list_sources(client, seeded):
    response = client.get("/sources/")
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 1
    assert body["data"][0]["source_name"].startswith("The Falling Sky")


def test_list_sources_filter_type(client, seeded):
    response = client.get("/sources/?source_type=book")
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


def test_list_sources_filter_peer_reviewed(client, seeded):
    response = client.get("/sources/?peer_reviewed=true")
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


def test_get_source_detail(client, seeded):
    sid = seeded["source_falling_sky"]
    response = client.get(f"/sources/{sid}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["source_name"].startswith("The Falling Sky")
    assert len(data["ingested_entities"]) == 2
    assert data["extraction_statistics"]["count"] == 2


def test_get_source_404(client, seeded):
    response = client.get("/sources/99999")
    assert response.status_code == 404


def test_get_extraction_detail(client, seeded):
    sid = seeded["source_falling_sky"]
    source = client.get(f"/sources/{sid}").json()["data"]
    ext_id = source["ingested_entities"][0]["id"]
    response = client.get(f"/extractions/{ext_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["entity_name_normalized"] in {"Chullachaqui", "Xapirip\u00eb"}


def test_get_extraction_404(client, seeded):
    response = client.get("/extractions/99999")
    assert response.status_code == 404
