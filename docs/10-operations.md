# REALMS Operations Guide

## Logging

All services log to Docker's JSON-file driver:

| Service | Max Size | Max Files | Location |
|---------|----------|-----------|----------|
| realms-api | 10MB | 3 | `docker compose logs realms-api` |
| realms-ingestor | 10MB | 5 | `docker compose logs realms-ingestor` |
| realms-neo4j-sync | 10MB | 3 | `docker compose logs realms-neo4j-sync` |

Log level controlled by `LOG_LEVEL` env var (default: `info`).

### Key Log Patterns

```
# Ingestion worker activity
realms-ingestor | INFO: Claimed source #12345 (Wikipedia: Orisha)
realms-ingestor | INFO: Fetched https://en.wikipedia.org/wiki/Orisha (41203 chars)
realms-ingestor | INFO: Chunked into 8 chunks
realms-ingestor | INFO: Extracted 14 entities from chunk 3 (model=..., conf=0.85)
realms-ingestor | INFO: Created entity: Oshun (id=18218, conf=0.85)
realms-ingestor | INFO: Merged entity: Yemaya (id=142, conf=0.79)

# Orphan recovery
realms-ingestor | WARNING: Resetting 3 orphaned sources (stuck >30m)

# Integrity gate
realms-ingestor | INFO: Integrity: Oshun score=0.92 action=ACCEPT

# Neo4j sync
realms-neo4j-sync | INFO: Sync pass: {'classes': 12, 'cultures': 36, 'regions': 29, 'entities': 218, 'relationships': 1422}
```

## Metrics

### API Metrics

| Endpoint | What It Returns |
|----------|-----------------|
| `GET /stats/` | Aggregate entity counts by type/realm/alignment/culture |
| `GET /metrics/ingestion` | Queue depth, throughput, error rate |
| `GET /metrics/activity?minutes=60` | Recent changes: new sources, edges, semantic additions |

### Integrity Metrics

| Endpoint | What It Returns |
|----------|-----------------|
| `GET /integrity/summary` | Corpus-level integrity score |
| `GET /integrity/audits` | Historical oracle sampling records |

### Review Metrics

| Endpoint | What It Returns |
|----------|-----------------|
| `GET /review/stats` | Low-confidence, single-source, isolated entity counts |

## Monitoring

### Health Check

```
GET /api/health
→ {"status": "healthy", "service": "realms-api", "timestamp": "..."}
```

Docker healthcheck runs every 30s, timeout 10s, 3 retries, 40s start period.

### What to Watch

1. **Ingestor stalled** — no new `processed_at` timestamps on `ingestion_sources` for >30 min
2. **Neo4j sync errors** — `docker compose logs realms-neo4j-sync` showing connection errors
3. **OpenRouter quota** — daily free-tier limit hit, check `per-day` in ingestor logs
4. **Disk space** — `data/raw/` cache grows unbounded; monitor `data/` directory size

## Backup

REALMS shares the EstimaBio backup infrastructure. Database backups are handled at the PostgreSQL level:

```bash
docker compose exec postgres pg_dump -U estimabio realms > /backup/realms_$(date +%Y%m%d).sql
```

Review `scripts/backup_local.sh` in the EstimaBio project for the full backup schedule.

## Cron Jobs

REALMS has no independent cron jobs. The ingestor and Neo4j sync run as long-lived Docker services.

## Incident Response

### Ingestor Crash Loop

```bash
docker compose logs realms-ingestor | tail -50
# Check for:
#   - OpenRouter API key issues
#   - PostgreSQL connection errors
#   - Disk space for raw cache
docker compose restart realms-ingestor
```

### API Slow / Unresponsive

```bash
docker compose logs realms-api | tail -50
# Check for:
#   - Slow queries (long-running DB transactions)
#   - Memory pressure (check docker stats)
docker compose stats realms-api
# Fix: restart or increase memory limit in docker-compose.yml
```

### Database Connection Issues

```bash
docker compose exec realms-api python -c "
from realms.utils.database import get_engine
e = get_engine()
print('Connected:', e.connect())
"
```

### Corrupted Data

1. Stop the ingestor: `docker compose stop realms-ingestor`
2. Identify affected entities via integrity audit
3. Revert via `review_actions` audit trail if reviewed
4. Re-ingest the affected sources: reset their `ingestion_status` to `pending`
5. Restart the ingestor

## Capacity Planning

| Resource | Current | Limit | Notes |
|----------|---------|-------|-------|
| Entities | 18,217 | — | Growing at ~500/day |
| Relationships | 130,632 | — | ~2K new edges/day |
| Source URLs | 12,138 | — | ~100 new/day |
| PostgreSQL | Shared | 2GB RAM | Connection pool: 10 |
| Neo4j | Shared | — | ~20K nodes, ~130K edges |
| Disk (raw cache) | ~200MB | — | data/raw/, grows unbounded |

### Scaling Considerations

- **API:** Stateless, can scale horizontally behind load balancer
- **Ingestor:** Currently limited to 1 concurrent chunk to avoid OpenRouter rate limits
- **Database:** Add read replica for heavy query loads
- **Neo4j:** Cluster for read scaling if needed
