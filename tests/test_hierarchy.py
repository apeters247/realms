"""Integration tests for the /hierarchy endpoints."""
import pytest

pytestmark = pytest.mark.integration


def test_hierarchy_tree(client, seeded):
    response = client.get("/hierarchy/tree")
    assert response.status_code == 200
    tree = response.json()["data"]
    assert tree["name"] == "root"
    cat_names = {c["name"] for c in tree["children"]}
    assert {"plant_spirit", "animal_ally"}.issubset(cat_names)
    plant_cat = next(c for c in tree["children"] if c["name"] == "plant_spirit")
    class_names = {c["name"] for c in plant_cat["children"]}
    assert "Chullachaqui" in class_names


def test_hierarchy_tree_filter_realm(client, seeded):
    response = client.get("/hierarchy/tree?realm=forest")
    assert response.status_code == 200
    tree = response.json()["data"]
    assert len(tree["children"]) >= 2


def test_hierarchy_flat(client, seeded):
    response = client.get("/hierarchy/flat")
    assert response.status_code == 200
    items = response.json()["data"]
    names = {i["name"] for i in items}
    assert {"Chullachaqui", "Xapirip\u00eb"}.issubset(names)
    chul = next(i for i in items if i["name"] == "Chullachaqui")
    assert chul["path"][-1] == "Chullachaqui"


def test_hierarchy_path_for_entity(client, seeded):
    entity_id = seeded["entity_xapiri"]
    response = client.get(f"/hierarchy/path/{entity_id}")
    assert response.status_code == 200
    path = response.json()["data"]
    assert path[-1] == "Xapirip\u00eb"
    assert "animal_ally" in path


def test_hierarchy_path_404(client, seeded):
    response = client.get("/hierarchy/path/99999")
    assert response.status_code == 404
