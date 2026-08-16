# REALMS Data Model

## Philosophy: Provenance-First Design

Every entity record preserves complete source lineage with confidence scoring. No data enters the system without traceable provenance. The schema uses a three-layer model:

1. **Source Layer** — Which document(s) state a fact
2. **Extraction Layer** — How we got it from the document (LLM prompt version, model, temperature)
3. **Consensus Layer** — How multiple sources agree/disagree (confidence propagated)

## Entity Relationship Diagram (Textual)

```
ingestion_sources ──┐
     │              │
     ▼              │
ingested_entities   │
     │              │
     ▼              ▼
entity_categories ──► entity_classes ──► entities ◄── entity_relationships
     │                    │                │  │              │
     │                    │                │  │              │
     ▼                    ▼                │  ▼              │
     └────────────────────────────────────┘  plant_spirit_connections
                                             │
                                             ▼
cultures ◄────────────────────────────────► geographic_regions

review_actions ◄── entities
integrity_audits (independent, no FK)
feedback_reports ◄── entities (nullable FK)
```

## Table Details

### ingestion_sources

Tracks every document/source processed.

| Column | Type | Notes |
|--------|------|-------|
| id | PK | Serial |
| source_type | VARCHAR(50) | enum: academic, internet, book, oral, ethnographic, wikipedia, wikisource, pubmed, archive_org, primary_source |
| source_name | VARCHAR(500) | Full title or name |
| authors | JSONB | `[{name, affiliation}]` |
| publication_year | INT | Indexed |
| doi | VARCHAR(100) | Indexed |
| url | TEXT | |
| credibility_score | FLOAT | CHECK 0–1 |
| peer_reviewed | BOOLEAN | |
| ingestion_status | VARCHAR(20) | pending, processing, completed, failed — indexed |
| raw_content_hash | VARCHAR(64) | SHA256 of original content |
| storage_path | VARCHAR(500) | Cache file location |
| error_log | TEXT | If processing failed |
| created_at / updated_at | TIMESTAMPTZ | |

Relationships: `ingested_entities` (cascade delete)

### ingested_entities

Raw extraction output before normalization.

| Column | Type | Notes |
|--------|------|-------|
| id | PK | Serial |
| source_id | FK → ingestion_sources | CASCADE |
| extraction_method | VARCHAR(50) | llm_prompt_v5, etc. |
| llm_model_used | VARCHAR(100) | e.g. anthropic/claude-sonnet-4.5 |
| llm_temperature | FLOAT | |
| llm_prompt_version | VARCHAR(20) | v5 |
| raw_extracted_data | JSONB | Full LLM output |
| normalized_data | JSONB | After cleanup |
| entity_name_raw / normalized | VARCHAR(500) | Before/after standardization |
| extraction_confidence | FLOAT | CHECK 0–1, indexed |
| extraction_context | TEXT | Surrounding text |
| quote_context | TEXT | Direct quote ≤500 chars |
| integrity_meta | JSONB | Pipeline record: score, action, checks |
| status | VARCHAR(20) | raw, normalized, confirmed, rejected — indexed |
| created_at / updated_at | TIMESTAMPTZ | |

### entity_categories

Top-level taxonomy (e.g. "Deities", "Nature Spirits").

| Column | Type | Notes |
|--------|------|-------|
| id | PK | Serial |
| name | VARCHAR(100) | UNIQUE |
| parent_id | FK → self | For subcategories |
| icon_emoji | VARCHAR(10) | UI display |
| sources | JSONB | Source IDs defining this category |

### entity_classes

Specific types within categories (e.g. "Orisha", "Kachina", "Angel").

| Column | Type | Notes |
|--------|------|-------|
| id | PK | Serial |
| category_id | FK → entity_categories | CASCADE, indexed |
| name | VARCHAR(200) | Indexed |
| alternate_names | JSONB | `{language: [names]}` |
| core_powers | JSONB | |
| associated_plants | JSONB | |
| hierarchy_level | INT | 1–10 |
| confidence_score | FLOAT | CHECK 0–1 |

### entities

The main table — 18,217 rows and growing.

| Column | Type | Notes |
|--------|------|-------|
| id | PK | Serial |
| entity_class_id | FK → entity_classes | SET NULL |
| name | VARCHAR(200) | |
| entity_type | VARCHAR(50) | deity, nature_spirit, demonic, angelic, ancestor, animal_ally, human_specialist, plant_spirit — indexed |
| alignment | VARCHAR(20) | beneficial, neutral, malevolent, protective, ambiguous — indexed |
| realm | VARCHAR(100) | earth, sky, underworld, water, forest, mountain, hyperspace, intermediate — indexed |
| description | TEXT | |
| powers / domains | JSONB | |
| cultural_associations | JSONB | Free-form names from extraction |
| geographical_associations | JSONB | |
| alternate_names | JSONB | `{language: [names]}` |
| consensus_confidence | FLOAT | CHECK 0–1, indexed |
| first_documented_year | INT | Phase 5 — indexed |
| evidence_period_start / end | INT | Phase 5 |
| external_ids | JSONB | Phase 6 — `{wikidata: Q123, viaf: 456}` |
| review_status | VARCHAR(20) | unreviewed, merged, out_of_scope, rejected, approved — indexed |
| extraction_instances | JSONB | Array of ingested_entity IDs |
| provenance_sources | JSONB | Array of ingestion_source IDs |

