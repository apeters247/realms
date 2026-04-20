<script lang="ts">
  import { onMount } from 'svelte';

  interface ReviewRow {
    id: number;
    name: string;
    entity_type: string | null;
    consensus_confidence: number;
    n_sources: number;
    flags: string[];
  }

  let token = $state<string>('');
  let queue = $state<ReviewRow[]>([]);
  let confidenceMax = $state(0.75);
  let singleSource = $state(false);
  let isolatedOnly = $state(false);
  let status = $state('');
  let busy = $state<number | null>(null);

  const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');
  const link = (p: string) => BASE + p;

  onMount(() => {
    token = localStorage.getItem('realms.reviewToken') || '';
    refresh();
  });

  function authHeaders(): Record<string, string> {
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  async function refresh() {
    status = 'loading…';
    try {
      const params = new URLSearchParams({ confidence_max: String(confidenceMax), limit: '200' });
      if (singleSource) params.set('single_source_only', 'true');
      if (isolatedOnly) params.set('isolated_only', 'true');
      const r = await fetch(`/review/entities?${params}`);
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      const payload = await r.json();
      queue = payload.data || [];
      status = '';
    } catch (e) {
      status = `error: ${(e as Error).message}`;
    }
  }

  async function perform(id: number, path: string, body?: unknown) {
    busy = id;
    try {
      const resp = await fetch(`/review/entities/${id}/${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: body ? JSON.stringify(body) : undefined,
      });
      if (resp.status === 401 || resp.status === 403) {
        alert('Token rejected — enter a new one via the toggle in the top bar.');
        return;
      }
      if (!resp.ok) {
        alert(`Action failed: ${resp.status} ${resp.statusText}`);
        return;
      }
      await refresh();
    } catch (e) {
      alert((e as Error).message);
    } finally {
      busy = null;
    }
  }

  function slugify(name: string): string {
    return (name || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  }
</script>

<section class="controls ui">
  <label>
    Max confidence
    <input type="range" min="0" max="1" step="0.05" bind:value={confidenceMax} onchange={refresh} />
    <span class="mono">{confidenceMax.toFixed(2)}</span>
  </label>
  <label><input type="checkbox" bind:checked={singleSource} onchange={refresh} /> Single-source only</label>
  <label><input type="checkbox" bind:checked={isolatedOnly} onchange={refresh} /> Isolated only</label>
  <button onclick={refresh}>Refresh</button>
  <span class="status">{status}</span>
</section>

<p class="count ui">{queue.length} entities awaiting review</p>

<table class="queue">
  <thead>
    <tr>
      <th>ID</th><th>Name</th><th>Type</th><th>Conf</th><th>Sources</th><th>Flags</th><th>Actions</th>
    </tr>
  </thead>
  <tbody>
    {#each queue as e (e.id)}
      <tr class:busy={busy === e.id}>
        <td class="mono">{e.id}</td>
        <td><a href={link(`/entity/${slugify(e.name)}/`)} data-preview={e.id}>{e.name}</a></td>
        <td class="ui">{e.entity_type || '—'}</td>
        <td class="mono">{(e.consensus_confidence || 0).toFixed(2)}</td>
        <td class="mono">{e.n_sources}</td>
        <td class="flags ui">{(e.flags || []).join(', ')}</td>
        <td class="acts">
          <button class="ok" disabled={busy === e.id}
                  onclick={() => perform(e.id, 'approve', { note: null })}>approve</button>
          <button class="no" disabled={busy === e.id}
                  onclick={() => confirm(`Reject #${e.id}?`) && perform(e.id, 'reject', { note: null })}>reject</button>
          <button class="think" disabled={busy === e.id}
                  onclick={() => perform(e.id, 'suggest')}>suggest</button>
        </td>
      </tr>
    {/each}
  </tbody>
</table>

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
  .queue { width: 100%; border-collapse: collapse; font-size: var(--fs-sm); }
  .queue th, .queue td {
    padding: var(--sp-2) var(--sp-3);
    border-bottom: 1px solid var(--rule-soft);
    text-align: left;
  }
  .queue th {
    font-family: var(--font-sans);
    font-size: var(--fs-xs);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--ink-faint);
    border-bottom-color: var(--rule);
  }
  .mono { font-family: var(--font-mono); color: var(--ink-dim); }
  .flags { color: var(--ink-faint); font-size: var(--fs-xs); }
  .acts button {
    padding: 2px 10px;
    border: 1px solid var(--rule);
    background: transparent;
    cursor: pointer;
    border-radius: var(--r-sm);
    margin-right: 3px;
    font-size: var(--fs-xs);
    font-family: var(--font-sans);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--ink-dim);
  }
  .acts .ok:hover { color: var(--conf-high); border-color: var(--conf-high); }
  .acts .no:hover { color: var(--conf-low); border-color: var(--conf-low); }
  .acts .think:hover { color: var(--accent-2); border-color: var(--accent-2); }
  .acts button:disabled { opacity: 0.4; cursor: not-allowed; }
  tr.busy { opacity: 0.6; }
</style>
