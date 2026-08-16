# REALMS — Research Entity Archive for Light & Metaphysical Spirit Hierarchies

Read-only public API + long-running ingestion pipeline for a provenance-tracked
knowledge base of spiritual entities documented across global indigenous traditions.

Live at https://realmsoutthere.com.

## Status (as of 2026-05-14)

| Phase | Status |
|-------|--------|
| 1 — Read-only API, SQLAlchemy ORM, seed data, integration tests | ✅ done |
| 2A — LLM ingestion pipeline (Wikipedia → free OpenRouter models → DB) | ✅ running |
| 2B — Web frontend (Astro 5 + Svelte 5 + Tailwind 4, Tufte/Obsidian redesign) | ✅ done |
| 2C — Neo4j sync worker with delete-detection | ✅ running |
| 2D — End-to-end deploy verification | ✅ done |
| 2E — Rate limiting, metrics, Alembic baseline | ✅ done |
| 2F — Pair-relationship classifier (Gemini Flash via OpenRouter) | ✅ done |
| 2G — Extractor v5 role fields, stub entities, review queue, ego graph, fuzzy search, export | ✅ done |
| 3  — PubMed + archive.org corroboration, tier badges | ✅ done |
| 4  — Inline LLM-assisted review writes (approve/reject/edit/merge/suggest) with audit trail | ✅ done |
| 5  — Temporal dimensions (first-attested, evidence period, timeline) | ✅ done |
| 6  — Cross-database linking (Wikidata SPARQL, VIAF SRU) | ✅ done |
| 7  — Integrity gate (accept ≥0.85, flag ≥0.65, reject below) | ✅ running |

## Live Data (current snapshot, 2026-05-14)

- 18,217 entities — 10,888 deity · 1,885 nature_spirit · 1,000 demonic · 526 ancestor · 463 angelic · 455 animal_ally · 445 human_specialist · 37 plant_spirit · 2,516 unclassified
- 41,932 LLM extractions, average consensus confidence 0.79
- 130,632 relationships — 30,684 typed (sibling_of 6,456 · allied_with 5,317 · parent_of 4,710 · syncretized_with 3,451 · enemy_of 2,466 · consort_of 2,422 · manifests_as 2,283 · aspect_of 1,423 · serves 1,313 · created_by 334 · teacher_of 315 · equivalent_to 87 · cognate_of 59 · …) plus 99,948 weak `co_occurs_with`
- 4,236 cultures, 4,199 geographic regions promoted from extractions (canonicalization pending — many synonymous forms still split, e.g. Greek / Greek mythology / Ancient Greek)
- 12,138 source URLs (Wikipedia + Wikisource encyclopedias + PubMed + archive.org); 10,126 completed
- 8,297 entities (46%) carry a `first_documented_year` from extractor v4+
- Review status: 18,014 unreviewed · 185 merged · 18 out_of_scope

## Documentation

Full documentation is in [`docs/`](docs/README.md):

| Document | Description |
|----------|-------------|
| `docs/01-overview.md` | Project vision, live stats, status |
| `docs/02-architecture.md` | System architecture and data flow |
| `docs/03-data-model.md` | All 12 ORM models and schema |
| `docs/04-api.md` | Complete API reference |
| `docs/05-ingestion-pipeline.md` | Deep-dive: fetch → LLM extract → normalize |
| `docs/06-frontend.md` | Astro/Svelte frontend architecture |
| `docs/07-graph.md` | Neo4j graph schema and sync |
| `docs/08-deployment.md` | Docker, nginx, Cloudflare guide |
| `docs/09-testing.md` | Test structure and how to run |
| `docs/10-operations.md` | Metrics, logging, backup, incident response |
| `docs/guides/getting-started.md` | First-time dev setup |
| `docs/guides/contributing.md` | PR workflow and code conventions |

## Quick start

```bash
cd /var/www/realms
# .env: POSTGRES_PASSWORD, LITELLM_MASTER_KEY, NEO4J_PASSWORD, OPENROUTER_API_KEY already set

docker compose up -d --build
docker compose exec realms-api python -m scripts.seed_realms      # one-time seed
docker compose exec realms-api python -m scripts.seed_sources     # load Wikipedia URLs

open http://127.0.0.1:8005/app/
```

## API at a glance

Base: `http://127.0.0.1:8005` (prod: `https://realmsouthere.com`)

| Category | Endpoints |
|----------|-----------|
| Entities | `GET /entities/` (list+filter), `GET /entities/{id}` (detail) |
| Classes | `GET /entity-classes/` |
| Hierarchy | `GET /hierarchy/tree`, `GET /hierarchy/flat` |
| Relationships | `GET /relationships/` |
| Cultures | `GET /cultures/`, `GET /cultures/{id}` |
| Regions | `GET /regions/`, `GET /regions/{id}` |
| Sources | `GET /sources/`, `GET /sources/{id}`, `GET /extractions/{id}` |
| Search | `GET /search?q=`, `GET /search/similar`, `POST /search/advanced` |
| Graph | `GET /graph/`, `GET /graph/ego/{id}` |
| Stats | `GET /stats/`, `GET /metrics/ingestion`, `GET /metrics/activity` |
| Review | `GET /review/stats`, `GET /review/entities` (token-gated writes) |
| Export | `GET /export/entities.json\|.csv`, `GET /export/relationships.csv` |
| Corroboration | `GET /corroboration/{id}` |
| Timeline | `GET /timeline/entities`, `GET /timeline/summary` |
| External links | `GET /external-links/{id}` |
| Integrity | `GET /integrity/summary`, `GET /integrity/audits` |
| Feedback | `POST /feedback` |
| Collections | `GET /collections`, `GET /collections/{slug}` |
| Changelog | `GET /changelog` |
| OG images | `GET /og/entity/{id}.png` |
| Health | `GET /api/health`, `GET /e/{entity_id}` (short permalink) |

Full reference: [`docs/04-api.md`](docs/04-api.md)

## Testing

```bash
docker compose exec realms-api pytest tests/ -v
```

**52 tests passing** (47 integration, 5 unit). See [`docs/09-testing.md`](docs/09-testing.md).
