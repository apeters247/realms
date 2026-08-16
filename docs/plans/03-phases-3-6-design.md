# REALMS Phases 3–6 Design

**Date:** 2026-04-19
**Status:** Draft
**Scope:** Four independent subsystems delivered in sequence. Each section scoped for one implementation plan, but packaged together here because the user requested a single end-to-end pass.

---

## Guiding constraints

- **Backward compatible with Phase 2G.** Existing entities, relationships, sources, and the Neo4j mirror must continue to work untouched during and after this work.
- **Single LLM path.** Both new LLM callers (Phase 3 corroboration, Phase 4 review suggestions) use OpenRouter direct, matching the extractor and pair classifier that were already migrated.
- **Minimum new tables.** Reuse `ingestion_sources` where possible; add schema only when the existing model can't carry the information.
- **Additive migrations only.** No column drops, no non-null adds without a default.
- **API remains read-only by default.** Phase 4 introduces the first write endpoints, gated by a `REALMS_REVIEW_TOKEN` bearer header; public access stays GET-only.

---

## Phase 3 — PubMed + archive.org corroboration

### Goal

Triangulate the Wikipedia-seeded knowledge base against primary-source ethnography and peer-reviewed anthropology, so each entity accumulates a provenance score that reflects multiple independent witnesses.

### Approach

The existing `ingestion_sources` table already carries `source_type`, `doi`, `authors`, `publication_year`, `peer_reviewed`, `credibility_score`. It was designed for this. Phase 3 is almost entirely new **fetchers** plus a **corroboration view** on top of what the normalizer already does.

### Components

**1. PubMed fetcher** — `realms/ingestion/pubmed_fetcher.py`
- Uses NCBI E-utilities (esearch + efetch), no API key required for ≤3 req/s.
- Given a seed query (entity name + cultural context), returns a list of `FetchedDocument` with PMID, title, abstract, authors, year, journal, DOI.
- Caches responses to `data/pubmed/<pmid>.json`.
- Politeness: 400ms sleep between requests, exponential backoff on 429/5xx.

**2. archive.org fetcher** — `realms/ingestion/archive_fetcher.py`
- Uses the Internet Archive Scholar search API (`scholar.archive.org/search`) + fulltext endpoint.
- Targets open ethnographic monographs (Eliade, Harner, Luna, Shepard, etc.) by known author/title whitelist in `config/archive_seeds.yaml`.
- Returns chunks of ≤3500 chars matching entity names (pre-filter by regex before LLM).

**3. Source seeding** — `scripts/seed_pubmed_sources.py`, `scripts/seed_archive_sources.py`
- For each of the ~266 existing entities, generate a PubMed query using entity name + top cultural association.
- Insert `IngestionSource` rows with `source_type='pubmed'` or `source_type='archive_org'`, `ingestion_status='pending'`.
- Caps: 3 PubMed sources per entity, 2 archive.org sources per entity (to keep corpus bounded).

**4. Worker routing** — update `realms/ingestion/worker.py`
- Dispatch by `source_type`: wikipedia → `fetch_wikipedia`, pubmed → `fetch_pubmed`, archive_org → `fetch_archive`.
- Reuse the same chunk → extract → normalize → role-edges flow. The extractor doesn't care about source origin.

**5. Corroboration API** — `realms/api/routes/corroboration.py`
- `GET /corroboration/{entity_id}` — returns entity provenance broken down by `source_type`, with a computed `corroboration_tier`:
  - `tier_3`: ≥1 PubMed **and** ≥1 archive.org **and** ≥1 Wikipedia
  - `tier_2`: ≥2 distinct source_types
  - `tier_1`: single source_type only
  - `tier_0`: no sources (stub entities)
- `GET /corroboration/stats` — aggregate counts by tier.
- `GET /corroboration/conflicts/{entity_id}` — surfaces fields where different sources disagree (e.g., alignment, realm, first-documented year).

**6. UI** — extend `web/app.js` entity detail drawer
- Tier badge next to entity name (tier_3 green, tier_2 yellow, tier_1 orange, tier_0 grey).
- Provenance list grouped by source_type with inline DOI / archive.org links.

### Schema changes

None required. Reuses `ingestion_sources` (already carries all PubMed/archive.org metadata) and `entities.provenance_sources` JSONB (already stores source IDs + quotes).

Optional minor addition: index on `ingestion_sources(source_type, ingestion_status)` for faster worker routing.

### Out of scope

- Paywalled journals (JSTOR, subscription Elsevier) — covered only if open-access DOI resolves.
- Non-English sources — deferred to a later phase.

---

## Phase 4 — Inline LLM-assisted review UI