Relationships: `outgoing_relationships`, `incoming_relationships`, `plant_connections`

### entity_relationships

Directed, typed edges between entities.

| Column | Type | Notes |
|--------|------|-------|
| id | PK | Serial |
| source_entity_id | FK → entities | CASCADE, indexed |
| target_entity_id | FK → entities | CASCADE, indexed |
| relationship_type | VARCHAR(50) | sibling_of, parent_of, consort_of, allied_with, enemy_of, etc. — indexed |
| description | TEXT | |
| strength | VARCHAR(20) | strong, moderate, weak |
| extraction_confidence | FLOAT | CHECK 0–1 |
| cultural_context | JSONB | |
| provenance_sources | JSONB | Source IDs |

### plant_spirit_connections

Links entities to plants/compounds (bridge to EstimaBio).

| Column | Type | Notes |
|--------|------|-------|
| id | PK | Serial |
| compound_id | VARCHAR(36) | FK → compounds (EstimaBio) |
| entity_id | FK → entities | CASCADE |
| relationship_type | VARCHAR(50) | teacher, ally, owner, manifestation, guardian |
| preparation_method | VARCHAR(100) | ayahuasca, tobacco, diet, smoke |

### cultures

Auto-promoted from `Entity.cultural_associations`.

| Column | Type | Notes |
|--------|------|-------|
| id | PK | Serial |
| name | VARCHAR(200) | Indexed |
| language_family | VARCHAR(100) | |
| region | VARCHAR(100) | Indexed |
| tradition_type | VARCHAR(50) | vegetalismo, shamanism, orisha_worship — indexed |
| primary_plants | JSONB | |
| entity_pantheon | JSONB | |

### geographic_regions

Auto-promoted from `Entity.geographical_associations`.

| Column | Type | Notes |
|--------|------|-------|
| id | PK | Serial |
| name | VARCHAR(200) | Indexed |
| region_type | VARCHAR(50) | Indexed |
| center_latitude / longitude | FLOAT | |
| boundary_geojson | JSONB | For map display |
| endemic_entities / shared_entities | JSONB | |

### review_actions

Audit trail for Phase 4 manual review operations.

| Column | Type | Notes |
|--------|------|-------|
| id | PK | Serial |
| entity_id | FK → entities | CASCADE, indexed |
| reviewer | VARCHAR(200) | |
| action | VARCHAR(50) | approve, reject, edit, merge, link |
| field | VARCHAR(100) | Which field changed |
| old_value / new_value | JSONB | Before/after |
| note | TEXT | |

### integrity_audits

Corpus-level oracle sampling records.

| Column | Type | Notes |
|--------|------|-------|
| id | PK | Serial |
| audited_at | TIMESTAMPTZ | Indexed |
| sample_size | INT | |
| n_supported / n_ambiguous / n_contradicted | INT | |
| oracle_model | VARCHAR(100) | |
| sample_ids | JSONB | `[{ext_id, claim, quote, verdict, conf}]` |

### feedback_reports

Public error-reporting submissions (Stream R).

| Column | Type | Notes |
|--------|------|-------|
| id | PK | Serial |
| entity_id | FK → entities | CASCADE |
| issue_type | VARCHAR(40) | Indexed |
| message | TEXT | |
| reporter_email | VARCHAR(200) | |
| reporter_ip_hash | VARCHAR(64) | |
| status | VARCHAR(20) | open, resolved — indexed |

## Key Indexes

| Index | Table | Purpose |
|-------|-------|---------|
| `idx_ingestion_sources_status` | ingestion_sources | Worker polls pending sources |
| `idx_entities_type` | entities | Filter by type |
| `idx_entities_alignment` / `idx_entities_realm` | entities | Filter by alignment/realm |
| `idx_entities_confidence` | entities | Sort/filter by confidence |
| `idx_entities_name_trgm` | entities | pg_trgm GIN for fuzzy name search |
| `idx_entity_relationships_type` | entity_relationships | Filter by type |
| GIN on `provenance_sources` | entities | Source lookup |

## Confidence Propagation

- **Extraction confidence** (0–1) from LLM per-entity field
- **Consensus confidence** = mean of all `extraction_confidence` values across extraction instances
- **Source credibility** (0–1) based on peer review, author expertise
- Integrity gate combines deterministic quote check + semantic LLM verification
