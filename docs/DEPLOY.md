# REALMS Deployment Guide

**Target domain:** `realms.cloud` (or your chosen domain; set at launch time).

## Architecture

```
┌─────────────────────┐
│ Cloudflare CDN / WAF │  ← cache everything under /app/*, /og/*, /export/*
└──────────┬───────────┘
           │ origin
           ▼
┌─────────────────────┐      ┌─────────────────────┐
│   realms-api        │─PG──▶│   postgres          │
│ (FastAPI + uvicorn) │      │ (schema managed by  │
│ + static web-next   │      │  Alembic)           │
└──────────┬──────────┘      └─────────────────────┘
           │
           ├─ realms-ingestor  (Claude Sonnet 4.5, premium)
           ├─ realms-ingestor-2 (Gemini 2.0 Flash, bulk)
           ├─ realms-ingestor-3 (Gemini 2.0 Flash, bulk)
           ├─ realms-ingestor-4 (Gemini 2.0 Flash, bulk)
           └─ realms-neo4j-sync (30s tick → Neo4j mirror)
```

## Launch-day env vars

Set in the API container's environment (via `.env` loaded by docker-compose):

| Variable | Required? | Purpose |
|----------|-----------|---------|
| `REALMS_PUBLIC_ORIGIN` | **yes** | public HTTPS URL. Sets canonical URLs, sitemap, OG. Example: `https://realms.cloud`. |
| `REALMS_API_ORIGIN` | build | build-time loader target. Example: `http://realms-api:8001` (internal). |
| `REALMS_BASE_PATH` | — | path prefix. Defaults to `/app`. Leave alone unless you mount at root. |
| `OPENROUTER_API_KEY` | **yes** | LLM extraction + verification + oracle. |
| `POSTGRES_PASSWORD` | **yes** | DB auth. |
| `NEO4J_PASSWORD` | yes | graph mirror. |
| `REALMS_REVIEW_TOKEN` | yes (post-launch) | secret string; enables the researcher write endpoints. Keep off in launch week. |
| `REALMS_INTEGRITY_GATE` | `off` at launch | once v4 re-ingestion is verified clean, flip to `on`. |
| `REALMS_ORACLE_MODEL` | default OK | `anthropic/claude-opus-4` for nightly audits. |

## Build & deploy

```bash
# 1. Static site build (Node 22)
cd /var/www/realms/web-next
REALMS_API_ORIGIN=http://realms-api:8001 \
REALMS_PUBLIC_ORIGIN=https://realms.cloud \
  npm run build

# 2. API image rebuild (only when Dockerfile or requirements change)
cd /var/www/realms
docker compose build realms-api

# 3. Apply schema migrations
docker exec realms-api alembic upgrade head

# 4. Bring stack up
docker compose up -d
```

## Cloudflare setup

1. Add `realms.cloud` to a Cloudflare zone. Flip DNS proxy to **orange-cloud** (proxied).
2. Origin: the machine running the docker stack. Use a port-forward or reverse proxy to expose `8005` (or whichever host port maps to `realms-api:8001`) as `443`.
3. Page Rules:
   - `https://realms.cloud/app/*`: Cache Everything, Edge Cache TTL 1 hour, Browser TTL 5 min.
   - `https://realms.cloud/og/*`: Cache Everything, Edge 7 days.
   - `https://realms.cloud/export/*`: Cache Everything, Edge 1 hour.
   - `https://realms.cloud/api/health`: Bypass cache.
4. WAF: enable the **Managed Rules** ruleset. Add custom rule to challenge requests with **no Accept-Language header** (basic bot filter).
5. Under **Speed → Optimization**: enable Brotli. Disable Rocket Loader (breaks Cytoscape).
6. **SSL/TLS → Edge Certificates**: set "Full (strict)" once origin has a valid cert (use Cloudflare origin cert, 15-year).

## TLS at origin

Two options; pick one.

### Option A — Cloudflare Origin Certificate (recommended)

```
# On the host, request Cloudflare origin cert from the dashboard.
# Save to /etc/ssl/realms/{origin.pem,origin.key}
# Front the docker stack with nginx:
sudo apt-get install nginx
# /etc/nginx/sites-available/realms:
server {
    listen 443 ssl http2;
    server_name realms.cloud;
    ssl_certificate /etc/ssl/realms/origin.pem;
    ssl_certificate_key /etc/ssl/realms/origin.key;
    location / { proxy_pass http://127.0.0.1:8005; proxy_set_header Host $host; }
}
```

### Option B — Let's Encrypt

```
sudo snap install --classic certbot
sudo certbot --nginx -d realms.cloud -d www.realms.cloud
```

Either way, the container itself serves plain HTTP — TLS terminates at nginx or Cloudflare.

## Sitemap submission (day-of-launch)

1. Verify ownership of `realms.cloud` at
   [Google Search Console](https://search.google.com/search-console/) and
   [Bing Webmaster Tools](https://www.bing.com/webmasters/).
2. Submit sitemap URL: `https://realms.cloud/app/sitemap-index.xml`.
3. Confirm `robots.txt` allows `Googlebot`, `Google-Extended`, `CCBot`.

## Health checks

- `GET /api/health` → `{"status":"healthy"}` → use as Cloudflare health check.
- `GET /integrity/stats` → corpus integrity score; page `/about/methodology/` shows the live badge.
- `GET /metrics/ingestion` → pending-sources backlog and throughput.

## Performance budget

- Home page LCP ≤ 1.2s (Cloudflare-cached), ≤ 2s origin-cold.
- Entity page LCP ≤ 1.5s cached, ≤ 3s origin-cold.
- Graph page JS ≤ 300KB gzipped; rendering of a 500-node corpus ≤ 3s.

If origin p95 exceeds budget, first check CPU contention with the
ingestor workers — they should be throttled or scheduled off-peak.

## Cost ceiling

- Cloudflare free tier covers all CDN + WAF + DNS + SSL for a launch.
- API host: anything with 2 CPU / 4GB RAM is enough while ingestion is
  not running. During ingestion, CPU spikes to 90%+ on one or two
  workers; budget 4–6 CPU total if ingestion runs continuously.
- LLM costs are the main variable — see `docs/superpowers/specs/2026-04-20-realms-10week-public-launch.md` for the cost model (~$420 to get to 2,500 entities at 99% integrity).

## Post-launch operations

### Enable the integrity gate

Once a sample of v4 extractions is confirmed to emit verbatim quotes the gate can verify:

```
REALMS_INTEGRITY_GATE=on
REALMS_INTEGRITY_ACCEPT=0.99
REALMS_INTEGRITY_FLAG=0.90
```

### Nightly oracle audit (cron)

Add to the host's crontab:

```
0 3 * * *  docker exec realms-api python -m scripts.run_integrity_oracle --sample 20 --days 1
```

### Purge flagged material

Weekly review:

```
docker exec realms-api python -m scripts.purge_out_of_scope --dry-run
# review the generated data/purge_audit_*.jsonl
docker exec realms-api python -m scripts.purge_out_of_scope --apply
```

### Dataset dump refresh

The dataset zip is generated on-demand at `/export/dataset.zip`. If traffic
justifies it, add a nightly cron:

```
0 4 * * *  curl -s -o /var/www/realms/data/realms-$(date +\%Y\%m\%d).zip \
             https://realms.cloud/export/dataset.zip
```
