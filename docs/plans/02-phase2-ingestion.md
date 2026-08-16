# REALMS Phase 2: Ingestion + Frontend + Neo4j Sync

> Continuation of Phase 1 (MVP API). Adds long-running ingestion worker, read-only web frontend, and Neo4j mirror.

**Goal:** Populate REALMS with real entity data continuously, make it browsable, and mirror relationships into Neo4j for graph queries.

**Architecture:**
- `realms-ingestor` container: polls `ingestion_sources` table, fetches Wikipedia articles, chunks text, calls LiteLLM for entity extraction, writes `ingested_entities` + normalizes into `entities`.
- `realms-neo4j-sync` container: polls for new entities/relationships in Postgres, mirrors into Neo4j.
- `web/` static frontend served by FastAPI via `StaticFiles`: hierarchy tree (D3), map (Leaflet), entity table.

**Tech Stack additions:** BeautifulSoup (already in requirements), `openai` SDK pointed at LiteLLM, `neo4j` driver, vanilla JS + D3 v7 + Leaflet 1.9.

---

## Task Breakdown

### Phase 2A: Ingestion pipeline

**Task A1: Seed initial sources**
- Create `data/seed_sources.yaml` with ~20 Wikipedia URLs covering Amazonian, African, Siberian, Polynesian traditions.
- Script `scripts/seed_sources.py` inserts them as `ingestion_sources` rows with `status=pending`.

**Task A2: Source fetcher**
- `realms/ingestion/fetcher.py`: Wikipedia fetch via REST API, SHA256 hash, store to `data/raw/`.

**Task A3: Text chunker**
- `realms/ingestion/chunker.py`: Paragraph-based chunking with 500-token max.

**Task A4: LLM entity extractor**
- `realms/ingestion/extractor.py`: Uses `openai` SDK → LiteLLM, strict JSON schema output.
- Prompt template at `realms/ingestion/prompts/extract_entities.md`.
- Returns list of entity dicts (name, type, alignment, realm, powers, domains, cultural_associations, description, quote_context).

**Task A5: Normalizer**
- `realms/ingestion/normalizer.py`: Dedup by fuzzy match on name + entity_type; upsert into `entities`.
- Merge provenance: appends source_id to `provenance_sources`, appends extraction_id to `extraction_instances`.
- Recomputes `consensus_confidence` as average of extraction confidences.

**Task A6: Worker loop**
- `realms/ingestion/worker.py`: infinite loop — poll pending sources, process one, sleep.
- Signal handling for graceful shutdown.

**Task A7: Docker service**
- New `realms-ingestor` service in docker-compose.yml.
- Own Dockerfile target (reuses base image).

### Phase 2B: Frontend

**Task B1: Static assets**
- `web/index.html`: app shell with nav tabs (Entities, Hierarchy, Map, Search, Stats).
- `web/app.css`: dark, readable design.
- `web/app.js`: fetch API, render.

**Task B2: D3 hierarchy view**
- Collapsible tree from `/hierarchy/tree`.

**Task B3: Leaflet map**
- Plot regions from `/regions/` with entity count tooltips.

**Task B4: Entity browser**
- Table view of `/entities/` with filters and pagination.
- Detail pane shows relationships, plant connections, sources.

**Task B5: Wire into FastAPI**
- Mount `web/` as static files at `/app/` route.

### Phase 2C: Neo4j sync

**Task C1: Neo4j client**
- `realms/sync/neo4j_sync.py`: Cypher MERGE on entities + relationships.

**Task C2: Sync worker**
- `realms/sync/worker.py`: polls changed entities, syncs to Neo4j.

**Task C3: Docker service**
- `realms-neo4j-sync` service in docker-compose.yml.

### Phase 2D: Operations

**Task D1: Health + metrics endpoints**
- `/api/metrics` returns queue depth, throughput, extraction success rate.

**Task D2: Verify end-to-end**
- Start full stack, watch ingestor consume sources, verify entities appear in API and UI.
