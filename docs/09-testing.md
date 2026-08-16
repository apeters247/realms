# REALMS Testing Guide

## Test Structure

```
tests/
├── conftest.py              # Fixtures: test DB, sessions, seed data, HTTP client
├── __init__.py
│
├── test_entities.py         # Entity CRUD + filtering
├── test_classes.py          # Entity class endpoints
├── test_search.py           # Keyword + trigram + advanced search
├── test_relationships.py    # Typed + co-occurrence relationships
├── test_cultures.py         # Culture endpoints
├── test_regions.py          # Region endpoints
├── test_sources.py          # Source + extraction endpoints
├── test_stats.py            # Statistics aggregation
├── test_hierarchy.py        # Tree + flat hierarchy
├── test_timeline.py         # Temporal filters
├── test_corroboration.py    # Corroboration tiers
├── test_review_actions.py   # Review write endpoints
├── test_backfill_integrity.py
│
├── test_chunker.py          # Unit test: chunking logic
├── test_normalizer.py       # Unit test: name normalization + dedup
├── test_fetchers.py         # Unit test: Wikipedia URL parsing
├── test_purge_fictional.py  # Unit test: fictional entity detection
├── test_external_linker.py  # Unit test: Wikidata/VIAF matching
```

## Test Markers

Defined in `pyproject.toml`:

| Marker | Meaning | Tests |
|--------|---------|-------|
| `integration` | Hits real PostgreSQL | 47 tests |
| `unit` | Fast, no external dependencies | 5 tests |

## Running Tests

### Prerequisites

PostgreSQL must be running. The test infrastructure creates a separate `realms_test` database automatically (session-scoped, dropped after).

### Run all tests

```bash
docker compose exec realms-api pytest tests/ -v
```

### Run by marker

```bash
docker compose exec realms-api pytest tests/ -m unit -v
docker compose exec realms-api pytest tests/ -m integration -v
docker compose exec realms-api pytest tests/ -m "not integration"  # unit only
```

### Run specific test

```bash
docker compose exec realms-api pytest tests/test_entities.py -v
docker compose exec realms-api pytest tests/test_search.py::test_global_search -v
```

### Run with coverage

```bash
docker compose exec realms-api pytest tests/ --cov=realms --cov-report=term-missing
```

### From outside Docker (if you have direct DB access)

```bash
docker exec -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
            -e REALMS_TEST_DB=realms_test \
            realms-api pytest tests/ -v
```

## Test Infrastructure

### conftest.py

Key fixtures:

| Fixture | Scope | Purpose |
|---------|-------|---------|
| `test_database_url` | session | Creates `realms_test` DB, applies schema, tears down at end |
| `db_session` | function | Clean session per test, truncates all tables after |
| `seeded` | function | Runs `scripts.seed_realms` and returns ID map |
| `client` | function | FastAPI `TestClient` pointed at test DB |

### Database Isolation

Tables are truncated after each test via `TRUNCATE ... RESTART IDENTITY CASCADE`. This ensures:
- No test pollution
- Auto-increment IDs reset
- Foreign key chains cleaned properly

### Seed Fixture

The `seeded` fixture calls `scripts.seed_realms.seed(session)` which populates:
- Entity categories (angelic, plant_spirit, etc.)
- Entity classes (Orisha, Kachina, etc.)
- Sample entities with relationships

Returns a dict mapping names to IDs for use in tests.

## Test Patterns

### Entity listing test (example)

```python
def test_list_entities_by_type(seeded, client):
    resp = client.get("/entities/?entity_type=deity")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) > 0
    for e in data:
        assert e["entity_type"] == "deity"
```

### Search test (example)

```python
def test_trigram_fuzzy_search(seeded, client):
    resp = client.get("/search/similar?q=xapiri&threshold=0.2")
    assert resp.status_code == 200
    names = [e["name"] for e in resp.json()["data"]]
    assert any("Xapiripë" in n for n in names)
```

## Writing New Tests

1. Add your test to the appropriate file in `tests/`
2. Use `seeded` fixture if you need seed data
3. Use `db_session` fixture if you need direct DB access
4. Use `client` fixture for HTTP-level tests
5. Add `@pytest.mark.unit` or `@pytest.mark.integration` marker

```python
@pytest.mark.integration
def test_my_feature(seeded, db_session, client):
    # Arrange
    entity_id = seeded["entity_name"]
    # Act
    resp = client.get(f"/entities/{entity_id}")
    # Assert
    assert resp.status_code == 200
```

## CI Notes

Tests are designed to run against a real PostgreSQL instance. There is no SQLite fallback. The test DB `realms_test` is created and destroyed per session.

## Current Status

**52 tests passing** (47 integration, 5 unit).
