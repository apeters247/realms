# REALMS Architecture

## System Diagram (Current)

```
                          ┌─────────────────────┐
                          │   Cloudflare CDN     │
                          │  /app/* /og/* cached │
                          └─────────┬───────────┘
                                    │ origin https://realmsoutthere.com
                                    ▼
                          ┌─────────────────────┐
                          │   nginx (host VM)   │
                          │  realmsoutthere.com │
                          │     reverse proxy   │
                          └─────────┬───────────┘
                                    │ 127.0.0.1:8005
                                    ▼
                    ┌─────────────────────────────────┐
                    │        realms-api (FastAPI)      │
                    │  ┌─ uvicorn ──────────────────┐  │
                    │  │ 21 route modules           │  │
                    │  │ static: /app (Astro build) │  │
                    │  │ static: /app-legacy (D3)   │  │
                    │  │ SlowAPI rate limiting      │  │
                    │  │ CORS, health check         │  │
                    │  └────────────────────────────┘  │
                    └──┬──────────┬──────────────┬─────┘
                       │ PG       │              │
                       ▼          ▼              ▼
              ┌────────────┐ ┌────────┐  ┌──────────────┐
              │ PostgreSQL │ │ Neo4j  │  │  Web (Astro) │
              │  realms DB │ │ graph  │  │  static files│
              │  12 tables │ │ 30s    │  │              │
              │  Alembic   │ │ sync   │  │              │
              └────────────┘ └────────┘  └──────────────┘

                    ┌─────────────────────────────────┐
                    │     realms-ingestor (worker)     │
                    │  ┌────────────────────────────┐  │
                    │  │ poll DB → fetch → chunk    │  │
                    │  │ → LLM extract → normalize  │  │
                    │  │ → role edges → promote dims│  │
                    │  │ → integrity gate            │  │
                    │  └────────────────────────────┘  │
                    │  LiteLLM / OpenRouter API client │
                    └─────────────────────────────────┘

                    ┌─────────────────────────────────┐
                    │   realms-neo4j-sync (worker)     │
                    │  ┌────────────────────────────┐  │
                    │  │ every 30s: MERGE entities  │  │
                    │  │ + classes + cultures +     │  │
                    │  │ regions + relationships    │  │
                    │  │ + DETACH DELETE stale      │  │
                    │  └────────────────────────────┘  │
                    └─────────────────────────────────┘
```

## Architectural Principles

1. **Provenance-First** — Every data element preserves complete source lineage with confidence scoring
2. **Read-Only Public API** — All write paths are internal (ingestion pipeline, token-gated review)
3. **Separation of Concerns** — Distinct layers for ingestion, storage, API, presentation
4. **Fault Tolerance** — Orphan recovery, retry/backoff, fallback model chains
5. **Infrastructure Sharing** — Reuses existing PostgreSQL and Neo4j instances from Herbalist/EstimaBio

## Service Breakdown

### realms-api

| Aspect | Detail |
|--------|--------|
| Entry | `run_realms_api.sh` → `uvicorn realms.api.main:app` |
| Port | 8001 (internal), mapped to 8005 on host |
| Routes | 21 route modules in `realms/api/routes/` |
| Middleware | CORS (configurable origins), SlowAPI rate limiting (60/min default) |
| Static | Mounts `/app` (Astro build) and `/app-legacy` (D3/Leaflet) |
| Health | `GET /api/health` used by Docker healthcheck |

### realms-ingestor

| Aspect | Detail |
|--------|--------|
| Entry | `scripts/run_ingestor.py` |
| Loop | Poll DB for pending sources every 20s, idle sleep 60s |
| Max chunks | 8 per source, 1 concurrent (to avoid OpenRouter rate limits) |
| Models | Primary: `openai/gpt-oss-120b:free`, fallback chain of 5 free models |
| Integrity | 2-stage gate: quote check + semantic verification via Gemini Flash |
| Priority | encyclopedia > wikipedia > archive_org > primary_source > book > pubmed > journal > other |

### realms-neo4j-sync

| Aspect | Detail |
|--------|--------|
| Entry | `scripts/run_neo4j_sync.py` |
| Interval | 30s |
| Strategy | Full resync each pass (incremental via `updated_at` checkpoint planned) |
| Delete | `DETACH DELETE` for stale entities/classes not in Postgres |

## Data Flow

### Ingestion Pipeline
```
User seeds URLs → DB (ingestion_sources, status=pending)
  ↓
Worker claims source (SELECT FOR UPDATE SKIP LOCKED)
  ↓
Fetch: Wikipedia REST API / Wikisource MediaWiki / PubMed / archive.org / generic HTML
  ↓
Cache: data/raw/<sha256>.txt (on-disk, SHA-keyed)
  ↓
Chunk: paragraph-boundary, ~3500 chars, section headings tracked
  ↓
LLM Extract: per chunk → OpenRouter → Claude Sonnet / free fallback → JSON
  ↓
Integrity Gate: quote presence check → semantic claim verify → accept/flag/reject
  ↓
Normalize: exact name match → trigram fuzzy → upsert/merge entity
  ↓
Role Edges: role claims → 14 typed relationship types (with stub creation for unknowns)
  ↓
Co-occurrence: every pair in chunk → weak co_occurs_with edge
  ↓
Promote Dimensions: backfill Culture + GeographicRegion rows
  ↓
Mark source completed
```

### Query Flow
```
HTTP Request → FastAPI route → Service class → SQLAlchemy ORM query → JSON response
```

## Technology Choices

| Choice | Rationale |
|--------|-----------|
| **FastAPI** | Async, auto OpenAPI docs, Pydantic validation, matches existing infra |
| **PostgreSQL** | ACID for provenance, JSONB for flexible metadata, existing instance |
| **Neo4j** | Natural graph traversals, Cytoscape.js visualization support |
| **Astro + Svelte** | Static site generation for performance, Svelte islands for interactivity |
| **OpenRouter** | Single API for multiple LLM providers, free tier for cost-effective bulk extraction |
| **Separate Services** | Independent scaling, failure isolation, clear read/write boundaries |

## Failure Modes

| Scenario | Mitigation |
|----------|-----------|
| OpenRouter rate limit | Exponential backoff, fallback model chain, daily quota detection |
| Source fetch failure | Retry next poll, error logged to `error_log` column |
| Worker crash | Orphan recovery: sources stuck "processing" >30min reset to "pending" |
| Neo4j unavailable | API continues serving from PostgreSQL (relationship queries degrade gracefully) |
| LLM returns bad JSON | Extraction skipped, raw response stored for inspection |
