# REALMS Ingestion Pipeline

## Lifecycle of a Source URL

```
User seeds URL ──► DB (ingestion_sources, status=pending)
                       │
                ┌──────▼──────┐
                │  Worker     │  polls every 20s
                │  run_once() │  (60s idle if queue empty)
                └──────┬──────┘
                       │
                ┌──────▼──────┐
                │  Claim      │  SELECT FOR UPDATE SKIP LOCKED
                │  source     │  priority: encyclopedia > wiki > archive > book > pubmed
                └──────┬──────┘
                       │
                ┌──────▼──────┐
           ┌────┤  Fetch      ├────┐
           │    └──────┬──────┘    │
           ▼           ▼           ▼
     Wikipedia   Wikisource   PubMed/archive.org/HTML
     REST API    MediaWiki    generic HTTP + BeautifulSoup
           │           │           │
           └───────────┼───────────┘
                       ▼
                ┌──────────────┐
                │  Cache       │  SHA256(url).txt → data/raw/
                │  on disk     │  Re-fetches use cache
                └──────┬──────┘
                       ▼
                ┌──────────────┐
                │  Chunk       │  ~3500 chars, paragraph-boundary
                │  chunker.py  │  section headings tracked
                └──────┬──────┘
                       ▼
           ┌───────────────────────┐
           │  LLM Extraction       │  ThreadPoolExecutor
           │  Per chunk:           │  (CHUNK_CONCURRENCY=1 to avoid
           │  OpenRouter → models  │   OpenRouter rate limits)
           └──────────┬────────────┘
                      ▼
           ┌───────────────────────┐
           │  Integrity Gate       │  2-stage:
           │  integrity_gate.py    │  1. Quote presence check
           │                       │  2. Semantic claim verify (LLM)
           │  Accept ≥0.85         │
           │  Flag ≥0.65           │
           │  Reject <0.65         │
           └──────────┬────────────┘
                      ▼
           ┌───────────────────────┐
           │  Normalize + Upsert   │  exact name → trigram fuzzy → merge
           │  normalizer.py        │  consensus confidence recomputed
           └──────────┬────────────┘
                      ▼
           ┌───────────────────────┐
           │  Role Edges           │  role fields → 14 typed relationship types
           │  relationships.py     │  stubs created for unknown targets
           │                       │  co_occurs_with between chunk pairs
           └──────────┬────────────┘
                      ▼
           ┌───────────────────────┐
           │  Promote Dimensions   │  backfill Culture + GeographicRegion
           │  promote_dimensions.py│  from entity.cultural_associations
           └──────────┬────────────┘
                      ▼
           ┌───────────────────────┐
           │  Canonicalization     │  every 20 sources: deduplicate
           │  (canonicalize)       │  cultural association strings
           └──────────┬────────────┘
                      ▼
           Mark source "completed" with processed_at timestamp
```

## Key Components

### 1. Fetcher (`realms/ingestion/fetcher.py`)

Four fetch strategies dispatched by source type:

| Source Type | Strategy | Function |
|-------------|----------|----------|
| `wikipedia.org` | MediaWiki `action=query&prop=extracts` + `explaintext` | `fetch_wikipedia()` |
| `wikisource.org` | MediaWiki `action=parse&prop=text` → BeautifulSoup strip | `fetch_wikisource()` |
| `pubmed` / PubMed URLs | NCBI E-utilities via `pubmed_fetcher.py` | `fetch_pubmed()` |
| `archive_org` URLs | Internet Archive `/metadata/` → text sidecar | `fetch_archive()` |
| Generic HTML | BeautifulSoup, prefer `<article>` or `<main>` | `fetch_html()` |

All results cached to `data/raw/<sha256(url)>.txt`. Deterministic re-runs.

### 2. Chunker (`realms/ingestion/chunker.py`)

- Max chunk size: ~3500 chars (~800-900 tokens)
- Min chunk size: 200 chars
- Boundary-aware: preserves paragraph breaks
- Tracks Wikipedia `== Section ==` headings and attaches to chunks
- Over-size paragraphs split on sentence boundaries

### 3. Extractor (`realms/ingestion/extractor.py`)

LLM-based entity extraction backed by OpenRouter.

