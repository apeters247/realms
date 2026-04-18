"""Integration tests for /regions endpoints."""
import pytest

pytestmark = pytest.mark.integration


def test_list_regions(client, seeded):
    response = client.get("/regions/")
    assert response.status_code == 200
    names = {r["name"] for r in response.json()["data"]}
    assert "Amazon Basin" in names


def test_list_regions_filter_type(client, seeded):
    response = client.get("/regions/?region_type=tropical")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == "Amazon Basin"


def test_get_region_detail(client, seeded):
    rid = seeded["region_amazon"]
    response = client.get(f"/regions/{rid}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "Amazon Basin"
    entity_names = {e["name"] for e in data["entities"]}
    assert {"Chullachaqui", "Xapirip\u00eb"}.issubset(entity_names)


def test_get_region_404(client, seeded):
    response = client.get("/regions/99999")
    assert response.status_code == 404
