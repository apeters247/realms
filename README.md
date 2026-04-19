# REALMS — Research Entity Archive for Light & Metaphysical Spirit Hierarchies

Read-only public API + long-running ingestion pipeline for a provenance-tracked
knowledge base of spiritual entities documented across global indigenous traditions.

## Status (as of 2026-04-19)

| Phase | Status |
|-------|--------|
| 1 — Read-only API, SQLAlchemy ORM, seed data, integration tests | ✅ done |
| 2A — LLM ingestion pipeline (Wikipedia → Claude Sonnet → DB) | ✅ running |
| 2B — Web frontend (D3 hierarchy, Leaflet map, Cytoscape graph) | ✅ done |
| 2C — Neo4j sync worker with delete-detection | ✅ running |
| 2D — End-to-end deploy verification | ✅ done |
| 2E — Rate limiting, metrics, Alembic baseline | ✅ done |
| 2F — Pair-relationship classifier (Gemini Flash via OpenRouter) | ✅ done |
| 2G — Extractor v3 role fields, stub entities, review queue, ego graph, fuzzy search, export | ✅ done |

## Live Data (current snapshot)

- 266 entities across 95+ traditions
- 439 LLM extractions, avg confidence 0.88
- 980 relationships (12 `parent_of`, 15 `sibling_of`, 7 `aspect_of`, plus co-occurrence)
- 107 cultures, 65 geographic regions promoted from extractions
- 44 source URLs seeded (Amazonian, African, Siberian, Native American, Polynesian, Entheogenic)

## Architecture

```
  Postgres ←──────── Neo4j
       │                ▲
       │                │ realms-neo4j-sync (30s loop, MERGE + delete-stale)
       ▼                │
   realms-api  ──── static web/ at /app/ (D3 + Leaflet + Cytoscape)
       ▲                    ▲
       │                    │
       │                    pair classifier (OpenRouter Gemini Flash, one-shot)
       │
       │   LiteLLM proxy → Claude Sonnet 4.6 / rombos-72b fallback
       ▲                    ▲
       │                    │ extract entities + role fields (v3 prompt)
   realms-ingestor  ── fetch → chunk → extract → normalize → role-edges → promote-dims
       ▲                                            ↑
       │                                            │
   ingestion_sources (Wikipedia URLs)        stubs created for unresolved role targets
```

## Docker services

| Container | Role | Port |
|-----------|------|------|
| `realms-api` | FastAPI + web UI | 8004 → 8001 |
| `realms-ingestor` | Wikipedia entity extraction loop | — |
| `realms-neo4j-sync` | Postgres → Neo4j mirror | — |

## Quick start

```bash
cd /var/www/realms
# .env: POSTGRES_PASSWORD, LITELLM_MASTER_KEY, NEO4J_PASSWORD, OPENROUTER_API_KEY already set

docker compose up -d --build
docker compose exec realms-api python -m scripts.seed_realms      # one-time seed
docker compose exec realms-api python -m scripts.seed_sources     # load Wikipedia URLs

open http://127.0.0.1:8004/app/
```

## API endpoints

Base: `http://127.0.0.1:8004`

**Browse**
- `/app/` — Web UI (entity browser, hierarchy, graph, map, stats, review queue)
- `/docs` — OpenAPI Swagger
- `/api/health` — Liveness probe

**Data**
- `GET /entities/` — List with filters: type, alignment, realm, confidence, culture, region, q
- `GET /entities/{id}` — Full detail with in + out relationships, plant connections, sources, quotes
- `GET /entity-classes/` — Taxonomy classes
- `GET /hierarchy/tree` — D3-format nested tree
- `GET /cultures/` / `/cultures/{id}` — 107 cultures, auto-promoted
- `GET /regions/` / `/regions/{id}` — 65 regions
- `GET /sources/` / `/sources/{id}` — 44 sources with ingestion status
- `GET /extractions/{id}` — Raw LLM extraction payload
- `GET /relationships/` — Semantic + co-occurrence edges

**Graph**
- `GET /graph/?culture=…&rel_type=semantic&max_nodes=250` — Cytoscape nodes + edges
- `GET /graph/ego/{center_id}?depth=2&semantic_only=true` — Ego subgraph BFS

