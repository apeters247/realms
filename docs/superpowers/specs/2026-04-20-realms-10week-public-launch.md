# REALMS — 10-Week Public Launch Sprint

**Date:** 2026-04-20
**Status:** Approved, implementation starting
**Prior specs:** `2026-04-19-realms-phases-3-6-design.md`, `2026-04-20-realms-ui-redesign.md`
**Audience:** Reddit research communities (r/folklore, r/mythology, r/AskReligiousStudies, r/AskAnthropology, r/classics) + search-engine discovery

---

## Goal

Take REALMS from its current state (489 entities, Phase 7 UI shipped, 0 entities with temporal data, unwieldy graphs) to a **public-launched encyclopedic knowledge base of 2,000–3,000 entities** at **99% relationship & provenance integrity**, hosted at a parameterized public domain, with polished UX, research-grade export tools, and SEO-hardened entity pages ready for Reddit discussion and search-engine indexing.

## Non-goals

- User accounts, logins, paywalls, ads, analytics beyond privacy-first counts.
- Tier 3 entheogenic visionary material (McKenna machine-elves, DMT entities as spirits).
- Tier 4 modern occult / fiction / tulpamancy / UFO contactee material.
- Real-time collaboration, multiplayer editing.
- Multilingual UI chrome (content language is per-entity; UI stays English).
- Custom domain hardcoding — domain is parameterized via `REALMS_PUBLIC_ORIGIN`.

## Guiding principles

1. **Integrity before growth.** The system does not scale to 2,500 entities until verification has been proven ≥99% on the current 489-entity corpus.
2. **Automation-first, human-in-the-loop-rarely.** Curator spends 1–3 hrs/week. Plan uses multi-LLM verification + sampling audits, not manual review.
3. **Public-readable, not editable.** No accounts, no tracking cookies, no JS required for content. "Report an error" is the only contribution path.
4. **Every URL is permanent, citable, crawlable.** Canonical URLs, stable entity IDs, Schema.org JSON-LD, RSS feed, sitemap.
5. **Ship data under CC-BY-4.0.** Full dump downloadable; GitHub repo public.
6. **Respectful of living traditions.** Dedicated ethics page, explicit acknowledgement of indigenous knowledge primacy, no monetization of sacred material.

---

## Work-streams (parallel throughout the sprint)

### Stream I — Integrity pipeline (25% of engineering)

**Outcome:** Every typed relationship and every entity field is provably grounded in a verbatim source quote, with error rate measured nightly and held at ≤1%.

**Architecture:**

```
              ┌─── extractor v4 ──────┐
              │  emits (claim, quote) │
              └───────────┬───────────┘
                          │
              ┌───────────▼───────────┐
              │ Stage 1: exact-match  │  does quote.normalize() appear
              │ deterministic verify  │  in the source chunk?
              └───────────┬───────────┘
                          │
              ┌───────────▼───────────┐
              │ Stage 2: semantic     │  Gemini 2.0 Flash reads
              │ verify (cheap LLM)    │  {quote, claim} → {supports, ambiguous, contradicts} + conf
              └───────────┬───────────┘
                          │
              ┌───────────▼───────────┐
              │ Stage 3: gate         │  integrity ≥0.99 → accept
              │                       │  0.90–0.99   → flag for review queue
              │                       │  <0.90       → reject, requeue
              └───────────┬───────────┘
                          │
              ┌───────────▼───────────┐
              │ Stage 4: oracle       │  nightly: 20-row random sample
              │ sampling (Opus)       │  → Claude Opus ground-truth pass
              │                       │  → error-rate dashboard
              └───────────────────────┘
```

**Components to build:**

