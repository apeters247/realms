# REALMS Frontend

## Architecture

The frontend is built with **Astro 5** (static site generation) + **Svelte 5** (interactive islands) + **Tailwind CSS 4**.

**Build output:** `web-next/dist/` — served by FastAPI at `/app/`  
**Legacy UI:** `web/` — served at `/app-legacy/` (D3 + Leaflet, original prototype)

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| **Static generation** | Performance, CDN-cacheable, no server-side rendering overhead |
| **Astro** | Native SSG, island architecture, excellent Markdown/MDX support |
| **Svelte 5** | Minimal runtime, runes API, great for interactive visualizations |
| **Tailwind 4** | Utility-first, CSS-first config, small bundle |
| **Dual build-time + runtime data** | Snapshot for static pages, fresh API calls in browser for interactive islands |

## Directory Structure

```
web-next/src/
├── lib/           # Shared TypeScript modules
│   ├── api.ts     # Typed fetch wrapper with retry + pagination
│   ├── types.ts   # EntitySummary, EntityDetail, RelationshipRef, etc.
│   ├── loader.ts  # Build-time data snapshot loader
│   ├── slug.ts    # Slug generation utilities
│   ├── url.ts     # URL helpers
│   └── jsonld.ts  # Schema.org JSON-LD generator
├── components/    # Astro components (11 files)
│   ├── Nav.astro / Footer.astro / Breadcrumb.astro
│   ├── EntityCard.astro / ConfidenceRibbon.astro / CoverageBar.astro
│   ├── SourceList.astro / SourceChip.astro / QuoteBlock.astro
│   ├── Sidenote.astro / Sparkline.astro
├── islands/       # Svelte 5 interactive islands (18 files)
│   ├── SearchBox.svelte / CommandPalette.svelte
│   ├── EntityGraph.svelte / FullGraph.svelte (Cytoscape.js)
│   ├── MapView.svelte (Leaflet)
│   ├── TimelineView.svelte (D3)
│   ├── BrowseList.svelte / HoverPreview.svelte
│   ├── CiteModal.svelte / FeedbackForm.svelte
│   ├── SwipeNav.svelte / ThemeToggle.svelte / ResearcherToggle.svelte
│   ├── IntegrityBadge.svelte
│   └── researcher/
│       ├── ResearcherDashboard.svelte
│       ├── ExternalLinking.svelte
│       ├── ReviewActions.svelte
│       └── AuditLog.svelte
├── layouts/
│   └── Base.astro  # Master layout: SEO, OG, theme boot, nav, footer
├── pages/          # 26 routes
│   ├── index.astro           # Home page
│   ├── browse.astro          # Entity browse/list
│   ├── search.astro          # Search interface
│   ├── graph.astro           # Full knowledge graph
│   ├── map.astro             # Geographic map
│   ├── timeline.astro        # Temporal view
│   ├── entity/[slug].astro   # Entity detail page
│   ├── tradition/[slug].astro# Culture/tradition page
│   ├── region/[slug].astro   # Geographic region page
│   ├── source/[id].astro     # Source detail page
│   ├── collection/[slug].astro
│   ├── collections.astro
│   ├── changelog.astro
│   ├── sources.astro
│   ├── api-docs.astro
│   └── about/                # Static pages
│       ├── about.astro
│       ├── methodology.astro
│       ├── ethics.astro
│       └── cite.astro
│   ├── researcher/           # Token-gated tools
│   │   ├── index.astro
│   │   ├── review.astro
│   │   ├── actions.astro
│   │   └── link.astro
│   ├── feed.xml.ts           # RSS feed
│   └── search-index.json.ts  # Client-side Fuse.js search index
├── styles/
│   ├── base.css    # Design tokens, typography (Fraunces serif)
│   └── layout.css  # Grid, sidenotes, responsive layout
└── fonts/          # @fontsource self-hosted fonts
```

## Data Flow

### Build Time (SSG)