### Goal

Turn the existing `/review/entities` queue from read-only into actionable: a human reviewer can approve, reject, edit, or merge entities, with full audit trail and optional LLM suggestions.

### Components

**1. Auth** — new `realms/api/dependencies.py`
- `require_review_token` dependency checks `Authorization: Bearer <REALMS_REVIEW_TOKEN>` header against env var.
- Missing or wrong → 401. No token configured → 503 (review disabled).
- CORS extended to allow `POST, PATCH, DELETE` on `/review/*` routes only.

**2. Audit trail** — new table `review_actions`
```sql
CREATE TABLE review_actions (
    id SERIAL PRIMARY KEY,
    entity_id INT REFERENCES entities(id) ON DELETE CASCADE,
    reviewer TEXT NOT NULL,
    action TEXT NOT NULL,       -- approve | reject | edit | merge_into | unmerge
    field TEXT,                 -- for 'edit': the entity column name
    old_value JSONB,
    new_value JSONB,
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
CREATE INDEX ix_review_actions_entity ON review_actions(entity_id);
CREATE INDEX ix_review_actions_created ON review_actions(created_at);
```

**3. Write endpoints** — extend `realms/api/routes/review.py`
- `POST /review/entities/{id}/approve` — sets `Entity.consensus_confidence=max(current, 0.95)`, marks ingested_entity rows status=`approved`, inserts review_action.
- `POST /review/entities/{id}/reject` — sets `consensus_confidence=0`, adds `reviewer_notes`, flags for hide in UI. Soft delete — no row removal.
- `PATCH /review/entities/{id}` — body `{field, value, note}`; whitelisted fields only: `name, entity_type, alignment, realm, description, powers, domains`. Logs old→new.
- `POST /review/entities/{id}/merge_into/{target_id}` — reassigns all relationships from src to target, updates provenance_sources union, soft-deletes source. Idempotent.
- `POST /review/entities/{id}/suggest` — calls OpenRouter (Gemini Flash) with entity fields + all raw extractions + description; returns proposed corrections as JSON patch. No write.

**4. Suggestions LLM caller** — `realms/ingestion/review_suggester.py`
- Mirrors `pair_classifier.py` structure: `_call_openrouter`, retry, prompt file `realms/ingestion/prompts/review_suggest.md`.
- Input: all raw extractions for the entity + current consensus row.
- Output: `{suggested_fields: {name, alignment, ...}, conflicts_detected: [...], confidence: 0.xx, rationale: "..."}`.

**5. UI** — new `/app/review` view in `web/app.js`
- Queue list (reuses `/review/entities` GET).
- Keyboard nav: `j/k` next/prev, `a` approve, `r` reject, `e` edit, `s` suggest, `m` merge.
- Edit form shows side-by-side: current value, all per-source extracted values (if they disagree), LLM suggestion.
- Token enter-once via localStorage; never committed.

**6. Tests**
- `tests/test_review_actions.py` — integration test for each action type + audit row creation.
- Auth test: 401 without token, 200 with token.
- Merge test: relationships and provenance correctly re-parented.

### Schema changes

- New table `review_actions`.
- Migration: `migrations/versions/20260419_0003_review_actions.py`.

---

## Phase 5 — Temporal dimensions

### Goal

Answer *when* questions: when was an entity first documented, what historical period does the belief span, how has it evolved.

### Components

**1. Schema** — add to `entities`:
```sql
ALTER TABLE entities ADD COLUMN first_documented_year INT NULL;
ALTER TABLE entities ADD COLUMN evidence_period_start INT NULL;
ALTER TABLE entities ADD COLUMN evidence_period_end INT NULL;
ALTER TABLE entities ADD COLUMN historical_notes TEXT NULL;
CREATE INDEX ix_entities_first_documented ON entities(first_documented_year);
```
(`historical_period` JSONB on `entity_relationships` already exists and is reused.)

**2. Temporal extraction** — extractor prompt v4
- Add optional fields to the extraction JSON: `first_attested_year` (int), `historical_period` ({start_year, end_year, era_name}), `historical_notes` (text).
- Backfill existing entities opportunistically — next time a source is re-processed, these fields are populated.
- One-shot backfill script `scripts/backfill_temporal.py` that runs the suggester pipeline on entities missing temporal data.

**3. API** — new `realms/api/routes/timeline.py`
- `GET /timeline/entities?start_year=X&end_year=Y&culture=Z` — entities whose evidence_period overlaps range.
- `GET /timeline/summary` — histogram of first_documented_year by century.

**4. UI** — new Timeline tab
- Horizontal timeline (D3) showing entities as bars spanning their evidence_period.
- Hover → entity details.
- Filter by culture / region.

