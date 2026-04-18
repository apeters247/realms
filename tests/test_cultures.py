"""Integration tests for /cultures endpoints."""
import pytest

pytestmark = pytest.mark.integration


def test_list_cultures(client, seeded):
    response = client.get("/cultures/")
    assert response.status_code == 200
    body = response.json()
    names = {c["name"] for c in body["data"]}
    assert {"Yanomami", "Shipibo-Konibo"}.issubset(names)


def test_list_cultures_filter_region(client, seeded):
    response = client.get("/cultures/?region=Upper Amazon")
    assert response.status_code == 200
    assert len(response.json()["data"]) == 2


def test_list_cultures_filter_tradition(client, seeded):
    response = client.get("/cultures/?tradition_type=vegetalismo")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == "Shipibo-Konibo"


def test_get_culture_detail(client, seeded):
    cid = seeded["culture_yanomami"]
    response = client.get(f"/cultures/{cid}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "Yanomami"
    entity_names = {e["name"] for e in data["entities"]}
    assert "Xapirip\u00eb" in entity_names


def test_get_culture_404(client, seeded):
    response = client.get("/cultures/99999")
    assert response.status_code == 404
