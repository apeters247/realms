"""Integration tests for /search endpoints."""
import pytest

pytestmark = pytest.mark.integration


def test_global_search(client, seeded):
    response = client.get("/search/?q=Xapirip")
    assert response.status_code == 200
    data = response.json()["data"]
    assert any(e["name"] == "Xapirip\u00eb" for e in data["entities"])


def test_global_search_empty_query(client, seeded):
    response = client.get("/search/?q=")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["entities"] == []
    assert data["entity_classes"] == []
    assert data["cultures"] == []
    assert data["sources"] == []


def test_global_search_across_resources(client, seeded):
    response = client.get("/search/?q=Yanomami")
    assert response.status_code == 200
    data = response.json()["data"]
    assert any(c["name"] == "Yanomami" for c in data["cultures"])


def test_advanced_search_entity_filter(client, seeded):
    response = client.post("/search/advanced", json={
        "filters": {"entity_type": "plant_spirit", "realm": "forest"},
        "sort": "-consensus_confidence",
        "page": 1,
        "per_page": 20,
    })
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == "Chullachaqui"