| Component | File | What it does |
|-----------|------|--------------|
| Extractor v4 prompt | `prompts/extractor_v4.md` | Emits `{claim, verbatim_quote, char_start, char_end}` tuples per relationship & field, plus explicit temporal fields (`first_attested_year`, `evidence_period_start`, `evidence_period_end`, `era_confidence`) |
| Exact-match verifier | `realms/ingestion/verify_quote.py` | Normalises diacritics/whitespace, fuzzy-matches quote against cached source chunk. Rejects if quote not present. |
| Semantic verifier | `realms/ingestion/verify_claim.py` | Single-shot Gemini 2.0 Flash call: "Does this quote support this claim?" → `{supports, ambiguous, contradicts, confidence}`. |
| Integrity gate | `realms/ingestion/integrity_gate.py` | Per-entity + per-batch. Saves `integrity_score` to `ingested_entity.integrity_meta` JSONB. |
| Oracle sampler | `scripts/run_integrity_oracle.py` | Nightly cron. Random 20-row sample from past-24h ingestions. Calls Claude Opus. Writes to `integrity_audits` table. |
| Dashboard | `realms/api/routes/integrity.py` + `/methodology` page | Public endpoint `GET /integrity/stats` shows current integrity score, 30-day rolling error rate. Methodology page embeds this. |

**New tables:**
```sql
CREATE TABLE integrity_audits (
  id SERIAL PRIMARY KEY,
  audited_at TIMESTAMPTZ DEFAULT NOW(),
  sample_size INT NOT NULL,
  n_supported INT NOT NULL,
  n_ambiguous INT NOT NULL,
  n_contradicted INT NOT NULL,
  oracle_model TEXT NOT NULL,
  error_rate NUMERIC(5,4) GENERATED ALWAYS AS (n_contradicted::numeric / sample_size) STORED,
  sample_ids INT[] NOT NULL,
  notes TEXT
);

-- additive JSONB field
ALTER TABLE ingested_entities ADD COLUMN integrity_meta JSONB;
-- shape: { "fields": [{name, quote, verifier_status, verifier_conf}], "integrity_score": 0.98 }
```

**Success criterion:** 30-day rolling `error_rate` ≤ 0.01, measured by the oracle sampler.

---

### Stream D — Data scale-out (25%)

**Outcome:** 2,000–3,000 entities across Tier 1 + Tier 2 scope. Every entity has ≥1 source, ≥80% have ≥2 sources (corroboration tier_2 or higher).

**Source seeding strategy:**

Wikipedia has well-curated category trees for our scope. Seed sources programmatically from these categories:

| Category root | Expected entities |
|----------------|---------|
| `Category:Deities by culture` (subtree) | ~800 |
| `Category:Legendary creatures by region` | ~400 |
| `Category:Folk saints` | ~80 |
| `Category:Ancestor veneration` | ~60 |
| `Category:Nature spirits` | ~150 |
| `Category:Household deities` | ~80 |
| `Category:Psychopomps` | ~40 |
| `Category:Oracles` | ~60 |
| `Category:Shamans` (only culturally-grounded entries) | ~40 |
| Per-tradition category pages (Yoruba, Hindu, Norse, …) | ~400 fill-in |
| **Total after dedup** | **~2,100** |

**Script:** `scripts/seed_from_wikipedia_category.py`
- Walks category tree (depth ≤ 3), filters by namespace=0 (articles only).
- Tier-3/4 blocklist: hard-coded category filter removes `Category:New religious movements`, `Category:Fictional characters`, `Category:Ceremonial magic`, `Category:Chaos magic`, `Category:UFO religions`, etc.
- Inserts `IngestionSource` rows with status=pending, source_type='wikipedia'.

**Tier 3/4 purge:**
- One-shot script `scripts/purge_out_of_scope.py` deletes entities whose:
  - Only source is in a blocked category (e.g., `dmt-experiences` tradition)
  - Cultural_associations contain only modern psychonaut/occult tags
- Generates audit report: list of deleted entity IDs + reason.
- User reviews the audit report before commit.

