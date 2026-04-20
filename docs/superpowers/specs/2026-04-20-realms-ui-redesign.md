# REALMS UI Redesign — Tufte × Obsidian × Palladio

**Date:** 2026-04-20
**Status:** Approved; in implementation
**Supersedes:** current vanilla-JS SPA in `web/`
**Lives at:** `web-next/` (new) → built to `web-next/dist/` → served by FastAPI at `/app/`

---

## Goals

1. **Defensible** — every visible claim traces to a source. No AI-slop.
2. **Indexable** — each entity is a pre-rendered HTML page with Schema.org structured data, linkable, citable, crawlable.
3. **Two modes** — public-first discovery (default); researcher mode (token-gated) unlocks review, bulk ops, raw data.
4. **Typographically-correct** — Tufte as visual guide: paper background, serif body, sidenotes, small multiples, red accents sparingly.

## Non-goals

- Real-time collaboration — not a multiplayer tool.
- WYSIWYG editing — edits happen through the review API only.
- Offline/PWA.
- Internationalization of UI chrome — content-language is per entity; UI is English for now.

---

## Visual language (approved 2026-04-20)

See section in conversation log; consolidated here:

- **Type:** Fraunces (body+display), Inter Tight (UI), JetBrains Mono (IDs).
- **Scale:** `0.75, 0.875, 1, 1.25, 1.5, 2, 3` rem. Prose `max-width: 64ch`. Line-height 1.55.
- **Color:** cream paper `#faf9f6` / warm ink `#1a1815` / oxblood accent `#7a1f13` / academic blue `#1b4b6b`. Dark mode is *not* inversion — `#13110e` bg, `#e8e3d8` ink, `#d04a2a` accent.
- **Layout:** 8pt baseline. Sidenote column 200px on ≥1280px screens, collapses to `<details>` below.
- **Motion:** View Transitions API cross-page; `cubic-bezier(0.4,0,0.2,1)` 180–240ms; reduce-motion honored.
- **Icons:** Phosphor Regular 16px.

---

## Information architecture

Every URL is a canonical, crawlable, citable page. No `#hash` routing.

```
/                               Home — curated tradition tiles, recent additions,
                                corroboration stats
/browse                         Paginated entity index with facet rail
/entity/<slug>                  Entity atomic page (SSG)
/tradition/<slug>               Culture page — member entities, summary, map
/region/<slug>                  Geographic page — member entities, boundary map
/graph                          Full-graph explorer (client-rendered)
/timeline                       Timeline explorer (client-rendered)
/map                            Global map (client-rendered)
/search?q=…                     Search results (SSR fallback + client enrichment)
/sources                        Source catalogue (by source_type)
/source/<id>                    Individual source page — entities extracted from it
/about                          Methodology, data model, citation guide
/researcher                     Researcher dashboard (token-gated)
/researcher/review              Review queue
/researcher/actions             Audit log
/researcher/link                External-ID linking dashboard
```

Slug rule: `name` → lower, strip diacritics, `[^a-z0-9]` → `-`, collapse dashes, trim. Collisions get `-2`, `-3` suffixes (stable sort by entity id).

Navigation chrome (persistent, subtle, top-of-page):

```
REALMS    Browse  Graph  Timeline  Map  Sources        ⌘K    🌗   ≡
                                                       search mode menu
```

The hamburger opens a sheet with About, Methodology, Researcher login, and a light/dark picker.

---

## Entity page — the atomic unit

The entity page is the most important surface in the site. Every decision elsewhere is downstream of this.

