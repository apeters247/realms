"""Integration tests for the /relationships endpoint."""
import pytest

pytestmark = pytest.mark.integration


def test_list_relationships(client, seeded):
    response = client.get("/relationships/")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["relationship_type"] == "allied_with"


def test_list_relationships_filter_by_type(client, seeded):
    response = client.get("/relationships/?relationship_type=allied_with")
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


def test_list_relationships_filter_missing(client, seeded):
    response = client.get("/relationships/?relationship_type=enemy_of")
    assert response.status_code == 200
    assert response.json()["data"] == []


def test_get_relationship_detail(client, seeded):
    list_resp = client.get("/relationships/").json()["data"]
    rel_id = list_resp[0]["id"]
    response = client.get(f"/relationships/{rel_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["relationship_type"] == "allied_with"
    assert "source_entity" in data
    assert "target_entity" in data
    assert data["source_entity"]["name"] == "Xapirip\u00eb"
    assert data["target_entity"]["name"] == "Chullachaqui"


def test_get_relationship_404(client, seeded):
    response = client.get("/relationships/99999")
    assert response.status_code == 404
