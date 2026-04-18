# REALMS — Research Entity Archive for Light & Metaphysical Spirit Hierarchies

Read-only public API + long-running ingestion pipeline for a provenance-tracked
knowledge base of spiritual entities documented across global indigenous
traditions.

## Status

| Phase | Status |
|-------|--------|
| 1 — Read-only API, SQLAlchemy ORM, seed data, integration tests | ✅ done |
| 2A — LLM ingestion pipeline (Wikipedia → Claude → DB) | ✅ running |
| 2B — Web frontend (D3 hierarchy, Leaflet map, entity browser) | ✅ done |
| 2C — Neo4j sync worker | ✅ running |
| 2D — End-to-end deploy verification | ✅ done |
| 2E — Rate limiting, metrics, Alembic baseline | ✅ done |

## Architecture

```
  Postgres (shared)           Neo4j (shared)
       │                           ▲
       │                           │ realms-neo4j-sync (30s loop)
       ▼                           │
   realms-api  ──────► static web/ at /app/
       ▲
       │                    LiteLLM proxy  ──► Claude Sonnet / Haiku / rombos
       │                           ▲
       │                           │ entity extraction
   realms-ingestor  ── fetch → chunk → extract → normalize → write
       ▲
       │
   ingestion_sources  (Wikipedia URLs, status: pending → completed/failed)
```

## Docs

- `docs/PROJECT_OVERVIEW.md` — Vision and scope
- `docs/ARCHITECTURE.md` — System architecture
- `docs/DATA_MODEL.md` — PostgreSQL schema
- `docs/API_SPECS.md` — API specification
- `docs/plans/2026-04-18-realms-mvp.md` — Phase 1 plan
- `docs/plans/2026-04-18-realms-phase2-ingestion.md` — Phase 2 plan

## Quick Start

```bash
cd /var/www/realms
# .env: POSTGRES_PASSWORD, LITELLM_MASTER_KEY, NEO4J_PASSWORD already set

# Build + start all three services (api + ingestor + neo4j-sync)
docker compose up -d --build

# Seed demo data + Wikipedia source queue (one-time)
docker compose exec realms-api python -m scripts.seed_realms
docker compose exec realms-api python -m scripts.seed_sources

# Browse
open http://127.0.0.1:8004/app/
```

## Services

| Container | Role | Port |
|-----------|------|------|
| `realms-api` | FastAPI + web UI | 8004 → 8001 |
| `realms-ingestor` | Wikipedia entity extraction loop | — |
| `realms-neo4j-sync` | PostgreSQL → Neo4j mirror | — |

## Endpoints

Base URL: `http://127.0.0.1:8004`

### Browse
- `/app/` — Web UI
- `/docs` — OpenAPI docs

### API
- `/api/health` — Liveness
- `/entities/` — List entities (filters: type, alignment, realm, confidence, q, culture_id, region_id)
- `/entities/{id}` — Detail with relationships + provenance
- `/entity-classes/` — Hierarchy classes
- `/hierarchy/tree` — Nested tree (for D3)
- `/relationships/` — Entity-to-entity graph
- `/cultures/` — Cultures
- `/regions/` — Geographic regions
- `/sources/` — Ingestion sources with status
- `/extractions/{id}` — Raw LLM extraction
- `/search/?q=...` — Global search
- `/search/advanced` — POST advanced query
- `/stats/` — Aggregate counts
- `/metrics/ingestion` — Live queue + throughput

### Rate limits
60 req/min per IP (configurable via `REALMS_RATE_LIMIT_PER_MINUTE`).

## Ingestion Pipeline

Flow per source:
1. Claim `pending` source (SKIP LOCKED → atomic single-worker dequeue)
2. Fetch Wikipedia plain-text via action API; cache to `data/raw/<sha256>.txt`
3. Chunk by paragraph up to ~3500 chars, tracking section headings
4. For each chunk: call LiteLLM (Claude Sonnet 4.6, with Ollama rombos / Haiku fallback) with retry/backoff
5. Normalize each extracted entity: upsert into `entities` by exact name match; merge powers/domains/provenance
6. Mark source `completed` with `processed_at` timestamp

Prompt v2 explicitly rejects biological taxa, humans, places, and organizations —
only spiritual/mythological entities qualify.

## Neo4j Graph

Every 30s, sync worker MERGEs:
- `Entity` nodes keyed by `realms_id`
- `EntityClass`, `Culture`, `Region` nodes
- `:DOCUMENTED_BY` (Entity → Culture), `:FOUND_IN` (Entity → Region), `:INSTANCE_OF` (Entity → Class)
- `:ALLIED_WITH`, `:TEACHER_OF`, etc. (Entity → Entity)

Cypher queries for exploration (use Neo4j Browser on the estimabio-neo4j container):
```cypher
MATCH (e:Entity)-[r:DOCUMENTED_BY]->(c:Culture)
WHERE e.consensus_confidence > 0.85
RETURN e, r, c LIMIT 50;
```

## Testing

```bash
docker exec -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
            -e REALMS_TEST_DB=realms_test \
            realms-api pytest tests/ -v
```

52 tests: 47 integration (real Postgres), 5 unit (chunker).

## Migrations

Alembic is scaffolded at `migrations/`. Baseline revision `20260418_0001` is a no-op
(the initial schema is created by `bootstrap_realms_db.py`). For the next schema
change:

```bash
docker exec realms-api alembic revision --autogenerate -m "add X"
docker exec realms-api alembic upgrade head
```

## Next Plans

- Phase 3: PubMed / JSTOR ingestion (better sources than Wikipedia)
- Phase 4: Cross-source entity merge via fuzzy matching + LLM judge
- Phase 5: Relationship extraction from co-occurrence analysis
- Phase 6: Admin review queue UI for low-confidence extractions
