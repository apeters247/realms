"""Integration tests for the /entities endpoint."""
import pytest


pytestmark = pytest.mark.integration


def test_list_entities_returns_seeded_data(client, seeded):
    response = client.get("/entities/")
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "pagination" in body
    assert body["pagination"]["total"] == 2
    names = {e["name"] for e in body["data"]}
    assert names == {"Chullachaqui", "Xapirip\u00eb"}


def test_list_entities_filter_by_entity_type(client, seeded):
    response = client.get("/entities/?entity_type=plant_spirit")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == "Chullachaqui"
    assert data[0]["entity_type"] == "plant_spirit"


def test_list_entities_filter_by_alignment(client, seeded):
    response = client.get("/entities/?alignment=beneficial")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == "Xapirip\u00eb"


def test_list_entities_confidence_filter(client, seeded):
    response = client.get("/entities/?confidence_min=0.9")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == "Xapirip\u00eb"


def test_list_entities_search_q(client, seeded):
    response = client.get("/entities/?q=Xapirip")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == "Xapirip\u00eb"


def test_list_entities_pagination(client, seeded):
    response = client.get("/entities/?per_page=1&page=1")
    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 1
    assert body["pagination"]["total"] == 2
    assert body["pagination"]["total_pages"] == 2


def test_get_entity_detail(client, seeded):
    entity_id = seeded["entity_xapiri"]
    response = client.get(f"/entities/{entity_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "Xapirip\u00eb"
    assert data["description"].startswith("Tiny humanoid")
    assert "relationships" in data
    assert "plant_connections" in data
    assert "sources" in data
    assert len(data["relationships"]["allied_with"]) == 1
    assert len(data["plant_connections"]) == 1
    assert len(data["sources"]) == 1


def test_get_entity_404(client, seeded):
    response = client.get("/entities/99999")
    assert response.status_code == 404


def test_get_entity_relationships(client, seeded):
    entity_id = seeded["entity_xapiri"]
    response = client.get(f"/entities/{entity_id}/relationships")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["relationship_type"] == "allied_with"


def test_get_entity_plant_connections(client, seeded):
    entity_id = seeded["entity_xapiri"]
    response = client.get(f"/entities/{entity_id}/plant-connections")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["relationship_type"] == "teacher_of"
