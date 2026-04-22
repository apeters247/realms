<script lang="ts">
  import { onMount } from 'svelte';

  interface Ent {
    id: number;
    name: string;
    slug: string;
    entity_type: string | null;
    realm: string | null;
    culture: string | null;
    confidence: number;
  }

  const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');
  const link = (p: string) => BASE + p;

  let all = $state<Ent[]>([]);
  let loading = $state(true);

  // filters
  let q = $state('');
  let selType = $state('');
  let selRealm = $state('');
  let selCulture = $state('');
  let selConfMin = $state(0.0);
  let selLetter = $state('');

  // pagination
  const PAGE_SIZE = 100;
  let page = $state(1);

  onMount(async () => {
    try {
      const r = await fetch(BASE + '/search-index.json');
      const payload = await r.json();
      all = (payload.entities || []).filter((e: Ent) => e.name);
    } catch {
      all = [];
    } finally {
      loading = false;
    }
    // Apply URL state
    if (typeof window !== 'undefined') {
      const u = new URL(window.location.href);
      q = u.searchParams.get('q') || '';
      selType = u.searchParams.get('type') || '';
      selRealm = u.searchParams.get('realm') || '';
      selCulture = u.searchParams.get('culture') || '';
      selLetter = u.searchParams.get('letter') || '';
      selConfMin = parseFloat(u.searchParams.get('conf_min') || '0');
      page = parseInt(u.searchParams.get('page') || '1', 10);
    }
  });

  function normalise(s: string): string {
    return (s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  }

  let filtered = $derived.by(() => {
    if (!all.length) return [];
    const nq = normalise(q.trim());
    return all.filter(e => {
      if (selType && e.entity_type !== selType) return false;
      if (selRealm && e.realm !== selRealm) return false;
      if (selCulture && e.culture !== selCulture) return false;
      if (selConfMin > 0 && (e.confidence ?? 0) < selConfMin) return false;
      if (selLetter && !normalise(e.name).startsWith(selLetter.toLowerCase())) return false;
      if (nq && !normalise(e.name).includes(nq)) return false;
      return true;
    });
  });

  // Sorted alphabetically for stable browsing.
  let sorted = $derived(
    filtered.slice().sort((a, b) => a.name.localeCompare(b.name)),
  );
  let pageCount = $derived(Math.max(1, Math.ceil(sorted.length / PAGE_SIZE)));
  let pageClamped = $derived(Math.min(page, pageCount));
  let pageItems = $derived(sorted.slice((pageClamped - 1) * PAGE_SIZE, pageClamped * PAGE_SIZE));

  // Facet options
  let typeOptions = $derived.by(() => {
    const c: Record<string, number> = {};
    for (const e of all) if (e.entity_type) c[e.entity_type] = (c[e.entity_type] || 0) + 1;
    return Object.entries(c).sort((a, b) => b[1] - a[1]);
  });
  let realmOptions = $derived.by(() => {
    const c: Record<string, number> = {};
    for (const e of all) if (e.realm) c[e.realm] = (c[e.realm] || 0) + 1;
    return Object.entries(c).sort((a, b) => b[1] - a[1]);
  });
  let cultureOptions = $derived.by(() => {
    const c: Record<string, number> = {};
    for (const e of all) if (e.culture) c[e.culture] = (c[e.culture] || 0) + 1;
    return Object.entries(c).sort((a, b) => b[1] - a[1]).slice(0, 50);
  });

  const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');

  // Sync URL state on filter change
  function syncUrl() {
    if (typeof window === 'undefined') return;
    const u = new URL(window.location.href);
    const set = (k: string, v: string | number) => {
      if (v !== '' && v !== 0 && v !== null && v !== undefined) u.searchParams.set(k, String(v));
      else u.searchParams.delete(k);
    };
    set('q', q); set('type', selType); set('realm', selRealm);
    set('culture', selCulture); set('letter', selLetter);
    set('conf_min', selConfMin || '');
    set('page', page > 1 ? page : '');
    window.history.replaceState({}, '', u);
  }

  // React to filter changes: reset page, update URL
  let lastFilterKey = $state('');
  $effect(() => {
    const k = [q, selType, selRealm, selCulture, selConfMin, selLetter].join('|');
    if (k !== lastFilterKey) {
      lastFilterKey = k;
      page = 1;
    }
    syncUrl();
  });

  function reset() {
    q = ''; selType = ''; selRealm = ''; selCulture = ''; selLetter = '';
    selConfMin = 0; page = 1;
  }
  function setLetter(l: string) {
    selLetter = (selLetter === l ? '' : l);
  }
</script>

<div class="browse-ui">
  <section class="filter-rail ui">
    <div class="row">
      <input class="search" type="search" bind:value={q}
             placeholder={`Search ${all.length ? all.length.toLocaleString() + ' entities' : 'entities'}…`}
             aria-label="Search entities" />
      <button class="clear" onclick={reset} disabled={!(q || selType || selRealm || selCulture || selLetter || selConfMin)}>
        Clear filters
      </button>
    </div>
    <div class="row facets">
      <label>
        Type
        <select bind:value={selType}>
          <option value="">any</option>
          {#each typeOptions as [t, n]}
            <option value={t}>{t} ({n})</option>
          {/each}
        </select>
      </label>
      <label>
        Realm
        <select bind:value={selRealm}>
          <option value="">any</option>
          {#each realmOptions as [r, n]}
            <option value={r}>{r} ({n})</option>
          {/each}
        </select>
      </label>
      <label>
        Tradition
        <select bind:value={selCulture}>
          <option value="">any</option>
          {#each cultureOptions as [c, n]}
            <option value={c}>{c} ({n})</option>
          {/each}
        </select>
      </label>
      <label>
        Min confidence
        <select bind:value={selConfMin}>
          <option value={0}>any</option>
          <option value={0.7}>good (≥0.70)</option>
          <option value={0.85}>high (≥0.85)</option>
          <option value={0.95}>excellent (≥0.95)</option>
        </select>
      </label>
    </div>
    <div class="row alpha">
      {#each LETTERS as l}
        <button class="ltr" class:active={selLetter === l} onclick={() => setLetter(l)}>{l}</button>
      {/each}
      <span class="count">
        {#if !loading}
          {sorted.length.toLocaleString()} / {all.length.toLocaleString()}
        {/if}
      </span>
    </div>
  </section>

  {#if loading}
    <p class="loading">Loading index…</p>
  {:else if !sorted.length}
    <p class="empty">No entities match these filters.</p>
  {:else}
    <ul class="results">
      {#each pageItems as e (e.id)}
        <li>
          <a href={link(`/entity/${e.slug}/`)} data-preview={e.id}>
            <span class="r-name">{e.name}</span>
            <span class="r-meta ui">
              {#if e.entity_type}{e.entity_type}{/if}
              {#if e.culture} · {e.culture}{/if}
              {#if e.realm} · {e.realm}{/if}
            </span>
          </a>
        </li>
      {/each}
    </ul>

    {#if pageCount > 1}
      <nav class="pager ui" aria-label="Pagination">
        <button onclick={() => { page = 1; }} disabled={pageClamped === 1}>« first</button>
        <button onclick={() => { page = Math.max(1, pageClamped - 1); }} disabled={pageClamped === 1}>‹ prev</button>
        <span class="page-info">page {pageClamped} of {pageCount}</span>
        <button onclick={() => { page = Math.min(pageCount, pageClamped + 1); }} disabled={pageClamped === pageCount}>next ›</button>
        <button onclick={() => { page = pageCount; }} disabled={pageClamped === pageCount}>last »</button>
      </nav>
    {/if}
  {/if}
</div>

<style>
  .browse-ui { margin-top: var(--sp-4); }
  .filter-rail {
    position: sticky;
    top: var(--nav-h, 56px);
    background: color-mix(in srgb, var(--bg) 95%, transparent);
    backdrop-filter: blur(6px) saturate(140%);
    -webkit-backdrop-filter: blur(6px) saturate(140%);
    border-top: 1px solid var(--rule);
    border-bottom: 1px solid var(--rule);
    padding: var(--sp-3) 0;
    z-index: 5;
    margin-bottom: var(--sp-5);
  }
  .row {
    display: flex;
    gap: var(--sp-3);
    flex-wrap: wrap;
    align-items: center;
    margin-bottom: var(--sp-2);
  }
  .row:last-child { margin-bottom: 0; }
  .search {
    flex: 1;
    min-width: 200px;
    padding: 8px 12px;
    border: 1px solid var(--rule);
    border-radius: var(--r-md);
    background: var(--bg);
    color: var(--ink);
    font-family: var(--font-serif);
    font-size: var(--fs-base);
  }
  .search:focus { outline: 2px solid var(--accent); outline-offset: 2px; }
  .clear {
    padding: 6px 12px;
    border: 1px solid var(--rule);
    background: transparent;
    border-radius: var(--r-sm);
    cursor: pointer;
    color: var(--ink-dim);
    font-size: var(--fs-sm);
  }
  .clear:hover { color: var(--accent); border-color: var(--accent); }
  .clear:disabled { opacity: 0.3; cursor: not-allowed; }
  .facets label {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: var(--fs-xs);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--ink-faint);
  }
  .facets select {
    background: var(--bg);
    border: 1px solid var(--rule);
    border-radius: var(--r-sm);
    padding: 3px 6px;
    font-family: var(--font-mono);
    font-size: var(--fs-xs);
    color: var(--ink);
    max-width: 180px;
    text-transform: none;
  }
  .alpha {
    font-family: var(--font-serif);
    font-size: var(--fs-sm);
  }
  .ltr {
    background: transparent;
    border: 1px solid transparent;
    color: var(--ink-dim);
    cursor: pointer;
    padding: 1px 6px;
    border-radius: var(--r-sm);
    font-family: inherit;
    font-size: inherit;
  }
  .ltr:hover { color: var(--accent); }
  .ltr.active { background: var(--accent); color: var(--bg); }
  .count {
    margin-left: auto;
    color: var(--ink-faint);
    font-family: var(--font-mono);
    font-size: var(--fs-xs);
  }
  .loading, .empty { color: var(--ink-faint); padding: var(--sp-4) 0; }
  .results {
    list-style: none;
    padding: 0;
    margin: 0;
    columns: 2;
    column-gap: var(--sp-5);
  }
  @media (min-width: 1024px) { .results { columns: 3; } }
  @media (max-width: 640px) { .results { columns: 1; } }
  .results li { break-inside: avoid; padding: 2px 0; }
  .results a {
    color: inherit;
    text-decoration: none;
    display: block;
    padding: 3px 4px;
    border-radius: var(--r-sm);
  }
  .results a:hover {
    background: var(--bg-alt);
    color: var(--accent);
  }
  .r-name { font-family: var(--font-serif); font-size: var(--fs-base); }
  .r-meta {
    color: var(--ink-faint);
    font-size: var(--fs-xs);
    margin-left: 6px;
    font-variant-caps: small-caps;
    letter-spacing: 0.04em;
  }
  .pager {
    margin-top: var(--sp-6);
    padding-top: var(--sp-3);
    border-top: 1px solid var(--rule);
    display: flex;
    gap: var(--sp-2);
    justify-content: center;
    align-items: center;
    font-size: var(--fs-sm);
    color: var(--ink-dim);
  }
  .pager button {
    background: transparent;
    border: 1px solid var(--rule);
    border-radius: var(--r-sm);
    padding: 4px 10px;
    cursor: pointer;
    color: var(--ink-dim);
    font-family: inherit;
    font-size: inherit;
  }
  .pager button:hover { color: var(--accent); border-color: var(--accent); }
  .pager button:disabled { opacity: 0.3; cursor: not-allowed; }
  .page-info { font-family: var(--font-mono); font-size: var(--fs-xs); color: var(--ink-faint); }
</style>