**Search**
- `GET /search/?q=…` — Global keyword search
- `POST /search/advanced` — Structured query
- `GET /search/similar?q=…` — Trigram fuzzy match ("orisha" → Orishas, Oricha, …)

**Ops & metrics**
- `GET /stats/` — Aggregate counts by type, alignment, realm, culture
- `GET /metrics/ingestion` — Queue depth + throughput
- `GET /metrics/activity?minutes=60` — Recent changes: sources, new edges, semantic additions
- `GET /review/stats` — Low-confidence / single-source / isolated counts
- `GET /review/entities?confidence_max=0.7&isolated_only=true` — QA candidate queue

**Export**
- `GET /export/entities.csv` / `.json`
- `GET /export/relationships.csv`
- `GET /export/cultures.json`
- `GET /export/sources.json`

## Ingestion pipeline

```
1. Claim a pending source (SELECT FOR UPDATE SKIP LOCKED)
2. Fetch Wikipedia text via REST API; cache to data/raw/<sha>.txt
3. Chunk by paragraph up to ~3500 chars, tracking section headings
4. Per chunk → Claude Sonnet 4.6 (LiteLLM → fallback Ollama rombos-72b)
   with retry/backoff and v3 prompt that requests 14 role fields
5. Normalize each extracted entity:
   - Exact name match OR fuzzy stem match (diacritic-strip + plural-tolerant)
   - Upsert: merge powers / domains / alternate_names / sources
   - Stub creation for unresolved role-field targets
6. Turn role claims into typed edges (parent_of, consort_of, teacher_of, etc.)
   at strength=strong, confidence 0.7–0.85
7. Add weak co_occurs_with edges between every pair extracted in same chunk
8. promote_all() — backfill Culture + GeographicRegion rows from entity
   cultural_associations / geographical_associations JSONB
9. Mark source completed with processed_at timestamp
```

Orphan recovery on startup: any source stuck in `processing` > 30 min is reset to `pending`.

## Relationship classification

Two stages in the current pipeline:

1. **Extractor v3 (primary):** LLM emits explicit role fields per entity
   (`parents: [Yemoja]`, `consorts: [Oshun]`, etc.). These become strong typed
   edges directly, with the source quote stored in `EntityRelationship.description`.

2. **Pair classifier (secondary):** For existing `co_occurs_with` edges, a
   one-shot OpenRouter Gemini Flash script reads the shared chunk text and
   classifies into the same 14 relationship types. Runs at ~$0.22/M tokens,
   ~$0.15 for all ~1000 edges.

Current semantic edges: 43 (12 parent_of, 15 sibling_of, 7 aspect_of, 3 child_of,
2 manifests_as, 2 created_by, 1 serves, 1 ruled_by, 1 allied_with + 15 associated_with).
Growing as v3 re-ingestion completes richer Yoruba/Vodou/Santería sources.

## Neo4j graph

Mirrors Postgres every 30s. Cypher example:

```cypher
MATCH (a:Entity)-[r]->(b:Entity)
WHERE a.consensus_confidence > 0.85 AND type(r) <> 'CO_OCCURS_WITH'
RETURN a, r, b LIMIT 50;
```

Sync is bidirectional (updates + deletes): entities removed from Postgres are
`DETACH DELETE`d from Neo4j within 30 seconds.

## Testing

```bash
docker exec -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
            -e REALMS_TEST_DB=realms_test \
            realms-api pytest tests/ -v
```

**52 tests passing** (47 integration tests against real Postgres, 5 unit tests for the chunker).

## Migrations

```bash
docker exec realms-api alembic revision --autogenerate -m "add X"
docker exec realms-api alembic upgrade head
```

Baseline `20260418_0001` (no-op). `20260419_0002` adds pg_trgm + GIN indexes for
similarity search. `run_realms_api.sh` runs `alembic upgrade head` automatically.

## Future phases

- **Phase 3 — PubMed / archive.org ingestion** for academic corroboration of the
  Wikipedia layer. Triangulation against primary ethnography.
- **Phase 4 — Inline LLM-assisted review UI** on low-confidence entities
  (approve / reject / edit).
- **Phase 5 — Temporal and historical dimensions** — when was an entity first
  documented? How has the belief evolved?
- **Phase 6 — Cross-database linking** (Wikidata Qxxxx, VIAF, WordNet).