**Throughput plan:**
- Ingestor already does ~6 entities/hour sustained.
- 2,500 entities × 1.2 re-ingest factor = ~3,000 ingestion tasks.
- At 6/hour = 500 hours = 21 days wall-clock with 1 worker.
- **Option:** spin up a second ingestor instance during weeks 3–5 → 10 days.

**Budget estimate:** Claude Sonnet 4.6 extraction ~$0.06/entity × 3,000 = $180. Gemini Flash verification ~$0.01/entity × 3,000 = $30. Opus oracle sampling (20/day × 70 days × $0.15) ≈ $210. **Total: ~$420.**

---

### Stream U — Polish & UX (20%)

**Outcome:** UI feels crafted, not generated. Graphs are legible at scale. Timeline shows data. Mobile works. Performance hits Lighthouse ≥95 on LCP/FID/CLS.

**Known defects to fix:**

| Area | Current pain | Target |
|------|--------------|--------|
| **/graph** | 980 edges rendered by default, pile-up in center | Default filter: typed edges only (hide co_occurs_with). Cluster by tradition. Node size ~ corroboration tier. Minimap. Search + focus. URL state. |
| **/timeline** | 0 dated entities | Populated by v4 extraction. Century-bucket view, zoom to decade. Per-tradition lanes. Uncertainty bars for approximate years. |
| **/map** | Flat marker dump | Cluster markers. Heatmap overlay toggle. Region lasso. |
| **/search** | Trigram only | Facets (type, alignment, realm, culture, region, tier). Weighted ranking. Autocomplete. |
| **/browse** | Alphabetical only | Multi-mode: by type, alignment, tradition, era. Stateful filter URL. |
| **/** (home) | Placeholder tiles | Featured tradition of the week (auto-rotating from structured data). 3–6 curated collection teaser cards. "Recently ingested" strip. Integrity badge (99% live). |
| **entity page** | Missing thumbnail, no "cite this" | Wikimedia Commons thumbnail when licensed CC. "Cite this" modal. Related entities sidebar. |
| **mobile** | Works but cramped | Touch targets ≥44×44px, swipe gestures between entity pages, adaptive sidenote column. |

**New pages:**
- `/collections` — index of curated collections
- `/collection/[slug]` — e.g. `solar-deities`, `forest-spirits`, `death-psychopomps`, `trickster-gods`, `household-spirits`, `ancestor-classes`. Auto-generated from tags + editorial rules; you review & approve titles only (spot-check).
- `/era/[century]` — e.g. `/era/-10c` (10th century BCE). Group entities by first-attested century bucket.

**Performance budget** (enforced per-build):
- Home LCP ≤ 1.2s, JS ≤ 5KB before interaction
- Entity page LCP ≤ 1.5s, JS ≤ 10KB (HoverPreview)
- Graph page JS ≤ 300KB gzipped (Cytoscape is the whale — that's OK for an interactive graph page)
- CLS = 0 on all pages

---

### Stream R — Research tools (15%)

**Outcome:** Researchers can cite, export, and programmatically consume the data without friction.

**Features:**

| Feature | Endpoint / UI | Format |
|---------|---------------|--------|
| Cite this entity | Modal on entity page | APA / MLA / Chicago / BibTeX / CSL-JSON |
| Export single entity | `GET /export/entity/{id}.{fmt}` | json / csv / bibtex / csl.json / graphml |
| Export collection | `GET /export/collection/{slug}.{fmt}` | csv / json |
| Export full dataset | `GET /export/dataset.zip` (nightly regenerated) | CSV + JSON + GraphML + README |
| Entity permalink | `/entity/{slug}` + `/e/{id}` short form | HTML + `Link: <…>; rel="canonical"` |
| Public API docs | `/api-docs` | Swagger-UI (already via FastAPI `/docs`) + human-readable quickstart |
| Changelog feed | `/changelog` (HTML) + `/changelog.rss` | Weekly "what changed" auto-generated from git + DB diffs |

**Error reporting:**
- `POST /feedback` (rate-limited, captcha-less, hashes reporter IP for dupe detection).
- Body: `{ entity_id, field, issue_type, message, reporter_email (optional) }`.
- Writes to `feedback_reports` table; surfaces in `/researcher/feedback` (token-gated).

---

### Stream S — SEO & trust (10%)

**Outcome:** Google indexes every entity page; social previews look sharp; methodology is transparent enough that skeptical reviewers can verify claims.

**Deliverables:**

- **Per-entity OG images** — PNG, 1200×630, Fraunces title + tradition + cream paper. Generated at build via `@resvg/resvg-js`. Currently only a default SVG exists.
- **Schema.org** validated via `schema-dts` types and `google-structured-data-testing-tool` in CI.
- **Internal linking density** — every entity links to tradition, region, source, related entities (already implemented — audit for density).
- **Canonical URLs** — already correct; verify.
- **Methodology page** — expanded to cover:
  - How entities are extracted (v4 pipeline diagram)
  - What "integrity score" means (with live 30-day dashboard)
  - How to cite REALMS (suggested BibTeX + DOI once obtained)
  - Acknowledgement of source traditions; primacy of living practitioners
  - CC-BY-4.0 licence + dataset download link
- **Ethics page** (`/about/ethics`) — dedicated page on indigenous knowledge, misappropriation risks, why REALMS doesn't reproduce ritual instructions, how to respectfully engage.
- **Accessibility** — WCAG 2.1 AA. pa11y in CI, zero errors on home/browse/entity/tradition/graph. Skip-to-content, focus rings, keyboard navigation for command palette + graph.
- **robots.txt / sitemap.xml** — already done; validate.
- **Launch day:** submit sitemap to Google Search Console, Bing Webmaster, verify `Google-Extended` allow.

---

### Stream L — Launch ops (5%)

**Outcome:** Site reachable at production domain, TLS, CDN, rate-limited, monitored.

**Deliverables:**

- Domain wiring via single env var `REALMS_PUBLIC_ORIGIN` (everything already reads this).
- TLS: via Cloudflare proxy (orange-cloud) OR Let's Encrypt on nginx — user's choice at week 9.
- CDN: Cloudflare free tier is plenty; caches everything under `/app/*`.
- Rate limits: existing slowapi limiter; bump to 100 req/min/IP on public routes, 20 req/min on expensive endpoints (`/graph`, `/search/advanced`, `/export/*`).
- WAF: Cloudflare's default managed rules + a custom rule that challenges requests missing a `Accept-Language` header (simple bot filter).
- Monitoring: existing infra monitor cron is fine; add uptime check via UptimeRobot free.
- Launch posts: drafted in `docs/launch/reddit_posts.md` per-subreddit, user reviews before posting.

---

## Week-by-week plan

Each week has a **primary** and **secondary** stream. Verification that the week "landed" = named success metric measurable in code/output.

| Wk | Primary | Secondary | Key deliverables | Success metric |
|----|---------|-----------|------------------|----------------|
| **1** | I | U | Extractor v4 prompt + verifier stub + integrity gate skeleton; graph default-filter fix | `POST /integrity/test` returns per-claim verdicts; graph shows ≤200 edges by default |
| **2** | I | S | Oracle sampler cron + dashboard endpoint; methodology page v2; OG PNG generator | `/integrity/stats` returns real error rate; OG PNG renders for any entity slug |
| **3** | D | U | Wikipedia category seeder; Tier 3/4 purge script + audit; timeline page populated with first 100 v4-extracted entities | ≥500 new `ingestion_sources` pending; ≥100 entities with `first_attested_year` |
| **4** | D | R | Second ingestor instance; `/export/entity/*` + citation modal; `/collections` index | 800+ entities total; BibTeX export validates |
| **5** | U | D | Graph clustering + minimap; search facets; `/map` clustering; continuing ingestion | Graph at 1500-edge corpus renders in <2s; search facet query returns in <100ms |
| **6** | D | R | Reach 2,000 entities; changelog feed; API docs page; error-reporting form | Entity count ≥2,000; `/changelog.rss` valid RSS 2.0 |
| **7** | S | U | a11y audit (WCAG 2.1 AA); Schema.org validation in CI; ethics page | pa11y passes on 10 sample pages; ethics page peer-reviewed by external reader |
| **8** | U | R | Collections auto-generator (solar deities, forest spirits, psychopomps, etc.); citation tests; permalinks | ≥8 live collections; Cite-this modal works in 5 formats |
| **9** | L | S | Domain wiring + TLS + CDN staging; load test; Reddit-post drafts; submit to Search Console | Staging site returns TLS cert; loadtest at 200 concurrent users holds <2s p95 |
| **10** | L | — | Go live; launch Reddit posts Monday-Wednesday across 3–4 subs; monitor feedback; triage bugs | Public URL loads; first 48h traffic captured; ≤5 critical bugs at end of week |

### Ingestion runs continuously in background from week 3 onwards.

---

## Definition of done for integrity

"99% integrity" is operationalised as:

- **Per-claim:** `verifier_status in {supported, ambiguous}` with `verifier_conf ≥ 0.85`, AND the quote exists exactly in the source chunk.
- **Per-entity:** at least 99% of claims on the entity pass per-claim criterion.
- **Corpus-level:** over 30-day rolling oracle sample, `n_contradicted / sample_size ≤ 0.01`.

**If corpus error rate exceeds 0.01 for 3 consecutive days:**
1. Halt ingestion.
2. Raise alert in `/integrity/stats` dashboard.
3. User reviews the contradicted claims, updates extractor prompt or verifier thresholds.
4. Resume.

---

## Out of scope (explicit)

- Multilingual UI
- User accounts / edit proposals on-platform
- Live WebSocket graph
- Offline PWA
- Tier 3 entheogenic / Tier 4 modern occult entities
- Commercial licensing (CC-BY-4.0 covers it)
- Print book / PDF export (maybe later)
- ML-based entity disambiguation beyond fuzzy trigram (current good-enough)
- Custom on-disk graph database (Neo4j mirror is enough)

## Open questions (resolve during sprint)

1. Domain (user picks week 9, no hardcode until then).
2. Whether to use Cloudflare or self-hosted nginx TLS (user picks week 9).
3. DOI — apply for Zenodo DOI once dataset is stable (post-launch).
4. Analytics — user preference between no-analytics and Plausible self-hosted (post-launch).

---

## Success metrics at week 10

- Public URL reachable via TLS, CDN cached, robots.txt + sitemap live.
- **Entity count:** 2,000–3,000.
- **Integrity:** corpus error rate ≤ 0.01, last 30 days of oracle samples.
- **Temporal coverage:** ≥60% of entities have `first_attested_year` (century-level OK).
- **Corroboration:** ≥50% of entities tier_2 or tier_3 (≥2 distinct source types).
- **Performance:** home + entity page Lighthouse ≥95 on LCP/FID/CLS.
- **Accessibility:** pa11y passes with zero errors on top-10 sample pages.
- **SEO:** sitemap submitted, 0 validation errors on Google Rich Results Test for entity page.
- **Launched:** 3–4 Reddit posts live, GitHub repo public, CC-BY-4.0 dataset dump downloadable.

---

## Appendix: Ingestion cost model

| Item | Unit | Rate | Qty | Cost |
|------|------|------|-----|------|
| Claude Sonnet 4.6 extraction | per entity | $0.06 | 3,000 | $180 |
| Gemini 2.0 Flash verification | per claim | $0.001 | ~30,000 | $30 |
| Claude Opus oracle sampling | per sample | $0.15 | 1,400 (20/day × 70 days) | $210 |
| Total | | | | **~$420** |

Plus existing ongoing Wikipedia fetch (free), archive.org fetch (free), PubMed fetch (free).