```
astro build
  │
  ├── loadSnapshot() → API fetches /entities + /entity-classes + /cultures + /regions
  │                    → populates entityBySlug map for static path generation
  │
  ├── For each entity/[slug].astro:
  │     ├── loadEntityDetail(id) → /entities/{id} (full detail)
  │     ├── loadCorroboration(id) → /corroboration/{id} (tier badges)
  │     └── Pre-render HTML + JSON-LD + OG image URL
  │
  └── For each /search-index.json.ts:
        └── apiAll(/entities) → Fuse.js index
```

### Runtime (Browser)

```
Page load
  │
  ├── Static HTML displayed immediately (from SSG)
  │
  └── Interactive islands hydrate:
        ├── EntityGraph → GET /graph/ego/{id} (fresh Cytoscape data)
        ├── MapView → GET /regions/ + GeoJSON data
        ├── SearchBox → client-side Fuse.js on prebuilt index
        └── HoverPreview → GET /entities/{preview_id} on hover
```

## Key Pages

### Entity Page (`/entity/{slug}/`)

The atomic unit of the app. Tufte × Obsidian design:

```
┌──────────────────────────────────────┬─────────────────┐
│  Breadcrumb                          │  Sidenotes      │
│                                      │                 │
│  # Entity Name          [Confidence] │  Alternate names│
│  Entity Type · Realm · Culture       │  Traditions     │
│                                      │  Regions        │
│  ─────────────────────────────────── │  External IDs   │
│                                      │  Corroboration  │
│  Description (drop cap)              │                 │
│                                      │                 │
│  ## Temporal                         │                 │
│  First attested: 1500 BCE            │                 │
│  Evidence period: 1500 BCE–500 CE    │                 │
│                                      │                 │
│  ## Relationships                    │                 │
│  [EntityGraph Svelte island]         │                 │
│  Parent of: Oshun, Oya              │                 │
│  Allied with: Chango, Yemaya         │                 │
│                                      │                 │
│  ## Sources                          │                 │
│  [SourceList grouped by type]        │                 │
│                                      │                 │
│  [CiteModal] [FeedbackForm]          │                 │
│                                      │                 │
│  ← Prev        Next →               │                 │
└──────────────────────────────────────┴─────────────────┘
```

### Browse Page (`/browse/`)

Filterable entity list with facets. Svelte `BrowseList` island handles client-side filtering, sorting, infinite scroll.

### Graph Page (`/graph/`)

Full-screen Cytoscape.js knowledge graph. `FullGraph` Svelte island with:
- Force-directed layout
- Culture/type/realm color coding
- Click → detail, drag → explore
- Filter by relationship type

## Researcher Mode

Token-gated UI for curators. Activated by `REALMS_REVIEW_TOKEN` environment variable. Pages under `/researcher/`:
- **Review** — approve/reject/edit entity extractions
- **External Linking** — review Wikidata/VIAF suggestions
- **Actions** — full audit log of previous review operations
- **Dashboard** — quality metrics, integrity scores

## Build

```bash
cd web-next
npm install       # one-time
npm run build     # outputs to web-next/dist/

# The build happens in Docker via multi-stage Dockerfile
# Stage 1: node:22-slim → npm ci && npm run build
# Stage 2: python runtime, copies web-next/dist/ → /app/web-next/dist/
```

## Astro Config Highlights

```js
output: 'static'
base: '/app'
trailingSlash: 'always'
prefetch: { defaultStrategy: 'viewport' }
experimental: { clientPrerender: true }
```

## Client-Side Libraries

| Library | Version | Used For |
|---------|---------|----------|
| Cytoscape.js | ^3.32 | Knowledge graph visualization |
| D3.js | ^7.9 | Timeline, hierarchy charts |
| Leaflet | ^1.9 | Geographic map |
| Fuse.js | ^7.1 | Client-side fuzzy search |
| Fraunces (font) | variable | Serif headings |
| Inter Tight (font) | variable | Sans-serif UI |
| JetBrains Mono (font) | variable | Code blocks |
