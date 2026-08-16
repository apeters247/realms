# REALMS Documentation

Live at [realmsouthere.com](https://realmsouthere.com) — a provenance-tracked knowledge base of ~18,200 spiritual entities from global indigenous traditions.

## Quick Navigation

| Audience | Start Here |
|----------|-----------|
| **New developer** | `guides/getting-started.md` — clone, configure, run |
| **API consumer** | `04-api.md` — endpoint reference |
| **Contributor** | `guides/contributing.md` — PR workflow, code style |
| **Deploying / ops** | `08-deployment.md` → `10-operations.md` |
| **Understanding the system** | `01-overview.md` → `02-architecture.md` |

## Document Index

### Reference (read in order for full context)

| # | Document | What It Covers |
|---|----------|----------------|
| 01 | `01-overview.md` | Project vision, live stats, status dashboard, retired phases |
| 02 | `02-architecture.md` | System components, data flow, service boundaries, tech choices |
| 03 | `03-data-model.md` | All 12 ORM models, key fields, indexes, relationships |
| 04 | `04-api.md` | Complete API reference for all 21+ routers |
| 05 | `05-ingestion-pipeline.md` | Deep-dive: fetch → chunk → extract → normalize → edges → promote |
| 06 | `06-frontend.md` | Astro 5 + Svelte 5 architecture, component tree, page routes |
| 07 | `07-graph.md` | Neo4j schema, sync mechanism, query patterns |
| 08 | `08-deployment.md` | Docker, nginx, Cloudflare, CI/CD |
| 09 | `09-testing.md` | Test structure, markers, DB setup, how to run |
| 10 | `10-operations.md` | Metrics, logging, backup, cron, incident response |

### Guides

| Document | Purpose |
|----------|---------|
| `guides/getting-started.md` | First-time setup for new developers |
| `guides/contributing.md` | PR workflow, code conventions, commit guidelines |

### Historical Plans

| Document | Phase | Status |
|----------|-------|--------|
| `plans/01-mvp-phase1.md` | Phase 1 — Read-only API, ORM, seed data, tests | ✅ Implemented |
| `plans/02-phase2-ingestion.md` | Phase 2 — Ingestion pipeline, frontend, Neo4j sync | ✅ Implemented |
| `plans/03-phases-3-6-design.md` | Phases 3–6 design spec | ✅ Implemented |
| `plans/04-ui-redesign.md` | Tufte × Obsidian UI redesign spec | ✅ Implemented |
| `plans/05-10week-launch.md` | 10-week public launch sprint plan | ✅ Implemented |
| `plans/06-data-quality.md` | Data quality + phenomenological pipeline | ✅ Implemented |

### Launch & Promotional

| Document | Purpose |
|----------|---------|
| `launch/reddit_posts.md` | Reddit launch post drafts for r/mythology, etc. |

### LLM Prompts (Runtime)

The prompt templates used by the ingestion pipeline live in `realms/ingestion/prompts/`:
- `extract_entities.md` — v5 extraction prompt (30+ output fields)
- `classify_pair.md` — v1 pair-relationship classification prompt

---

*Last updated: 2026-05-18*
