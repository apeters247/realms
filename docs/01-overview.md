# REALMS Overview

**REALMS** (Research Entity Archive for Light & Metaphysical Spirit Hierarchies) is an open-access knowledge base documenting spiritual entities from global indigenous traditions, with special focus on those encountered through entheogenic practices.

**Live at:** https://realmsouthere.com  
**Repository:** `/var/www/realms` (Docker Compose project)

## Vision

To create the most comprehensive provenance-tracked knowledge base mapping spiritual entity hierarchies, geographic/cultural origins, documented powers and domains, connections to plant teachers, and historical accounts across indigenous traditions.

## Scope

| Tradition Area | Examples |
|----------------|----------|
| Amazonian | Shipibo, mestizo vegetalismo, Yanomami, ayahuasca traditions |
| African diaspora | Yoruba/Orisha, Vodun, Santeria, Candomblé |
| Siberian/Uralic | Nenets, Nganasan, Yakut shamanism, Tengrism |
| Native American | Kachina, Ojibwe, Navajo, Cherokee, Inca |
| Polynesian/Melanesian | Hawaiian, Maori, Samoan, Pulotu framework |
| Global entheogenic | DMT entity encounters, machine elves, tryptamine experiences |
| Classical/European | Greek, Roman, Celtic, Norse mythology |
| Abrahamic | Angelic hierarchies, demonology, saint traditions |

## Live Data (2026-05-14)

| Metric | Value |
|--------|-------|
| Entities | **18,217** (10,888 deity, 1,885 nature_spirit, 1,000 demonic, 526 ancestor, 463 angelic, 455 animal_ally, 445 human_specialist, 37 plant_spirit, 2,516 unclassified) |
| Relationships | **130,632** (30,684 typed + 99,948 co-occurrence) |
| LLM extractions | 41,932 at avg 0.79 consensus confidence |
| Source URLs | 12,138 (10,126 completed) |
| Cultures | 4,236 (promoted from extractions) |
| Geographic regions | 4,199 (promoted from extractions) |
| Entities with first_documented_year | 8,297 (46%) |
| Review status | 18,014 unreviewed / 185 merged / 18 out_of_scope |

## Status Dashboard

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Read-only API, SQLAlchemy ORM, seed data, integration tests | ✅ Done |
| 2A | LLM ingestion pipeline (Wikipedia → OpenRouter → DB) | ✅ Running |
| 2B | Web frontend (Astro 5 + Svelte 5 + Tailwind 4) | ✅ Done |
| 2C | Neo4j sync worker with delete-detection | ✅ Running |
| 2D | End-to-end deploy verification | ✅ Done |
| 2E | Rate limiting, metrics, Alembic baseline | ✅ Done |
| 2F | Pair-relationship classifier (Gemini Flash via OpenRouter) | ✅ Done |
| 2G | Extractor v5 role fields, stub entities, review queue, ego graph, fuzzy search, export | ✅ Done |
| 3 | PubMed + archive.org corroboration, tier badges | ✅ Done |
| 4 | Inline LLM-assisted review writes with audit trail | ✅ Done |
| 5 | Temporal dimensions (first-attested, evidence period, timeline) | ✅ Done |
| 6 | Cross-database linking (Wikidata SPARQL, VIAF SRU) | ✅ Done |
| 7 | Integrity gate (accept ≥0.85, flag ≥0.65, reject below) | ✅ Running |

## Key Features

- **Entity Database** — 18K+ spiritual beings with attributes, powers, domains
- **Hierarchy Mapping** — Typed entity classes within categories
- **Relationship Graph** — 14 semantic relationship types + weak co-occurrence
- **Geographic Mapping** — Origins and cultural distribution with Leaflet
- **Plant Connections** — Links to teacher plants and ethnobotanical knowledge
- **Provenance Tracking** — Source lineage with extraction confidence, consensus scoring
- **Corroboration Tiers** — Tier 0–3 badges based on source diversity and credibility
- **Cross-Database Linking** — Wikidata SPARQL, VIAF SRU authority control
- **Timeline** — First-documented years, evidence periods
- **Interactive Visualization** — Cytoscape.js knowledge graphs, D3 hierarchy, Leaflet maps
- **Read-Only Public API** — Open for research, education, exploration
- **Integrity Gate** — 2-stage (quote check + semantic LLM verification) per extraction

## Architecture at a Glance

```
Postgres ←──────── Neo4j (30s sync, MERGE + delete-stale)
     │                    ▲
     │                    │
     ▼                    │
 realms-api (FastAPI) ──→ static web/ at /app/ (Astro 5)
     ▲
     │  LiteLLM / OpenRouter → Claude Sonnet / Gemini Flash / free models
     │
 realms-ingestor ── fetch → chunk → extract → normalize → role-edges → promote-dims
```

Three Docker services: `realms-api`, `realms-ingestor`, `realms-neo4j-sync`.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, Uvicorn |
| ORM | SQLAlchemy 2.0 (DeclarativeBase, Mapped types) |
| Database | PostgreSQL 15 |
| Knowledge Graph | Neo4j 5 |
| Frontend | Astro 5 + Svelte 5 + Tailwind CSS 4 |
| LLM | OpenRouter (Claude Sonnet, Gemini Flash, free tier models) |
| Containerization | Docker + Docker Compose |
| Reverse Proxy | nginx |
| CDN | Cloudflare |
| Visualization | Cytoscape.js, D3.js, Leaflet.js, Fuse.js |

## Relationship Type Taxonomy

Typed edges from extraction role fields + pair classifier:

| Type | Count | Description |
|------|-------|-------------|
| `sibling_of` | 6,456 | Same parent/class |
| `allied_with` | 5,317 | Cooperative relationship |
| `parent_of` | 4,710 | Direct parent-child |
| `syncretized_with` | 3,451 | Syncretic equivalence |
| `enemy_of` | 2,466 | Antagonistic |
| `consort_of` | 2,422 | Marital/romantic partner |
| `manifests_as` | 2,283 | Aspect/manifestation |
| `aspect_of` | 1,423 | Sub-aspect of another |
| `serves` | 1,313 | Servant/subordinate |
| `created_by` | 334 | Creator-creation |
| `teacher_of` | 315 | Teacher-student |
| `equivalent_to` | 87 | Cross-pantheon equivalence |
| `cognate_of` | 59 | Linguistic/cultural cognate |
| `co_occurs_with` | 99,948 | Weak: same source chunk |
