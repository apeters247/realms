"""Integration tests for /stats endpoint."""
import pytest

pytestmark = pytest.mark.integration


def test_stats_structure(client, seeded):
    response = client.get("/stats/")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_entities"] == 2
    assert data["by_type"]["plant_spirit"] == 1
    assert data["by_type"]["animal_ally"] == 1
    assert data["by_realm"]["forest"] == 2
    assert data["by_alignment"]["beneficial"] == 1
    assert data["by_alignment"]["neutral"] == 1
    assert data["sources_processed"] == 1
    assert data["total_extractions"] == 2
    assert 0.0 < data["avg_confidence"] <= 1.0


def test_stats_by_culture(client, seeded):
    response = client.get("/stats/")
    data = response.json()["data"]
    assert data["by_culture"]["Yanomami"] == 1
    assert data["by_culture"]["Shipibo-Konibo"] == 1
