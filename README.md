# REALMS — Research Entity Archive for Light & Metaphysical Spirit Hierarchies

Read-only public API over a provenance-tracked knowledge base of spiritual
entities documented across global indigenous traditions.

## Status

**Phase 1 (MVP) — COMPLETE.** Read-only API, 47 integration tests, seed data.

**Not yet built (future plans):**
- Ingestion pipeline (LLM extractors for academic sources)
- Neo4j graph sync
- Web frontend (D3.js hierarchy, Cytoscape.js graph, Leaflet map)
- Alembic migrations (currently uses `create_all()` bootstrap)
- Rate limiting middleware

## Docs

- `docs/PROJECT_OVERVIEW.md` — Vision and scope
- `docs/ARCHITECTURE.md` — System architecture
- `docs/DATA_MODEL.md` — PostgreSQL schema
- `docs/API_SPECS.md` — API specification
- `docs/plans/` — Implementation plans

## Quick Start

REALMS shares PostgreSQL with the EstimaBio stack via the `herbalist_estimabio-network` Docker network.

```bash
# .env needs POSTGRES_PASSWORD set (same value as estimabio's postgres container)
cd /var/www/realms
echo "POSTGRES_PASSWORD=<your-postgres-password>" > .env
echo "POSTGRES_DB=realms" >> .env

# Build + start
docker compose up -d --build

# Seed sample data (one-time)
docker compose exec realms-api python -m scripts.seed_realms

# Browse
curl http://127.0.0.1:8001/api/health
open http://127.0.0.1:8001/docs
```

## Endpoints

Base URL: `http://127.0.0.1:8001`

| Path | Description |
|------|-------------|
| `/api/health` | Liveness probe |
| `/entities/` | List entities |
| `/entities/{id}` | Entity detail |
| `/entities/{id}/relationships` | Entity relationships |
| `/entities/{id}/plant-connections` | Plant-spirit connections |
| `/entity-classes/` | List entity classes |
| `/entity-classes/{id}` | Class detail |
| `/entity-classes/{id}/entities` | Entities in class |
| `/hierarchy/tree` | Full nested hierarchy (D3.js format) |
| `/hierarchy/flat` | Flattened hierarchy |
| `/hierarchy/path/{entity_id}` | Breadcrumb path for an entity |
| `/relationships/` | Entity-to-entity relationships |
| `/relationships/{id}` | Relationship detail |
| `/cultures/` | Cultures |
| `/cultures/{id}` | Culture detail |
| `/regions/` | Geographic regions |
| `/regions/{id}` | Region detail |
| `/sources/` | Source documents |
| `/sources/{id}` | Source detail with extractions |
| `/extractions/{id}` | Raw LLM extraction |
| `/search/?q=...` | Global search across resources |
| `/search/advanced` | POST advanced entity search |
| `/stats/` | Aggregate counts |

Full spec: `docs/API_SPECS.md`.

## Testing

```bash
docker exec -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
            -e REALMS_TEST_DB=realms_test \
            realms-api pytest tests/ -v
```

Tests hit a real PostgreSQL test database (`realms_test` by default). No mocks —
matches the project convention of validating against real infra.

## Architecture

```
realms/
├── api/              FastAPI app + 10 route modules
├── models/           SQLAlchemy ORM (orm.py) + Pydantic schemas
├── services/         Per-resource query logic
└── utils/            DB engine / session factory

scripts/              bootstrap_realms_db.py, seed_realms.py
tests/                47 integration tests (real Postgres)
docs/plans/           Implementation plans
```
