# Getting Started with REALMS Development

## Prerequisites

- Docker and Docker Compose
- Git
- Access to the shared `estimabio-network` Docker network
- `OPENROUTER_API_KEY` in `.env`

## Quick Start (5 minutes)

```bash
# 1. Clone and enter directory
cd /var/www/realms

# 2. Copy environment template
# .env should contain:
#   POSTGRES_PASSWORD=...
#   NEO4J_PASSWORD=...
#   OPENROUTER_API_KEY=sk-or-...
#   LITELLM_MASTER_KEY=sk-...  (optional, for LiteLLM)

# 3. Build and start services
docker compose up -d --build

# 4. Wait for health check (40s)
docker compose ps  # should show 3 services healthy

# 5. Seed the database (one-time)
docker compose exec realms-api python -m scripts.seed_realms
docker compose exec realms-api python -m scripts.seed_sources

# 6. Verify
curl http://127.0.0.1:8005/api/health
curl http://127.0.0.1:8005/stats/
curl http://127.0.0.1:8005/entities/?per_page=3

# 7. Open the web UI
open http://127.0.0.1:8005/app/
```

## Development Workflow

### Code changes (no rebuild needed)

All Python source directories are volume-mounted:

```yaml
volumes:
  - ./realms:/app/realms       # Instant Python changes
  - ./scripts:/app/scripts     # Instant script changes
  - ./web:/app/web             # Legacy web changes
```

Edit code → save → changes reflected immediately. Restart service only if needed:

```bash
docker compose restart realms-api
```

### Frontend changes

The Astro frontend builds to `web-next/dist/` which is mounted into the container:

```bash
cd web-next
npm install     # one-time
npm run build   # rebuild → changes visible at /app/
```

For continuous development:

```bash
cd web-next
npm run dev     # Astro dev server at http://127.0.0.1:4321/app/
```

### Docker rebuild (when dependencies change)

```bash
# Full rebuild (no cache)
docker compose build --no-cache
docker compose up -d

# Quick rebuild (only changed layers)
docker compose build
docker compose up -d
```

## Project Tour

### Key Directories

| Path | What It Is |
|------|-----------|
| `realms/` | Python package: API, ingestion, models, services, sync |
| `realms/api/routes/` | 21 FastAPI route modules |
| `realms/models/orm.py` | 12 SQLAlchemy ORM models |
| `realms/services/` | Business logic layer |
| `realms/ingestion/` | Pipeline: fetcher, chunker, extractor, normalizer, relationships, integrity |
| `scripts/` | CLI utilities (31 scripts) |
| `tests/` | pytest tests (52 tests) |
| `web-next/` | Astro 5 + Svelte 5 frontend |
| `web/` | Legacy D3/Leaflet frontend |
| `migrations/` | Alembic migration versions |
| `data/` | Seed YAML files, runtime caches |
| `docs/` | Documentation |

### Common Tasks

#### Add a new entity filter

1. Add the query parameter to `realms/api/routes/entities.py`
2. Add the filter logic to `realms/services/entity_service.py`
3. Add a test in `tests/test_entities.py`

#### Add a new API route

1. Create `realms/api/routes/new_feature.py`
2. Register in `realms/api/main.py` via `app.include_router()`
3. Add corresponding service in `realms/services/`
4. Add Pydantic schemas in `realms/models/schemas.py` if needed

#### Add a new ingestion source type

1. Add fetch logic in `realms/ingestion/fetcher.py` or a new file
2. Add the source type to `_dispatch_fetch()` in `realms/ingestion/worker.py`
3. Add priority ordering in `_claim_next_source()`

## Database

```bash
# Connect directly
docker compose exec realms-api psql -d realms

# Run migrations
docker compose exec realms-api alembic upgrade head

# Create new migration
docker compose exec realms-api alembic revision --autogenerate -m "description"

# Reset and reseed
docker compose exec realms-api python -m scripts.bootstrap_realms_db  # idempotent
```

## LLM Configuration

Extraction model chain:

```bash
# Primary model
export REALMS_EXTRACTION_MODEL=anthropic/claude-sonnet-4.5

# Fallback models (comma-separated)
export REALMS_EXTRACTION_FALLBACK_MODELS="deepseek/deepseek-chat,google/gemini-2.0-flash-001"

# Pair classifier (for existing co-occurrence edges)
export REALMS_PAIR_MODEL=google/gemini-2.0-flash-001
```

## Helpful Commands

```bash
# Check service logs
docker compose logs -f realms-api
docker compose logs -f realms-ingestor
docker compose logs -f realms-neo4j-sync

# Run tests
docker compose exec realms-api pytest tests/ -v

# Run a single source through ingestion (manual)
docker compose exec realms-api python -c "
from realms.utils.database import get_db_session
from realms.ingestion.worker import _process_source
with get_db_session() as s:
    src = s.get(Source, 1)
    print(_process_source(s, src))
"

# View extraction stats
docker compose exec realms-api python -c "
from realms.utils.database import get_db_session
from models import Entity, IngestedEntity
with get_db_session() as s:
    print('Entities:', s.query(Entity).count())
    print('Extractions:', s.query(IngestedEntity).count())
"
```

## Learning Path

1. Read `docs/01-overview.md` — understand the project
2. Read `docs/02-architecture.md` — understand the system
3. Read `docs/05-ingestion-pipeline.md` — understand how data gets in
4. Read `docs/04-api.md` — understand how data gets out
5. Read `docs/06-frontend.md` — understand the UI
6. Run the tests: `docker compose exec realms-api pytest tests/ -v`
7. Trace a single entity through the ingestion pipeline
