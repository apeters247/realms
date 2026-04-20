<script lang="ts">
  import { onMount, tick } from 'svelte';
  import Fuse from 'fuse.js';

  const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');
  const link = (p: string) => BASE + p;

  interface SearchItem {
    type: 'entity' | 'tradition' | 'region' | 'action';
    id: string;
    name: string;
    hint?: string;
    href: string;
  }

  let open = $state(false);
  let query = $state('');
  let highlighted = $state(0);
  let items: SearchItem[] = $state([]);
  let fuse: Fuse<SearchItem> | null = null;
  let inputEl: HTMLInputElement | null = $state(null);

  const actions: SearchItem[] = [
    { type: 'action', id: 'act-browse', name: 'Browse all entities', hint: 'Go to browse', href: link('/browse/') },
    { type: 'action', id: 'act-graph', name: 'Open graph view', hint: 'Go to graph', href: link('/graph/') },
    { type: 'action', id: 'act-timeline', name: 'Open timeline', hint: 'Go to timeline', href: link('/timeline/') },
    { type: 'action', id: 'act-map', name: 'Open map', hint: 'Go to map', href: link('/map/') },
    { type: 'action', id: 'act-sources', name: 'Sources', hint: 'Go to sources', href: link('/sources/') },
    { type: 'action', id: 'act-researcher', name: 'Researcher dashboard', hint: 'Requires token', href: link('/researcher/') },
    { type: 'action', id: 'act-about', name: 'About REALMS', hint: 'Methodology & citation', href: link('/about/') },
    { type: 'action', id: 'act-random', name: 'Surprise me', hint: 'Random entity', href: '#random' },
  ];

  onMount(async () => {
    window.addEventListener('keydown', onKey);
    window.addEventListener('realms:cmdk-open', openPalette as EventListener);
    // Load search manifest (built at static-build time)
    try {
      const resp = await fetch(link('/search-index.json'), { cache: 'force-cache' });
      if (resp.ok) {
        const manifest = await resp.json();
        items = [
          ...actions,
          ...(manifest.entities || []).map((e: any) => ({
            type: 'entity' as const,
            id: String(e.id),
            name: e.name,
            hint: [e.entity_type, e.realm].filter(Boolean).join(' · '),
            href: link(`/entity/${e.slug}/`),
          })),
          ...(manifest.traditions || []).map((t: any) => ({
            type: 'tradition' as const,
            id: String(t.id),
            name: t.name,
            hint: 'Tradition',
            href: link(`/tradition/${t.slug}/`),
          })),
        ];
      } else {
        items = actions;
      }
    } catch {
      items = actions;
    }
    fuse = new Fuse(items, {
      keys: ['name', 'hint'],
      threshold: 0.34,
      ignoreLocation: true,
    });
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('realms:cmdk-open', openPalette as EventListener);
    };
  });

  function onKey(ev: KeyboardEvent) {
    const mod = ev.metaKey || ev.ctrlKey;
    if (mod && ev.key.toLowerCase() === 'k') {
      ev.preventDefault();
      openPalette();
      return;
    }
    if (!open) return;
    if (ev.key === 'Escape') {
      close();
      return;
    }
    if (ev.key === 'ArrowDown') {
      ev.preventDefault();
      highlighted = Math.min(highlighted + 1, filtered.length - 1);
    } else if (ev.key === 'ArrowUp') {
      ev.preventDefault();
      highlighted = Math.max(highlighted - 1, 0);
    } else if (ev.key === 'Enter') {
      ev.preventDefault();
      choose(filtered[highlighted]);
    }
  }

  async function openPalette() {
    open = true;
    highlighted = 0;
    query = '';
    await tick();
    inputEl?.focus();
  }

  function close() {
    open = false;
  }

  async function choose(item: SearchItem | undefined) {
    if (!item) return;
    close();
    if (item.id === 'act-random') {
      if (items.length) {
        const entities = items.filter(i => i.type === 'entity');
        if (entities.length) {
          const pick = entities[Math.floor(Math.random() * entities.length)];
          window.location.assign(pick.href);
          return;
        }
      }
    }
    window.location.assign(item.href);
  }

  const filtered = $derived.by(() => {
    if (!query.trim()) return items.slice(0, 12);
    if (!fuse) return items.slice(0, 12);
    return fuse.search(query.trim()).slice(0, 30).map(r => r.item);
  });
