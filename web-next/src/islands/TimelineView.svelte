<script lang="ts">
  import { onMount } from 'svelte';

  const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');
  const link = (p: string) => BASE + p;

  interface Bucket { year: number; count: number }
  interface Lane {
    tradition: string;
    start_year: number;
    end_year: number;
    n_entities: number;
    buckets: Bucket[];
  }
  interface Member {
    id: number;
    name: string;
    entity_type: string | null;
    alignment: string | null;
    first_documented_year: number | null;
    consensus_confidence: number;
  }

  let lanes = $state<Lane[]>([]);
  let window_info = $state<{ min_year: number; max_year: number; step: number; zoom: string } | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  let topN = $state(25);
  let zoom = $state<'millennium' | 'century' | 'decade'>('century');

  // Drill-in panel
  let panelOpen = $state(false);
  let panelTitle = $state<string>('');
  let panelTradition = $state<string>('');
  let panelRange = $state<{ start: number; end: number } | null>(null);
  let panelMembers = $state<Member[]>([]);
  let panelLoading = $state(false);

  // Color map — deterministic per-tradition hue, matches FullGraph
  const TRADITION_HUES = [
    '#7a1f13', '#1b4b6b', '#3f6b2e', '#8b5a2b', '#5d4b8b',
    '#b8860b', '#4a7c7d', '#7a3a5c', '#2e5d40', '#a54a1a',
    '#3a4a7c', '#6b4a2e',
  ];
  function hue(t: string): string {
    const h = Array.from(t).reduce((a, c) => (a * 31 + c.charCodeAt(0)) | 0, 0);
    return TRADITION_HUES[Math.abs(h) % TRADITION_HUES.length];
  }

  function yearLabel(y: number): string {
    if (y >= 0) return `${y} CE`;
    return `${Math.abs(y)} BCE`;
  }

  async function loadLanes() {
    loading = true;
    try {
      const r = await fetch(`/timeline/lanes?top_n=${topN}&zoom=${zoom}`);
      if (!r.ok) throw new Error(`${r.status}`);
      const payload = await r.json();
      lanes = payload.data.lanes;
      window_info = payload.data.window;
      error = null;
    } catch (e) {
      error = (e as Error).message;
    } finally {
      loading = false;
    }
  }

  onMount(loadLanes);

  // Convert year → x% in the window so lanes can CSS-position with percent.
  function xPct(y: number): number {
    if (!window_info) return 0;
    const span = window_info.max_year - window_info.min_year;
    if (span <= 0) return 0;
    return ((y - window_info.min_year) / span) * 100;
  }

  // Bucket density → opacity 0.18..1
  function densityOpacity(count: number, maxCount: number): number {
    if (maxCount <= 0) return 0.2;
    return 0.18 + Math.min(0.82, (count / maxCount) * 0.82);
  }

  async function openBucket(lane: Lane, startYear: number, endYear: number) {
    panelTradition = lane.tradition;
    panelRange = { start: startYear, end: endYear };
    panelTitle = `${lane.tradition} · ${yearLabel(startYear)} – ${yearLabel(endYear)}`;
    panelOpen = true;
    panelLoading = true;
    try {
      const r = await fetch(
        `/timeline/bucket_members?tradition=${encodeURIComponent(lane.tradition)}&start_year=${startYear}&end_year=${endYear}&limit=200`,
      );
      const payload = await r.json();
      panelMembers = payload.data.members || [];
    } catch {
      panelMembers = [];
    } finally {
      panelLoading = false;
    }
  }

  function closePanel() { panelOpen = false; }

  function slugify(name: string): string {
    return (name || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  }

  // Tick marks on the X-axis scale (e.g., every 500 years at century zoom)
  const tickStep = $derived.by(() => {
    if (!window_info) return 500;
    const span = window_info.max_year - window_info.min_year;
    if (span > 6000) return 1000;
    if (span > 2500) return 500;
    return 200;
  });

  const xTicks = $derived.by(() => {
    if (!window_info) return [];
    const t: number[] = [];
    const start = Math.ceil(window_info.min_year / tickStep) * tickStep;
    for (let y = start; y <= window_info.max_year; y += tickStep) t.push(y);
    return t;
  });
</script>

<section class="controls ui">
  <label>
    Traditions
    <select bind:value={topN} onchange={loadLanes}>
      <option value={10}>top 10</option>
      <option value={25}>top 25</option>
      <option value={50}>top 50</option>
      <option value={100}>top 100</option>
    </select>
  </label>
  <label>
    Zoom
    <select bind:value={zoom} onchange={loadLanes}>
      <option value="millennium">millennium</option>
      <option value="century">century</option>
      <option value="decade">decade</option>
    </select>
  </label>
  <span class="hint">Click a bar segment to see entities in that tradition × era.</span>
</section>

{#if loading}
  <p class="loading ui">Loading timeline…</p>
{:else if error}
  <p class="err ui">Error: {error}</p>
{:else if lanes.length && window_info}
  <div class="gantt" role="figure" aria-label="Timeline of traditions">
    <div class="axis" aria-hidden="true">
      {#each xTicks as ty}
        <span class="tick" style:left={`${xPct(ty)}%`}>
          <span class="tick-line"></span>
          <span class="tick-label ui">{yearLabel(ty)}</span>
        </span>
      {/each}
    </div>

    <div class="lanes">
      {#each lanes as lane (lane.tradition)}
        {@const maxCount = Math.max(1, ...lane.buckets.map(b => b.count))}
        {@const laneColor = hue(lane.tradition)}
        <div class="lane">
          <div class="lane-head" title={`${lane.n_entities} entities`}>
            <a href={link(`/tradition/${slugify(lane.tradition)}/`)} class="lane-name">{lane.tradition}</a>
            <span class="lane-count ui mono">{lane.n_entities}</span>
          </div>
          <div class="lane-track">
            <!-- continuous era bar (ghost) -->
            <span
              class="era-bar"
              style:left={`${xPct(lane.start_year)}%`}
              style:width={`${Math.max(0.5, xPct(lane.end_year) - xPct(lane.start_year))}%`}
              style:background={laneColor}
            ></span>
            <!-- density bins -->
            {#each lane.buckets as b}
              {@const bw = (window_info.step / (window_info.max_year - window_info.min_year)) * 100}
              <button
                class="bin"
                style:left={`${xPct(b.year)}%`}
                style:width={`${Math.max(0.3, bw)}%`}
                style:background={laneColor}
                style:opacity={densityOpacity(b.count, maxCount)}
                title={`${yearLabel(b.year)}: ${b.count} ${b.count === 1 ? 'entity' : 'entities'}`}
                onclick={() => openBucket(lane, b.year, b.year + window_info.step)}
              ></button>
            {/each}
          </div>
        </div>
      {/each}
    </div>
  </div>

  <p class="caption ui">
    Dots represent the {window_info.zoom}-level density of entities attested in that tradition.
    Tradition-era fallbacks fill the ghost bar where per-entity years aren't yet populated.
  </p>
{/if}

{#if panelOpen}
  <div class="panel-backdrop" onclick={closePanel} role="presentation"></div>
  <aside class="panel" role="dialog" aria-label={panelTitle} aria-modal="true">
    <header>
      <h2>{panelTitle}</h2>
      <button class="close" onclick={closePanel} aria-label="Close">×</button>
    </header>
    {#if panelLoading}
      <p class="ui loading">Loading…</p>
    {:else if panelMembers.length}
      <p class="ui caption">{panelMembers.length} entities · top by consensus confidence</p>
      <ul class="members">
        {#each panelMembers as m (m.id)}
          <li>
            <a href={link(`/entity/${slugify(m.name)}/`)} data-preview={m.id}>{m.name}</a>
            <span class="ui meta">
              {#if m.entity_type}{m.entity_type}{/if}
              {#if m.alignment} · {m.alignment}{/if}
              {#if m.first_documented_year != null}
                 · <span class="mono">{yearLabel(m.first_documented_year)}</span>
              {/if}
            </span>
          </li>
        {/each}
      </ul>
      {#if panelRange}
        <p class="ui caption">
          <a href={link(`/browse/?tradition=${encodeURIComponent(panelTradition)}`)}>
            Browse all {panelTradition} entities →
          </a>
        </p>
      {/if}
    {:else}
      <p class="ui muted">No entities in this range.</p>
    {/if}
  </aside>
{/if}

<style>
  .controls {
    display: flex;
    gap: var(--sp-4);
    align-items: center;
    padding: var(--sp-3);
    border: 1px solid var(--rule);
    border-radius: var(--r-md);
    background: var(--bg-alt);
    font-size: var(--fs-sm);
    color: var(--ink-dim);
    flex-wrap: wrap;
    margin-bottom: var(--sp-4);
  }
  .controls label { display: flex; align-items: center; gap: var(--sp-2); }
  .controls select {
    background: transparent;
    border: 1px solid var(--rule);
    border-radius: var(--r-sm);
    padding: 2px 8px;
    color: var(--ink);
    font-family: inherit;
    font-size: inherit;
  }
  .hint { margin-left: auto; color: var(--ink-faint); font-size: var(--fs-xs); }
  .gantt {
    position: relative;
    width: 100%;
    padding-top: 28px; /* axis label height */
    padding-left: 180px; /* lane head width reserve */
    border: 1px solid var(--rule);
    border-radius: var(--r-md);
    background: var(--bg);
    overflow: hidden;
  }
  .axis {
    position: absolute;
    top: 0;
    left: 180px;
    right: 0;
    height: 28px;
    border-bottom: 1px solid var(--rule);
  }
  .tick {
    position: absolute;
    top: 0;
    transform: translateX(-50%);
    color: var(--ink-faint);
    font-size: var(--fs-xs);
  }
  .tick-line {
    position: absolute;
    left: 50%;
    top: 18px;
    width: 1px;
    height: 10px;
    background: var(--rule);
  }
  .tick-label {
    display: inline-block;
    padding: 2px 4px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-family: var(--font-mono);
  }
  .lanes {
    display: flex;
    flex-direction: column;
  }
  .lane {
    display: contents;
  }
  .lane-head {
    position: absolute;
    left: 0;
    width: 180px;
    height: 22px;
    padding: 2px 8px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: var(--bg);
    border-bottom: 1px solid var(--rule-soft);
    z-index: 2;
  }
  .lane-name {
    font-family: var(--font-serif);
    font-size: var(--fs-sm);
    color: var(--ink);
    text-decoration: none;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 130px;
  }
  .lane-name:hover { color: var(--accent); text-decoration: underline; }
  .lane-count {
    color: var(--ink-faint);
    font-family: var(--font-mono);
    font-size: var(--fs-xs);
  }
  .lane-track {
    position: relative;
    height: 22px;
    margin-bottom: 0;
    border-bottom: 1px solid var(--rule-soft);
  }
  .era-bar {
    position: absolute;
    top: 9px;
    height: 4px;
    border-radius: 2px;
    opacity: 0.18;
  }
  .bin {
    position: absolute;
    top: 3px;
    height: 16px;
    border: none;
    cursor: pointer;
    padding: 0;
    border-radius: 1px;
    transition: filter var(--dur-fast) var(--ease);
  }
  .bin:hover {
    filter: brightness(1.15);
    outline: 1px solid var(--ink);
    outline-offset: 1px;
    z-index: 3;
  }
  .caption {
    color: var(--ink-faint);
    font-size: var(--fs-xs);
    margin-top: var(--sp-3);
    max-width: var(--col-prose);
  }
  .loading, .err, .muted { color: var(--ink-faint); padding: var(--sp-4); }
  .err { color: var(--conf-low); }

  /* Scaling — fix alignment with lane-head column at different widths */
  .lane-head,
  .lane-track {
    box-sizing: border-box;
  }

  /* fix positioning so .lane is a grid row */
  .lane {
    display: grid;
    grid-template-columns: 180px 1fr;
    position: relative;
  }
  .lane-head {
    position: relative;
    left: auto;
  }

  /* Drill-in panel */
  .panel-backdrop {
    position: fixed;
    inset: 0;
    background: rgb(0 0 0 / 0.35);
    backdrop-filter: blur(2px);
    z-index: 50;
  }
  .panel {
    position: fixed;
    top: 0;
    right: 0;
    width: min(560px, 95vw);
    height: 100%;
    background: var(--bg);
    border-left: 1px solid var(--rule);
    overflow-y: auto;
    padding: var(--sp-5);
    z-index: 51;
    animation: slidein var(--dur-base) var(--ease);
  }
  @keyframes slidein { from { transform: translateX(8%); opacity: 0.6; } to { transform: translateX(0); opacity: 1; } }
  .panel header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    border-bottom: 1px solid var(--rule);
    padding-bottom: var(--sp-3);
    margin-bottom: var(--sp-3);
  }
  .panel h2 { margin: 0; font-size: var(--fs-lg); font-weight: 450; }
  .panel .close {
    background: transparent;
    border: 0;
    color: var(--ink-faint);
    font-size: 20px;
    cursor: pointer;
    padding: 0 8px;
  }
  .panel .close:hover { color: var(--accent); }
  .members { list-style: none; padding: 0; margin: 0; }
  .members li {
    padding: var(--sp-2) 0;
    border-bottom: 1px solid var(--rule-soft);
    display: flex;
    align-items: baseline;
    gap: var(--sp-2);
    flex-wrap: wrap;
  }
  .members a {
    font-family: var(--font-serif);
    color: var(--ink);
    text-decoration: none;
  }
  .members a:hover { color: var(--accent); text-decoration: underline; }
  .meta { color: var(--ink-faint); font-size: var(--fs-xs); }
  .mono { font-family: var(--font-mono); }
</style>