### Layout (wide screen, ≥1280px)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ← Tradition: Yoruba                                                     │
│                                                                          │
│  ┌──────────────────────────────────────┐  ┌────────────────────────┐  │
│  │  Osun                                │  │  Also known as         │  │
│  │  Orisha • West Africa • tier_3       │  │    Oshun (English)     │  │
│  │                                       │  │    Ọ̀ṣun (Yoruba)        │  │
│  │  ──────────────                       │  │    Oxum (Portuguese)   │  │
│  │                                       │  │                         │  │
│  │  Osun is the Yoruba deity of          │  │  First attested        │  │
│  │  freshwater, fertility, love, and     │  │    ~800 CE             │  │
│  │  sensuality, one of the seven         │  │                         │  │
│  │  principal Orishas...                 │  │  Region                 │  │
│  │                                       │  │    Nigeria, Benin      │  │
│  │  She presides over the Osun River,    │  │                         │  │
│  │  whose waters are said to heal[¹].    │  │  Tradition              │  │
│  │                                       │  │    Yoruba, Santería,   │  │
│  │  [description continues...]           │  │    Candomblé            │  │
│  │                                       │  │                         │  │
│  │  ↻ synthesized from 3 sources         │  │  External              │  │
│  │                                       │  │    Wikidata Q234567    │  │
│  │                                       │  │    VIAF 12345          │  │
│  └──────────────────────────────────────┘  └────────────────────────┘  │
│                                                                          │
│  ┌── Relationships ────────────────────────────────────────────────────┐│
│  │                      Yemoja ─ mother of ─→                          ││
│  │                         ↓                                            ││
│  │           Oduduwa ←── consort ──   Osun   ──→ syncretized with      ││
│  │                         ↓                       Our Lady of Charity ││
│  │                      Shango                                          ││
│  │                                                                      ││
│  │  [mini Cytoscape graph, ego network depth=1, click to expand]       ││
│  └──────────────────────────────────────────────────────────────────────┘│
│                                                                          │
│  ┌── Sources ───────────────────────────────────────────────────────┐  │
│  │  [¹] Bastide, Les Religions africaines au Brésil (1960), p. 142.  │  │
│  │      Wikipedia · archive.org/details/bastide00…                    │  │
│  │      "L'eau de l'Osun guérit…" [full quote]                       │  │
│  │  [²] Murphy, Osun across the Waters (2001). PMID 11234567.         │  │
│  │  [³] archive.org/details/yorubamythsLEGEND.                        │  │
│  └─────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
```

### Layout (narrow, <1280px)

Sidenotes collapse into `<details><summary>` elements inline with prose. Relationships section becomes a horizontal scroll of chips. Sources always at bottom.

### Structural pieces

1. **Breadcrumb** (Astro component): tradition → entity name. `<nav>` with proper aria.
2. **Heading block** (`<header>`):
   - `<h1>` entity name (Fraunces Display 48px).
   - Below: sentence caps line: *`entity_type` · `region` · tier badge* in Inter Tight 14px, ink-dim.
   - Thin rule below.
3. **Prose column** (`<article>`):
   - Description rendered with `<p>` paragraphs.
   - Source chips `[¹]` are `<sup><a>` that deep-link to the Sources section. On hover, show a floating card (Svelte `HoverPreview` island) with the source title, year, and a snippet of the quote.
   - When the description is LLM-synthesized (we have multiple extractions merged), append `<p class="synthesis-tag">↻ synthesized from N sources</p>`. This is not hidden — it's a design feature.
4. **Sidenote column** (`<aside role="complementary">`) on wide screens: alternate names, first-attested year, evidence period, region, tradition, external links, source types present. All small-caps labels in Inter Tight, values in Fraunces.
5. **Relationships** — a titled section with a mini Cytoscape island (`<EntityGraph>`, `client:visible`). Depth = 1. Node click navigates; node hover invokes HoverPreview. A "View full subgraph →" link jumps to `/graph?center=<id>`.
6. **Sources** — numbered list. Each entry: authors, year, venue, DOI/URL, quote blockquote, source-type chip. Quotes come from `IngestedEntity.quote_context` via `/corroboration/<id>` endpoint.
7. **Backlinks** (Obsidian) — section below Sources: "Mentioned by N entities" with a linked list (entities whose relationships point here, or whose descriptions reference this one).

### Per-entity JSON-LD (embedded in `<head>`)

```jsonld
{
  "@context": "https://schema.org",
  "@type": ["Thing", "CreativeWork"],
  "@id": "https://realms.org/entity/osun",
  "name": "Osun",
  "alternateName": ["Oshun", "Ọ̀ṣun", "Oxum"],
  "description": "<first 280 chars of description>",
  "url": "https://realms.org/entity/osun",
  "sameAs": [
    "https://www.wikidata.org/wiki/Q234567",
    "https://viaf.org/viaf/12345"
  ],
  "identifier": [
    {"@type": "PropertyValue", "propertyID": "REALMS", "value": "42"},
    {"@type": "PropertyValue", "propertyID": "Wikidata", "value": "Q234567"}
  ],
  "citation": [
    {"@type": "CreativeWork", "name": "…", "author": "…", "datePublished": "1960", "url": "…"}
  ],
  "isPartOf": {
    "@type": "Dataset",
    "name": "REALMS — Research Entity Archive for Light & Metaphysical Spirit Hierarchies",
    "url": "https://realms.org/",
    "license": "CC-BY-4.0"
  }
}
```

OpenGraph + Twitter Cards on every page. `og:image` is auto-generated at build time (see SEO section).

---

## Global views (interactive islands)

### /graph

Full-graph Cytoscape view. Ported from current app.js `initGraphView` but:
- **Tufte-ified node styles** — thin 1px ink borders, no shadows, node label in Fraunces small caps.
- **Semantic-only toggle** — hide co-occurrence edges by default; keep only typed relationships.
- **Tradition coloring** — up to 12 traditions get distinct muted hues; overflow goes to `ink-faint`.
- **URL state** — `?center=<id>&depth=2&filter=semantic` reflected in query string (sharable).
- **Picker** — command palette aware (`⌘K` → "Focus on Yemoja" → center and pan).

### /timeline

D3 horizontal band chart from `/timeline/entities`. One row per tradition, ticks at century marks, entity spans drawn as thin horizontal bars (Tufte's quartet-style). Hovering a bar shows a tooltip with entity name + era.

### /map

Leaflet, minimal basemap (stamen toner-lite or similar muted tile set). Entities clustered by geographic_associations → `/cultures/<id>` lat/lng. Click a cluster → filtered list.

### Hover link-previews (Obsidian)

Any `<a data-preview="entity-id">` gets a hover preview after 300ms. Lightweight Svelte component; portals to `<body>`, absolutely positioned. Fetches `/entities/<id>` if not already in a build-time manifest; caches in memory.

### Command palette (⌘K / Ctrl-K)

Svelte island, lazy-loaded only on first keyboard trigger. Actions:
- Search entities by name (fuzzy, `fuse.js`) — goes to `/entity/<slug>`.
- Search traditions → `/tradition/<slug>`.
- Jump to views: Browse, Graph, Timeline, Map, Sources, About, Researcher.
- Toggle dark/light.
- Toggle researcher mode.
- Random entity ("surprise me").
- Copy current URL.

Visual: single input top-centered, paper-colored floating panel with ink text, same typography as pages. No icons in results — clean text only.

---

## Researcher mode

### Activation

Top-right icon (`<ResearcherToggle>` Svelte island) persists state in `localStorage.realms.researcher = true`. When activated, user is prompted for the review token (stored in `localStorage.realms.reviewToken`, same as current Phase 4 UI). The token field is a password input, cleared on 401/403.

### Unlocks (progressive disclosure)

When `researcher=true`:

1. **Entity page** gets:
   - Approve / Reject / Merge buttons in the header.
   - Field-level edit pencils next to every editable attribute (whitelisted).
   - Raw JSON viewer in a collapsible `<details>`.
   - Extraction details table (model, temperature, prompt version, confidence per extraction).
   - Review-actions audit log for this entity.
2. **Browse page** gets:
   - Extra columns: confidence, source type count, last reviewed.
   - Bulk-select with a floating action bar (approve N, reject N, link to Wikidata).
3. **/researcher dashboard** becomes visible:
   - Review queue (low-confidence / isolated / single-source).
   - Audit log (all `review_actions` rows, filterable).
   - External-link suggest queue (candidates proposed by `link_external_ids.py`, one-click accept).
   - Ingestion health: queue depth, throughput, error rates.

### Visual differentiation

Researcher mode adds a 2px oxblood accent stripe at the top of the viewport (`border-top: 2px var(--accent)`) so it's obvious you're not in public mode. No other chrome changes — same typography, same spacing.

---

## SEO / structured data / bot-friendliness

Since the user specifically called out "attractive to index bots and searchers looking for ground truth data":

### Per-page

- **Canonical URL** in `<link rel="canonical">`.
- **OpenGraph** + **Twitter card** on every page.
- **JSON-LD** structured data:
  - Entity pages → `Thing` / `CreativeWork` (see above).
  - Tradition pages → `Collection`.
  - Source pages → `ScholarlyArticle` or `Book`.
  - Home → `WebSite` with `SearchAction`.
- **Breadcrumbs** via `BreadcrumbList` JSON-LD.

### Site-wide

- **`robots.txt`** generously allowing all major crawlers, disallowing `/researcher/*`.
- **`sitemap.xml`** via `@astrojs/sitemap` — all entities, traditions, regions, source pages. Updated on rebuild.
- **RSS feed** at `/feed.xml` of newly-added entities (last 50) — helps indexing.
- **Automatically-generated OG images** per entity at `/og/<slug>.png` via `@resvg/resvg-js`. Layout: entity name in Fraunces on cream background, with region + tradition beneath. Cached.
- **HTTP headers** (FastAPI-side addition): `Link: <canonical>; rel="canonical"`, `Cache-Control: public, max-age=300, stale-while-revalidate=86400` on entity pages.

### "Ground truth" surface

A special **`/about/methodology`** page explains:
- How entities are extracted (LLM + human review).
- What a confidence score means.
- Corroboration tiers and how to read them.
- What the "↻ synthesized from N sources" tag means.
- How to cite REALMS in a scholarly paper (suggested BibTeX, DOI if obtained later).

Entity pages link "Why do we show this?" in the footer, which jumps to the relevant methodology section.

---

## Build & integration

### Directory layout

```
/var/www/realms/
├── web/              (legacy, kept as fallback at /app-legacy/)
├── web-next/         (new)
│   ├── astro.config.mjs
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── src/
│   │   ├── lib/
│   │   │   ├── api.ts              (typed fetch against realms-api)
│   │   │   ├── slug.ts
│   │   │   ├── jsonld.ts
│   │   │   └── types.ts            (mirrors API DTOs)
│   │   ├── layouts/
│   │   │   ├── Base.astro          (html+head, fonts, theme)
│   │   │   └── Article.astro       (Tufte two-column with sidenotes)
│   │   ├── components/
│   │   │   ├── Nav.astro
│   │   │   ├── Sidenote.astro
│   │   │   ├── ConfidenceRibbon.astro
│   │   │   ├── SourceChip.astro
│   │   │   ├── SourceList.astro
│   │   │   ├── QuoteBlock.astro
│   │   │   ├── Breadcrumb.astro
│   │   │   ├── EntityCard.astro
│   │   │   └── Footer.astro
│   │   ├── islands/                (Svelte)
│   │   │   ├── CommandPalette.svelte
│   │   │   ├── EntityGraph.svelte  (Cytoscape wrapper)
│   │   │   ├── HoverPreview.svelte
│   │   │   ├── SearchBox.svelte
│   │   │   ├── TimelineView.svelte
│   │   │   ├── MapView.svelte
│   │   │   ├── ThemeToggle.svelte
│   │   │   ├── ResearcherToggle.svelte
│   │   │   └── researcher/
│   │   │       ├── ReviewActions.svelte
│   │   │       ├── AuditLog.svelte
│   │   │       └── RawJsonViewer.svelte
│   │   ├── pages/
│   │   │   ├── index.astro
│   │   │   ├── browse.astro
│   │   │   ├── entity/[slug].astro
│   │   │   ├── tradition/[slug].astro
│   │   │   ├── region/[slug].astro
│   │   │   ├── source/[id].astro
│   │   │   ├── graph.astro
│   │   │   ├── timeline.astro
│   │   │   ├── map.astro
│   │   │   ├── search.astro
│   │   │   ├── sources.astro
│   │   │   ├── about.astro
│   │   │   ├── about/methodology.astro
│   │   │   └── researcher/
│   │   │       ├── index.astro
│   │   │       ├── review.astro
│   │   │       ├── actions.astro
│   │   │       └── link.astro
│   │   ├── styles/
│   │   │   ├── tokens.css       (CSS variables)
│   │   │   ├── typography.css
│   │   │   └── base.css
│   │   └── fonts/               (self-hosted variable fonts)
│   │       ├── Fraunces-VariableFont_SOFT,WONK,opsz,wght.woff2
│   │       ├── InterTight-Variable.woff2
│   │       └── JetBrainsMono-Variable.woff2
│   └── dist/                    (build output → served by FastAPI)
```

### Astro config

- `output: 'static'`
- `integrations: [svelte(), tailwind(), sitemap(), prefetch()]`
- `prefetch: { defaultStrategy: 'viewport' }`
- `compressHTML: true`

### Build-time data loading

A single `src/lib/loader.ts` fetches:
- all entities (`GET /entities/?per_page=500` until exhausted)
- all traditions (`GET /cultures/`)
- all regions (`GET /regions/`)
- all sources (`GET /sources/`)

Cached to `.astro-cache/realms-snapshot.json` during build. Each page's `getStaticPaths()` reads from this snapshot — one API fetch cycle per build.

Snapshot age is embedded in the page footer and in `<meta name="realms-snapshot-at">` so users and crawlers see when we last synced.

### FastAPI serves it

After `npm run build`, mount `/app` → `web-next/dist/` (preserving existing behaviour); legacy `web/` moves to `/app-legacy/`.

```python
# realms/api/main.py (addition)
WEB_DIR = Path(os.getenv("REALMS_WEB_DIR", "/app/web-next/dist"))
LEGACY_WEB_DIR = Path("/app/web")
...
if LEGACY_WEB_DIR.exists():
    app.mount("/app-legacy", StaticFiles(directory=str(LEGACY_WEB_DIR), html=True), name="web-legacy")
if WEB_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
```

### Dockerfile

Adds a node build stage:

```dockerfile
FROM node:22-slim AS web-build
WORKDIR /src
COPY web-next/package.json web-next/package-lock.json* ./
RUN npm ci
COPY web-next/ ./
# Point the loader at the in-build FastAPI via env
ARG REALMS_API_ORIGIN=http://realms-api:8001
ENV REALMS_API_ORIGIN=$REALMS_API_ORIGIN
RUN npm run build

FROM python:3.11-slim AS runtime
# … existing steps …
COPY --from=web-build /src/dist /app/web-next/dist
```

In dev, the builder pulls from the already-running `realms-api` container on the estimabio network. In CI, a one-off build runs against a seeded test DB.

---

## Accessibility

- Semantic HTML first (headings, landmarks, lists).
- Color contrast ≥ 4.5:1 for body text (palette chosen to hit this).
- `prefers-reduced-motion` disables View Transitions and hover previews.
- Focus rings: 2px oxblood offset, never removed.
- Skip-to-content link at top of body.
- `<dialog>` for Cmd-K with `showModal()` — focus trap + Esc dismiss for free.

## Performance budget

- Home page: ≤30KB CSS, ≤0KB JS (no islands).
- Entity page: ≤30KB CSS, ≤5KB JS (HoverPreview only until interaction).
- Graph page: ≤200KB JS total (Cytoscape is the whale).
- LCP on entity page < 1.2s from paper-cold cache.
- Zero layout shift (CLS = 0).

Enforce via `astro build --experimental-performance-budget` and Lighthouse CI gate in the Dockerfile's build step.

---

## Test plan

1. **Build** — `npm run build` succeeds, generates N+M+K pages where N = entities, M = traditions, K = regions.
2. **Accessibility** — pa11y on 10 sample pages, zero errors.
3. **Structured data** — `google-structured-data-testing-tool` (headless) on 5 entity pages, zero warnings.
4. **Visual regression** — screenshot the entity page in both modes, commit baseline.
5. **Integration** — existing pytest suite (99 tests) remains green. New Playwright smoke tests for:
   - `/entity/osun` renders name, sidenotes, sources.
   - Cmd-K opens, searches, navigates.
   - Researcher mode toggle persists and adds controls.
6. **SEO** — sitemap contains all entities; robots.txt disallows `/researcher`; JSON-LD validates.

---

## Out of scope (deferred)

- Multilingual UI chrome.
- Full-text search index (we use `/search` which is DB-backed).
- Offline PWA.
- User accounts / per-user preferences beyond localStorage.
- Self-hosted analytics (Plausible / Umami) — can be added via a single `<script>` later.

---

## Open questions for later

1. **Domain?** `realms.org` in examples; actual public domain TBD.
2. **Analytics vendor?** Plausible is my recommendation (privacy-first, lightweight).
3. **Search infra?** Current DB trigram search is fine for <1k entities. Revisit at 10k.
