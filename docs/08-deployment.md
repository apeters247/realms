# REALMS Deployment Guide

## Architecture (Production)

```
User → Cloudflare CDN → nginx (host VM) → realms-api:8001
                                              │
                                              ├── PostgreSQL (shared estimabio instance)
                                              ├── Neo4j (shared estimabio instance)
                                              └── Static files: /app (Astro), /app-legacy

realms-ingestor (worker, no public port)
realms-neo4j-sync (worker, no public port)
```

**Target domain:** `realmsouthere.com`  
**API origin:** `https://realmsouthere.com`  
**Docker network:** Joins `estimabio-network` (external)

## Docker Services

| Service | Image | Host Port | Resource Limits | Healthcheck |
|---------|-------|-----------|-----------------|-------------|
| `realms-api` | `realms:latest` | `127.0.0.1:8005:8001` | 2 CPU / 2GB RAM | `GET /api/health` |
| `realms-ingestor` | `realms:latest` | — | 1.5 CPU / 1GB RAM | Process existence |
| `realms-neo4j-sync` | `realms:latest` | — | 0.5 CPU / 512MB RAM | Process existence |

## Quick Start

```bash
cd /var/www/realms

# 1. Ensure .env has required variables (see below)
# 2. Build and start
docker compose up -d --build

# 3. Seed the database (one-time)
docker compose exec realms-api python -m scripts.seed_realms
docker compose exec realms-api python -m scripts.seed_sources

# 4. Verify
curl http://127.0.0.1:8005/api/health
curl http://127.0.0.1:8005/stats/
```

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `POSTGRES_PASSWORD` | ✅ | — | PostgreSQL password |
| `NEO4J_PASSWORD` | ✅ | — | Neo4j password |
| `OPENROUTER_API_KEY` | ✅ | — | LLM API access |
| `LITELLM_MASTER_KEY` | — | `sk-dummy` | LiteLLM proxy key |
| `REALMS_REVIEW_TOKEN` | — | — | Enable write endpoints (Phase 4) |
| `REALMS_RATE_LIMIT_PER_MINUTE` | — | 60 | API rate limit |
| `REALMS_PUBLIC_ORIGIN` | — | `https://realmsouthere.com` | Public URL for OG/SEO |
| `LOG_LEVEL` | — | `info` | Logging verbosity |

## Dockerfile

Multi-stage build:

```
Stage 1 (web-build): node:22-slim
  → npm ci && npm run build → web-next/dist/

Stage 2 (python-runtime): python:3.11-slim
  → pip install realms/requirements.txt
  → Copy all Python source + web build output
  → Run as non-root 'app' user
  → CMD: ./run_realms_api.sh
```

## Build and Deploy

### Rebuild Required (dependencies changed)

```bash
docker compose build --no-cache
docker compose up -d
```

### Code Change (volume-mounted — instant)

```bash
# Python code in realms/, scripts/, etc. reflects immediately
docker compose restart realms-api   # only if needed
```

### Astro frontend rebuild

The Astro build output is mounted from `./web-next/dist`. To rebuild:

```bash
cd web-next && npm run build
# or inside container:
docker compose exec realms-api npm run build --prefix /app/web-next
```

## nginx

Config at `nginx/realmsouthere.com.conf`:
- Reverse proxy `realmsouthere.com` → `127.0.0.1:8005`
- SSL termination (certificates managed externally)
- Static asset caching headers
- Rate limiting

## Cloudflare

- **CDN:** Caches `/app/*`, `/og/*`, `/export/*` with long TTLs
- **WAF:** Basic DDoS protection, rate limiting at edge
- **SSL:** Full (strict) — origin certificate on the VM

## Database

### Connection

```yaml
POSTGRES_HOST: postgres        # Docker service name
POSTGRES_PORT: 5432
POSTGRES_USER: estimabio
POSTGRES_DB: realms            # Separate database from estimabio
```

### Migrations

Managed via Alembic:

```bash
docker compose exec realms-api alembic revision --autogenerate -m "description"
docker compose exec realms-api alembic upgrade head
```

Migrations are stored in `migrations/versions/`. The entrypoint script `run_realms_api.sh` runs `alembic upgrade head` automatically on container start.

### Seed Data

| Seed Script | Purpose |
|-------------|---------|
| `scripts/seed_realms.py` | Entity categories, entity classes, initial entities |
| `scripts/seed_sources.py` | Load Wikipedia source URLs from `data/seed_sources.yaml` |
| `scripts/seed_archive_sources.py` | Load archive.org source URLs from `data/archive_seeds.yaml` |
| `scripts/seed_pubmed_sources.py` | PubMed seed queries for Phase 3 corroboration |

## Monitoring

- **API health:** `GET /api/health` (Docker healthcheck)
- **Metrics:** `GET /metrics/ingestion` — queue depth, throughput
- **Activity:** `GET /metrics/activity?minutes=60` — recent changes
- **Logs:** `docker compose logs -f realms-api` (JSON-file driver, 10MB × 3 files)

## Troubleshooting

### API won't start

```bash
docker compose logs realms-api     # Check startup errors
docker compose exec realms-api alembic current  # Check migration state
docker compose exec realms-api python -c "from realms.utils.database import get_engine; print('ok')"  # Check DB connectivity
```

### Ingestor not processing

```bash
docker compose logs realms-ingestor
docker compose exec realms-api psql -d "$POSTGRES_DB" -c "SELECT count(*) FROM ingestion_sources WHERE ingestion_status='pending'"
```

### Neo4j sync not working

```bash
docker compose logs realms-neo4j-sync
docker compose exec realms-neo4j-sync python -c "
from neo4j import GraphDatabase
d = GraphDatabase.driver('bolt://neo4j:7687', auth=('neo4j', '$NEO4J_PASSWORD'))
with d.session() as s:
    print(s.run('MATCH (n) RETURN count(n)').single()[0])
"
```

## Rollback

```bash
# Roll back last Alembic migration
docker compose exec realms-api alembic downgrade -1

# Redeploy previous Docker image
docker compose down
docker compose up -d --build  # rebuild from current source
```