**5. Normalizer updates** — `realms/ingestion/normalizer.py`
- When merging extractions, resolve temporal fields: earliest `first_attested_year` wins, widest `evidence_period` wins (min start, max end), concatenate `historical_notes` with source tag.

### Schema changes

- 4 new columns on `entities`.
- 1 new index.
- Migration: `migrations/versions/20260419_0004_temporal_dimensions.py`.

---

## Phase 6 — Cross-database linking

### Goal

Link each entity to its canonical external identifier in Wikidata / VIAF / WordNet so researchers can pivot between REALMS and the broader scholarly graph.

### Components

**1. Schema** — add to `entities`:
```sql
ALTER TABLE entities ADD COLUMN external_ids JSONB DEFAULT '{}'::jsonb NOT NULL;
CREATE INDEX ix_entities_external_ids ON entities USING GIN (external_ids);
```
Structure: `{"wikidata": "Q123", "viaf": "456", "wordnet": "..."}`.

**2. Matchers** — `realms/services/external_linker.py`
- `WikidataMatcher.match(name, culture, description)` — SPARQL query: entities with label matching name, P31 (instance-of) in religion/mythology set, filtered by description cosine similarity ≥ 0.6.
- `VIAFMatcher.match(name)` — VIAF SRU query, personalName index; returns top 3 candidates with disambiguation strings.
- Both return list of `{id, label, description, confidence}` sorted by confidence.

**3. Linking job** — `scripts/link_external_ids.py`
- For each entity missing a given external_ids key, run the matcher, auto-accept if top candidate confidence ≥ 0.85 **and** 2x confidence gap over runner-up. Otherwise queue for manual review (writes to a new review_action with `action='external_link_suggest'`, `new_value={match_candidates}`).

**4. API** — `realms/api/routes/external_links.py`
- `GET /entities/{id}/external_links` — current linked IDs + display labels.
- `POST /review/entities/{id}/link` (Phase 4 auth) — body `{system: "wikidata", id: "Q123"}`; validates format, stores in `external_ids`.
- `POST /review/entities/{id}/unlink` — body `{system}`; removes key.

**5. UI** — extend entity detail card
- Badges for each external_id linking to the authority URL (Wikidata: `https://www.wikidata.org/wiki/Q123`, VIAF: `https://viaf.org/viaf/456`).

### Schema changes

- 1 new JSONB column + GIN index on `entities`.
- Migration: `migrations/versions/20260419_0005_external_ids.py`.

### Rate limits & etiquette

- Wikidata SPARQL: 60 req/min per the public endpoint. Matcher uses a 1.2s sleep.
- VIAF SRU: no documented limit; use 500ms sleep and per-session caching.

---

## Execution order and dependencies

```
P0 extractor fix ── done
       │
       ▼
Phase 3 corroboration ──┐
(fetchers + routing)    │
       │                ▼
Phase 4 review UI ──── PHASE 5 temporal ── PHASE 6 external links
(writes, audit,          (schema + prompt     (matchers + linking)
 suggester)               + UI)
```

- Phase 3 has no Phase 4/5/6 deps.
- Phase 4 audit table is reused by Phase 6 for link suggestions.
- Phase 5 is schema-only + extractor prompt; independent of others.
- Phase 6 uses Phase 4 auth for write endpoints.

---

## Testing strategy (cross-phase)

- Each phase adds integration tests against the real test Postgres (pattern already established in `tests/`).
- New marker `@pytest.mark.external` for Phase 3/6 tests that hit PubMed / Wikidata — skipped by default in CI, runnable on demand.
- Migrations tested by applying them to a clean DB and asserting no drift against ORM metadata.

---

## Rollout plan (per-phase)

1. Implement + test locally against `realms_test`.
2. Alembic migration applied on startup (already wired in `run_realms_api.sh`).
3. Worker reload (`docker compose up -d realms-ingestor`) picks up new extractor prompts / fetchers.
4. UI is static — browser refresh.

No database downtime; all migrations are additive.

---

## Open questions (flagged for review)

1. **Phase 3 corpus size**: 3 PubMed + 2 archive.org per entity × 266 entities = 1330 new sources. At 10s per extraction avg, full re-corroboration is ~3.7 hours of worker time. Acceptable?
2. **Phase 4 token management**: Single shared `REALMS_REVIEW_TOKEN` — sufficient for now, or do we need per-reviewer tokens? Recommendation: single token for MVP, revisit if >1 reviewer active.
3. **Phase 6 auto-accept threshold**: 0.85 confidence + 2x gap is conservative. Once linking starts, expect to tune.
