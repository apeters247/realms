# REALMS API Reference

**Base URL:** `https://realmsouthere.com`  
**API endpoints:** `https://realmsouthere.com/{path}`  
**Swagger UI:** `https://realmsouthere.com/docs`  
**Rate limit:** 60 requests/minute per IP (configurable via `REALMS_RATE_LIMIT_PER_MINUTE`)

All endpoints return JSON. Paginated responses use `{data, pagination: {total, page, per_page, total_pages}}`.  
Successful GET: 200. Errors: 400/404/422/429/500.

## Entities

```
GET /entities
```

List with filters. **Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `entity_type` | str | — | deity, nature_spirit, demonic, angelic, ancestor, animal_ally, human_specialist, plant_spirit |
| `alignment` | str | — | beneficial, neutral, malevolent, protective, ambiguous |
| `realm` | str | — | earth, sky, underworld, water, forest, mountain, hyperspace, intermediate |
| `hierarchy_level_min` | int | — | 1–10 |
| `hierarchy_level_max` | int | — | 1–10 |
| `confidence_min` | float | — | 0.0–1.0 |
| `culture_id` | int | — | Filter by culture |
| `region_id` | int | — | Filter by region |
| `power` | str | — | Specific power |
| `domain` | str | — | Specific domain |
| `q` | str | — | Text search (name, description, alternate names) |
| `page` | int | 1 | |
| `per_page` | int | 50 | Max 100 |
| `sort` | str | `-consensus_confidence,name` | Prefix `-` for descending |
| `include_merged` | bool | false | Include rejected/merged/out_of_scope |

```
GET /entities/{id}
```

Full detail: relationships (in + out), plant connections, sources, extraction details, alternate names, external IDs, temporal data, description.

```
GET /entities/{id}/relationships
```

Outgoing relationships only.

```
GET /entities/{id}/plant-connections
```

Plant-spirit connections only.

## Entity Classes

```
GET /entity-classes
```

List taxonomy classes. Filters: `category_id`, `hierarchy_level_min/max`, `confidence_min`, `q`.

```
GET /entity-classes/{id}
```

Class detail with member entities (paginated) and provenance sources.

## Hierarchy

```
GET /hierarchy/tree
```

Nested JSON for D3.js visualization: categories → classes → entity count.

```
GET /hierarchy/flat
```

Flat list: `{id, name, level, path, entity_count, confidence}`.

## Relationships

```
GET /relationships
```

List typed edges. Filters:

| Param | Description |
|-------|-------------|
| `relationship_type` | sibling_of, parent_of, consort_of, allied_with, enemy_of, etc. |
| `source_entity_id` | |
| `target_entity_id` | |
| `confidence_min` | |
| `cultural_context` | |
| `historical_period` | |

```
GET /relationships/{id}
```

Full detail with source/target entity summaries.

## Cultures

```
GET /cultures
```

Filters: `region`, `tradition_type`, `language_family`, `q`.

```
GET /cultures/{id}
```

Detail with entity list, pantheon, sources.

## Regions

```
GET /regions
```

Filters: `region_type`, `q`.

```
GET /regions/{id}
```

Detail with entities, cultural overlap, GeoJSON boundaries.

## Sources

```
GET /sources
```

Filters: `source_type`, `publication_year_min/max`, `peer_reviewed`, `credibility_min`, `ingestion_status`, `q`.

```
GET /sources/{id}
```

Detail with ingested entities and extraction statistics.

```
GET /extractions/{id}
```

Raw LLM extraction payload, normalized data, method/parameters, review status.

## Search

```
GET /search?q=...
```

Global keyword search across entities, classes, cultures, sources. Returns categorized results.

```
GET /search/similar?q=...&threshold=0.2&limit=20
```

Trigram fuzzy name matching: "xapiri" → "Xapiripë". `threshold` 0.05–0.95, `limit` 1–100.

```
POST /search/advanced
```

Body: `{filters: {entity_type, realm, cultures, confidence_min, ...}, sort, page, per_page}`

## Graph

```
GET /graph?culture=...&rel_type=semantic&max_nodes=250
```

Cytoscape.js formatted nodes + edges. Filters by culture, relationship type (semantic vs co_occurs_with).

```
GET /graph/ego/{center_id}?depth=2&semantic_only=true
```

Ego subgraph via BFS from a central entity. Configurable depth and edge type filter.

## Stats & Metrics

```
GET /stats
```

Aggregate counts: total by type/realm/alignment/culture, avg confidence, sources processed.

```
GET /metrics/ingestion
```

Queue depth + throughput for ingestion pipeline.

```
GET /metrics/activity?minutes=60
```

Recent changes: new sources, new edges, semantic additions.

## Review

```
GET /review/stats
```

Quality metrics: low-confidence counts, single-source entities, isolated entities.

```
GET /review/entities?confidence_max=0.7&isolated_only=true
```

QA candidate queue for review. Token-gated write endpoints (require `REALMS_REVIEW_TOKEN`).

## Export

```
GET /export/entities.csv|.json
GET /export/relationships.csv
GET /export/cultures.json
GET /export/sources.json
```

Public data dumps.

## Corroboration

```
GET /corroboration/{entity_id}
```

Tier badge and sources grouped by type (tier_0 through tier_3).

## Timeline

```
GET /timeline/entities?start_year=-2000&end_year=500
GET /timeline/summary
```

Temporal data. Only populated for entities with `first_documented_year` from extractor v4+.

## External Links

```
GET /external-links/{entity_id}
```

Cross-database references (Wikidata, VIAF).

## Integrity

```
GET /integrity/summary
GET /integrity/audits
```

Integrity gate corpus-level scores and audit records.

## Feedback

```
POST /feedback
```

Public error reporting submission. Body: `{entity_id?, field?, issue_type, message, reporter_email?}`.

## Collections

```
GET /collections
GET /collections/{slug}
```

Curated collections.

## Changelog

```
GET /changelog
```

Recent changes feed.

## OG Images

```
GET /og/entity/{id}.png
```

Auto-generated Open Graph preview images for entity pages.

## Utility Endpoints

```
GET /api/health
```
`{"status": "healthy", "service": "realms-api", "timestamp": "..."}`

```
GET /e/{entity_id}
```
Short permalink → redirects to canonical slug URL (cite `realmsouthere.com/e/42` in papers).

```
GET /
```
Redirects to `/app/` (web UI) or returns API info JSON.