**Model chain:**
1. Primary: `REALMS_EXTRACTION_MODEL` (default: `openai/gpt-oss-120b:free`)
2. Fallback chain: 5 free-tier models (gemma-4, nemotron, etc.)
3. Per-model retry: 3 attempts with exponential backoff
4. Daily quota detection: skips model entirely on `per-day` 429

**Prompt v5 output fields:**

| Category | Fields |
|----------|--------|
| Identity | name, entity_type, alignment, realm |
| Description | description (2-3 sentences) |
| Classification | powers[], domains[], alternate_names{} |
| Associations | cultural_associations[], geographical_associations[] |
| Roles | parents[], children[], consorts[], siblings[], teachers[], students[], servants[], enemies[], allies[], manifestations[], aspect_of, syncretized_with, created_by |
| Temporal | first_attested_year, evidence_period_start/end, historical_notes |
| Confidence | confidence (0-1, calibrated table) |

**Enum normalization:** Entity type, alignment, and realm are canonicalized via alias maps. Unknown values dropped to `None` to prevent garbage persist.

### 4. Normalizer (`realms/ingestion/normalizer.py`)

- **Exact match:** case-insensitive name lookup (covers ~99%)
- **Trigram fuzzy:** pg_trgm `similarity()` + `SET pg_trgm.similarity_threshold = 0.55`
- **Stem key:** diacritic-strip + plural-tolerant matching
- **Merge strategy:** accumulate lists, keep earliest temporal, recompute consensus confidence as mean of all extraction confidences

### 5. Relationship Engine (`realms/ingestion/relationships.py`)

Two edge creation mechanisms:

| Mechanism | Strength | How |
|-----------|----------|-----|
| Co-occurrence | weak (0.5) | Every pair in same chunk → `co_occurs_with` |
| Role claims | strong (0.85) | 14 role fields → typed edges, stubs for unknowns |

Role edges upgrade existing `co_occurs_with` edges if present.

### 6. Pair Classifier (`realms/ingestion/pair_classifier.py`)

Secondary pass: for existing `co_occurs_with` edges, a separate OpenRouter Gemini Flash call reads the shared chunk text and classifies into the same 14 relationship types. Runs at ~$0.22/M tokens.

### 7. Dimension Promoter (`realms/ingestion/promote_dimensions.py`)

Idempotent: backfills `cultures` and `geographic_regions` tables from entity JSONB arrays. Called after every ingestion pass.

### 8. Integrity Gate (`realms/ingestion/integrity_gate.py`)

Two-stage per-extraction verification:

| Stage | Check | Cost |
|-------|-------|------|
| 1 — Quote presence | Is the claim's quote text actually found in the source chunk? | $0 (string match) |
| 2 — Semantic verify | LLM (Gemini Flash) judges if the claim is supported by the quote | ~$0.001/claim |

**Action matrix:**

| Score | Action |
|-------|--------|
| ≥0.85 | ACCEPT — extraction stored normally |
| 0.65–0.85 | FLAG — stored but flagged for review |
| <0.65 | REJECT — extraction discarded |

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `REALMS_INGESTOR_POLL_INTERVAL` | 20 | Seconds between DB polls |
| `REALMS_INGESTOR_IDLE_SLEEP` | 60 | Sleep when queue empty |
| `REALMS_INGESTOR_MAX_CHUNKS` | 8 | Max chunks per source |
| `REALMS_INGESTOR_CHUNK_CONCURRENCY` | 1 | Parallel extraction threads |
| `REALMS_EXTRACTION_MODEL` | `openai/gpt-oss-120b:free` | Primary extraction model |
| `REALMS_EXTRACTION_FALLBACK_MODELS` | gemma-4, nemotron, etc. | Fallback chain |
| `REALMS_INTEGRITY_GATE` | `on` | Enable integrity gate |
| `REALMS_INTEGRITY_ACCEPT` | 0.85 | Accept threshold |
| `REALMS_INTEGRITY_FLAG` | 0.65 | Flag threshold |

## Orphan Recovery

On startup, any source stuck in `processing` > 30 minutes is reset to `pending`. This prevents crash-induced dead rows.

## Monitoring

Key metrics exposed via `GET /metrics/ingestion`:
- Queue depth (pending sources count)
- Throughput (sources completed per hour)
- Error rate (failed / total)
- Model usage distribution
