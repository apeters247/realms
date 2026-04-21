<script lang="ts">
  import { onMount } from 'svelte';

  interface Props { initialQuery?: string; }
  let { initialQuery = '' }: Props = $props();

  let query = $state(initialQuery);
  let results = $state<any[]>([]);
  let similar = $state<any[]>([]);
  let status = $state<string>('idle');
  let debounce: ReturnType<typeof setTimeout> | null = null;

  // Facets — all empty means no filter
  let filterType = $state<string>('');
  let filterAlignment = $state<string>('');
  let filterRealm = $state<string>('');

  const TYPES = ['', 'deity', 'ancestor', 'nature_spirit', 'plant_spirit', 'animal_ally',
                 'human_specialist', 'angelic', 'demonic'];
  const ALIGNMENTS = ['', 'beneficial', 'protective', 'neutral', 'ambiguous', 'malevolent'];
  const REALMS = ['', 'earth', 'sky', 'underworld', 'water', 'forest', 'mountain', 'intermediate'];

  async function run() {
    const q = query.trim();
    const hasFacets = !!(filterType || filterAlignment || filterRealm);
    if (!q && !hasFacets) {
      results = [];
      similar = [];
      status = 'idle';
      return;
    }
    status = 'searching';
    try {
      // Use advanced search when facets are set OR query is long enough for real matching.
      if (hasFacets) {
        const filters: Record<string, any> = {};
        if (q) filters.q = q;
        if (filterType) filters.entity_type = filterType;
        if (filterAlignment) filters.alignment = filterAlignment;
        if (filterRealm) filters.realm = filterRealm;
        const r = await fetch('/search/advanced', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ filters, per_page: 80, sort: '-consensus_confidence' }),
        });
        const payload = await r.json();
        results = payload.data || [];
        similar = [];
        status = `${results.length} match${results.length === 1 ? '' : 'es'}`;
      } else {
        const enc = encodeURIComponent(q);
        const [r1, r2] = await Promise.all([
          fetch(`/search/?q=${enc}`).then(r => r.ok ? r.json() : { data: [] }),
          fetch(`/search/similar?q=${enc}`).then(r => r.ok ? r.json() : { data: [] }),
        ]);
        results = r1.data || [];
        similar = r2.data || [];
        status = `${results.length} match${results.length === 1 ? '' : 'es'}`;
      }
      syncUrl();
    } catch (err) {
      status = `failed: ${(err as Error).message}`;
    }
  }

  function syncUrl() {
    if (typeof window === 'undefined') return;
    const url = new URL(window.location.href);
    if (query) url.searchParams.set('q', query); else url.searchParams.delete('q');
    for (const [k, v] of Object.entries({
      type: filterType, align: filterAlignment, realm: filterRealm,
    })) {
      if (v) url.searchParams.set(k, v); else url.searchParams.delete(k);
    }
    window.history.replaceState({}, '', url);
  }

  onMount(() => {
    if (typeof window !== 'undefined') {
      const u = new URL(window.location.href);
      filterType = u.searchParams.get('type') || '';
      filterAlignment = u.searchParams.get('align') || '';
      filterRealm = u.searchParams.get('realm') || '';
    }
    if (initialQuery || filterType || filterAlignment || filterRealm) run();
  });

  function onInput() {
    if (debounce) clearTimeout(debounce);
    debounce = setTimeout(run, 180);
  }

  function onFacetChange() { run(); }

  function slugify(name: string): string {
    return (name || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  }

  const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');
  const link = (p: string) => BASE + p;
</script>

<input
  class="sbox"
  type="search"
  bind:value={query}
  oninput={onInput}
  placeholder="Search entities, traditions, regions…"
  autofocus
/>

<section class="facets ui" aria-label="Search filters">
  <label>
    Type
    <select bind:value={filterType} onchange={onFacetChange}>
      {#each TYPES as t}<option value={t}>{t || 'any'}</option>{/each}
    </select>
  </label>
  <label>
    Alignment
    <select bind:value={filterAlignment} onchange={onFacetChange}>
      {#each ALIGNMENTS as a}<option value={a}>{a || 'any'}</option>{/each}
    </select>
  </label>
  <label>
    Realm
    <select bind:value={filterRealm} onchange={onFacetChange}>
      {#each REALMS as r}<option value={r}>{r || 'any'}</option>{/each}
    </select>
  </label>
  <span class="status">{status}</span>
</section>

{#if results.length}
  <ul class="hits">
    {#each results as e (e.id)}
      <li>
        <a href={link(`/entity/${slugify(e.name)}/`)} data-preview={e.id}>{e.name}</a>
        <span class="meta ui">
          {#if e.entity_type}{e.entity_type}{/if}
          {#if e.alignment} · {e.alignment}{/if}
          {#if e.realm} · {e.realm}{/if}
          {#if e.cultural_associations?.[0]} · {e.cultural_associations[0]}{/if}
        </span>
      </li>
    {/each}
  </ul>
{:else if status === 'idle'}
  <p class="empty ui">Enter a query or pick a filter.</p>
{:else if status.startsWith('searching')}
  <p class="empty ui">Searching…</p>
{:else}
  <p class="empty ui">No matches.</p>
{/if}

{#if similar.length}
  <section class="similar">
    <h2 class="sim-head ui">Did you mean</h2>
    <ul class="hits">
      {#each similar.slice(0, 12) as s (s.id)}
        <li>
          <a href={link(`/entity/${slugify(s.name)}/`)} data-preview={s.id}>{s.name}</a>
          {#if s.similarity != null}
            <span class="meta ui mono">{Number(s.similarity).toFixed(2)}</span>
          {/if}
        </li>
      {/each}
    </ul>
  </section>
{/if}

<style>
  .sbox {
    width: 100%;
    max-width: var(--col-prose);
    padding: 10px 14px;
    border: 1px solid var(--rule);
    border-radius: var(--r-md);
    font-family: var(--font-serif);
    font-size: var(--fs-md);
    background: var(--bg);
    color: var(--ink);
    margin-bottom: var(--sp-3);
  }
  .sbox:focus {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
  .facets {
    display: flex;
    flex-wrap: wrap;
    gap: var(--sp-4);
    padding: var(--sp-3);
    border: 1px solid var(--rule);
    border-radius: var(--r-md);
    background: var(--bg-alt);
    margin-bottom: var(--sp-4);
    font-size: var(--fs-sm);
    color: var(--ink-dim);
    align-items: center;
  }
  .facets label { display: flex; align-items: center; gap: var(--sp-2); }
  .facets select {
    border: 1px solid var(--rule);
    border-radius: var(--r-sm);
    background: var(--bg);
    color: var(--ink);
    padding: 2px 6px;
    font-family: var(--font-mono);
    font-size: inherit;
  }
  .status {
    margin-left: auto;
    font-family: var(--font-mono);
    font-size: var(--fs-xs);
    color: var(--ink-faint);
  }
  .hits {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .hits li {
    padding: var(--sp-2) 0;
    border-bottom: 1px solid var(--rule-soft);
  }
  .hits a {
    font-family: var(--font-serif);
    font-size: var(--fs-md);
    color: var(--ink);
    text-decoration: none;
  }
  .hits a:hover { color: var(--accent); text-decoration: underline; }
  .meta {
    color: var(--ink-faint);
    font-size: var(--fs-sm);
    margin-left: var(--sp-2);
  }
  .empty { color: var(--ink-faint); }
  .similar { margin-top: var(--sp-6); }
  .sim-head {
    font-size: var(--fs-xs);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--ink-faint);
    border-top: 1px solid var(--rule);
    padding-top: var(--sp-3);
  }
  .mono { font-family: var(--font-mono); }
</style>