</script>

{#if open}
  <div class="overlay" role="dialog" aria-modal="true" aria-label="Command palette" onclick={close}>
    <div class="palette" onclick={(ev) => ev.stopPropagation()} role="presentation">
      <input
        bind:this={inputEl}
        bind:value={query}
        oninput={() => (highlighted = 0)}
        placeholder="Search entities, traditions, or jump to…"
        autocomplete="off"
        spellcheck="false"
      />
      <ul class="results" role="listbox">
        {#each filtered as item, i (item.id)}
          <li
            role="option"
            aria-selected={i === highlighted}
            class:active={i === highlighted}
            onmouseenter={() => (highlighted = i)}
            onclick={() => choose(item)}
          >
            <span class="kind">{item.type}</span>
            <span class="name">{item.name}</span>
            {#if item.hint}<span class="hint">{item.hint}</span>{/if}
          </li>
        {/each}
        {#if filtered.length === 0}
          <li class="empty">No matches.</li>
        {/if}
      </ul>
      <div class="footer">
        <span class="kbd">↑↓</span> navigate · <span class="kbd">↵</span> open · <span class="kbd">esc</span> close
      </div>
    </div>
  </div>
{/if}

<style>
  .overlay {
    position: fixed;
    inset: 0;
    background: color-mix(in srgb, var(--ink) 35%, transparent);
    backdrop-filter: blur(6px);
    display: grid;
    place-items: start center;
    z-index: 200;
    padding-top: 10vh;
  }
  .palette {
    width: min(640px, 92vw);
    background: var(--bg);
    border: 1px solid var(--rule);
    border-radius: var(--r-md);
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.18);
    display: flex;
    flex-direction: column;
    max-height: 72vh;
    overflow: hidden;
    font-family: var(--font-sans);
  }
  input {
    padding: var(--sp-4) var(--sp-5);
    font-size: var(--fs-md);
    border: 0;
    background: transparent;
    color: var(--ink);
    border-bottom: 1px solid var(--rule);
    font-family: var(--font-serif);
  }
  input:focus-visible { outline: none; }
  input::placeholder { color: var(--ink-faint); }

  .results {
    list-style: none;
    margin: 0;
    padding: var(--sp-2) 0;
    overflow-y: auto;
    flex: 1;
  }
  .results li {
    display: grid;
    grid-template-columns: 80px 1fr auto;
    gap: var(--sp-3);
    padding: var(--sp-2) var(--sp-5);
    align-items: baseline;
    cursor: pointer;
    font-size: var(--fs-sm);
    color: var(--ink-dim);
  }
  .results li.active {
    background: var(--bg-alt);
    color: var(--ink);
  }
  .kind {
    font-size: var(--fs-xs);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--ink-faint);
  }
  .name {
    font-family: var(--font-serif);
    font-size: var(--fs-base);
    color: inherit;
  }
  .hint {
    color: var(--ink-faint);
    font-size: var(--fs-xs);
    font-family: var(--font-sans);
  }
  .empty {
    padding: var(--sp-4) var(--sp-5);
    color: var(--ink-faint);
    font-style: italic;
  }
  .footer {
    border-top: 1px solid var(--rule);
    padding: var(--sp-2) var(--sp-5);
    font-size: var(--fs-xs);
    color: var(--ink-faint);
  }
  .kbd {
    font-family: var(--font-mono);
    background: var(--bg-alt);
    padding: 1px 5px;
    border-radius: var(--r-sm);
    border: 1px solid var(--rule);
  }
</style>
