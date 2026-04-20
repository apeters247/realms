<script lang="ts">
  import { onMount } from 'svelte';

  interface Action {
    id: number;
    entity_id: number;
    reviewer: string;
    action: string;
    field: string | null;
    created_at: string;
    note: string | null;
  }

  let actions = $state<Action[]>([]);
  let status = $state('');
  let limit = $state(200);
  let filterAction = $state<string>('');

  const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');
  const link = (p: string) => BASE + p;

  onMount(() => { refresh(); });

  async function refresh() {
    status = 'loading…';
    try {
      const params = new URLSearchParams({ limit: String(limit) });
      if (filterAction) params.set('action', filterAction);
      const r = await fetch(`/review/actions?${params}`);
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      const payload = await r.json();
      actions = payload.data || [];
      status = '';
    } catch (e) {
      status = `error: ${(e as Error).message}`;
    }
  }

  function fmt(ts: string): string {
    return new Date(ts).toISOString().slice(0, 19).replace('T', ' ');
  }

  const ACTIONS = ['', 'approve', 'reject', 'edit', 'merge_into', 'external_link', 'external_unlink', 'external_link_suggest'];
</script>

<section class="controls ui">
  <label>
    Filter
    <select bind:value={filterAction} onchange={refresh}>
      {#each ACTIONS as a}
        <option value={a}>{a || 'all actions'}</option>
      {/each}
    </select>
  </label>
  <label>
    Limit
    <select bind:value={limit} onchange={refresh}>
      <option value={50}>50</option>
      <option value={200}>200</option>
      <option value={1000}>1000</option>
    </select>
  </label>
  <button onclick={refresh}>Refresh</button>
  <span class="status">{status}</span>
</section>

<p class="count ui">{actions.length} actions</p>

{#if actions.length}
  <ol class="audit">
    {#each actions as a (a.id)}
      <li>
        <span class="mono when">{fmt(a.created_at)}</span>
        <span class="reviewer">{a.reviewer}</span>
        <span class={`action a-${a.action}`}>{a.action}</span>
        {#if a.field}<span class="field">· {a.field}</span>{/if}
        <span class="target">on <a href={link(`/entity/${a.entity_id}/`)}>#{a.entity_id}</a></span>
        {#if a.note}<span class="note">— {a.note}</span>{/if}
      </li>
    {/each}
  </ol>
{:else}
  <p class="muted">No audit rows match these filters.</p>
{/if}

<style>
  .controls {
    display: flex;
    gap: var(--sp-5);
    flex-wrap: wrap;
    align-items: center;
    padding: var(--sp-3);
    border: 1px solid var(--rule);
    border-radius: var(--r-md);
    background: var(--bg-alt);
    color: var(--ink-dim);
    margin-bottom: var(--sp-3);
    font-size: var(--fs-sm);
  }
  .controls label { display: flex; align-items: center; gap: var(--sp-2); }
  .controls select {
    background: transparent;
    border: 1px solid var(--rule);
    color: var(--ink);
    border-radius: var(--r-sm);
    padding: 2px 6px;
    font-family: inherit;
    font-size: inherit;
  }
  .controls button {
    padding: 4px 10px;
    border: 1px solid var(--rule);
    background: transparent;
    border-radius: var(--r-md);
    cursor: pointer;
    color: var(--ink-dim);
  }
  .controls button:hover { color: var(--ink); border-color: var(--ink-faint); }
  .status { margin-left: auto; font-family: var(--font-mono); font-size: var(--fs-xs); color: var(--ink-faint); }
  .count { color: var(--ink-faint); font-size: var(--fs-sm); margin: 0 0 var(--sp-3) 0; }
  .audit { list-style: none; padding: 0; margin: 0; font-size: var(--fs-sm); font-family: var(--font-sans); }
  .audit li {
    padding: var(--sp-2) 0;
    border-bottom: 1px solid var(--rule-soft);
    display: flex;
    gap: var(--sp-2);
    align-items: baseline;
    flex-wrap: wrap;
  }
  .audit .when { color: var(--ink-faint); font-size: var(--fs-xs); }
  .audit .reviewer { color: var(--ink-dim); }
  .audit .action {
    text-transform: uppercase;
    font-size: var(--fs-xs);
    letter-spacing: 0.08em;
    padding: 1px 6px;
    border-radius: 2px;
  }
  .audit .a-approve { color: var(--conf-high); background: color-mix(in srgb, var(--conf-high) 12%, transparent); }
  .audit .a-reject { color: var(--conf-low); background: color-mix(in srgb, var(--conf-low) 12%, transparent); }
  .audit .a-edit { color: var(--accent-2); }
  .audit .a-merge_into { color: var(--accent); }
  .audit .a-external_link { color: var(--accent); }
  .audit .field { color: var(--ink-faint); }
  .audit .target a { color: var(--accent-2); }
  .audit .note { color: var(--ink-dim); font-style: italic; }
  .muted { color: var(--ink-faint); }
</style>
