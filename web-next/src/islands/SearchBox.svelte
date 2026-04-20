<script lang="ts">
  import { onMount } from 'svelte';

  interface Props { initialQuery?: string; }
  let { initialQuery = '' }: Props = $props();

  let query = $state(initialQuery);
  let results = $state<any[]>([]);
  let similar = $state<any[]>([]);
  let status = $state<string>('idle');
  let debounce: ReturnType<typeof setTimeout> | null = null;

  async function run(q: string) {
    if (!q.trim()) {
      results = [];
      similar = [];
      status = 'idle';
      return;
    }
    status = 'searching';
    const enc = encodeURIComponent(q);
    try {
      const [r1, r2] = await Promise.all([
        fetch(`/search/?q=${enc}`).then(r => r.ok ? r.json() : { data: [] }),
        fetch(`/search/similar?q=${enc}`).then(r => r.ok ? r.json() : { data: [] }),
      ]);
      results = r1.data || [];
      similar = r2.data || [];
      status = `${results.length} match${results.length === 1 ? '' : 'es'}`;
    } catch (err) {
      status = `failed: ${(err as Error).message}`;
    }
  }

  onMount(() => {
    if (initialQuery) run(initialQuery);
  });

  function onInput() {
    if (debounce) clearTimeout(debounce);
    debounce = setTimeout(() => run(query), 180);
    // Reflect in URL without full reload
    const url = new URL(window.location.href);
    if (query) url.searchParams.set('q', query); else url.searchParams.delete('q');
    window.history.replaceState({}, '', url);
  }

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
  placeholder="Search entities, traditions…"
  autofocus
/>
<div class="status ui">{status}</div>

{#if results.length > 0}
  <section class="results">
    <h2>Matches</h2>
    <ul>
      {#each results as item (item.id ?? item.name)}
        <li>
          <a href={link(`/entity/${slugify(item.name)}/`)} data-preview={item.id}>{item.name}</a>
          <span class="meta">{item.entity_type || ''}{item.realm ? ` · ${item.realm}` : ''}</span>
        </li>
      {/each}
    </ul>
  </section>
{/if}

{#if similar.length > 0}
  <section class="results">
    <h2>Similar names</h2>
    <ul>
      {#each similar as item (item.id ?? item.name)}
        <li>
          <a href={link(`/entity/${slugify(item.name)}/`)} data-preview={item.id}>{item.name}</a>
          <span class="meta">{item.entity_type || ''}</span>
        </li>
      {/each}
    </ul>
  </section>
{/if}

<style>
  .sbox {
    width: 100%;
    padding: var(--sp-4) var(--sp-5);
    font-family: var(--font-serif);
    font-size: var(--fs-xl);
    background: var(--bg);
    border: 1px solid var(--rule);
    border-radius: var(--r-md);
    color: var(--ink);
  }
  .sbox:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
    border-color: var(--accent);
  }
  .status {
    margin-top: var(--sp-2);
    color: var(--ink-faint);
    font-size: var(--fs-sm);
  }
  .results { margin-top: var(--sp-6); }
  .results h2 {
    font-size: var(--fs-md);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--ink-faint);
    border-bottom: 1px solid var(--rule);
    padding-bottom: var(--sp-2);
  }
  .results ul { list-style: none; padding: 0; margin: 0; }
  .results li {
    padding: var(--sp-2) 0;
    border-bottom: 1px solid var(--rule-soft);
    display: flex;
    align-items: baseline;
    gap: var(--sp-4);
  }
  .results li a {
    font-family: var(--font-serif);
    font-size: var(--fs-lg);
  }
  .meta {
    color: var(--ink-faint);
    font-size: var(--fs-sm);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
</style>
