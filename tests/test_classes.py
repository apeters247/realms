"""Integration tests for the /entity-classes endpoint."""
import pytest

pytestmark = pytest.mark.integration


def test_list_classes(client, seeded):
    response = client.get("/entity-classes/")
    assert response.status_code == 200
    body = response.json()
    names = {c["name"] for c in body["data"]}
    assert {"Chullachaqui", "Xapirip\u00eb"}.issubset(names)


def test_list_classes_filter_category(client, seeded):
    cat_id = seeded["category_plant"]
    response = client.get(f"/entity-classes/?category_id={cat_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == "Chullachaqui"


def test_get_class_detail(client, seeded):
    class_id = seeded["class_xapiri"]
    response = client.get(f"/entity-classes/{class_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "Xapirip\u00eb"
    assert "entities" in data
    assert len(data["entities"]) == 1
    assert data["entities"][0]["name"] == "Xapirip\u00eb"


def test_get_class_404(client, seeded):
    response = client.get("/entity-classes/99999")
    assert response.status_code == 404


def test_get_entities_in_class(client, seeded):
    class_id = seeded["class_chullachaqui"]
    response = client.get(f"/entity-classes/{class_id}/entities")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == "Chullachaqui"
