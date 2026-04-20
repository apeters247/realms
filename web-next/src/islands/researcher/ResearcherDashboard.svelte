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

  interface Action {
    id: number;
    entity_id: number;
    reviewer: string;
    action: string;
    field: string | null;
    created_at: string;
    note: string | null;
  }

  let token = $state<string>('');
  let stats = $state<any>(null);
  let queue = $state<ReviewRow[]>([]);
  let actions = $state<Action[]>([]);
  let confidenceMax = $state(0.75);
  let singleSource = $state(false);
  let isolatedOnly = $state(false);
  let status = $state('');

  onMount(() => {
    token = localStorage.getItem('realms.reviewToken') || '';
    refresh();
  });

  function authHeaders() {
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  async function refresh() {
    status = 'loading';
    try {
      const params = new URLSearchParams({ confidence_max: String(confidenceMax), limit: '100' });
      if (singleSource) params.set('single_source_only', 'true');
      if (isolatedOnly) params.set('isolated_only', 'true');
      const [s, q, a] = await Promise.all([
        fetch('/review/stats').then(r => r.json()).then(r => r.data),
        fetch(`/review/entities?${params}`).then(r => r.json()).then(r => r.data),
        fetch('/review/actions?limit=25').then(r => r.ok ? r.json() : { data: [] }).then(r => r.data),
      ]);
      stats = s;
      queue = q;
      actions = a;
      status = '';
    } catch (e) {
      status = `error: ${(e as Error).message}`;
    }
  }

  async function perform(id: number, path: string, body?: unknown) {
    try {
      const resp = await fetch(`/review/entities/${id}/${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: body ? JSON.stringify(body) : undefined,
      });
      if (resp.status === 401 || resp.status === 403) {
        alert('Token rejected — enter a new one in the top-right toggle.');
        return;
      }
      if (!resp.ok) {
        alert(`Action failed: ${resp.status} ${resp.statusText}`);
        return;
      }
      await refresh();
    } catch (e) {
      alert((e as Error).message);
    }
  }

  function slugify(name: string): string {
    return (name || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  }

  const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');
  const link = (p: string) => BASE + p;
</script>

<section class="stats">
  {#if stats}
    <div class="stat"><div class="n">{stats.total_entities}</div><div class="label">Total</div></div>
    <div class="stat"><div class="n">{stats.low_confidence}</div><div class="label">Low conf</div></div>
    <div class="stat"><div class="n">{stats.very_low_confidence}</div><div class="label">Very low</div></div>
    <div class="stat"><div class="n">{stats.single_source_entities}</div><div class="label">Single source</div></div>
    <div class="stat"><div class="n">{stats.isolated_entities}</div><div class="label">Isolated</div></div>
  {:else}
    <div class="stat muted">loading…</div>
  {/if}
</section>

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

<section>
  <h2>Review queue ({queue.length})</h2>
  <table class="queue">
    <thead>
      <tr>
        <th>ID</th><th>Name</th><th>Type</th><th>Conf</th><th>Sources</th><th>Flags</th><th>Actions</th>
      </tr>
    </thead>
    <tbody>
      {#each queue as e (e.id)}
        <tr>
          <td class="mono">{e.id}</td>
          <td>
            <a href={link(`/entity/${slugify(e.name)}/`)} data-preview={e.id}>{e.name}</a>
          </td>
          <td class="ui">{e.entity_type || '—'}</td>
          <td class="mono">{(e.consensus_confidence || 0).toFixed(2)}</td>
          <td class="mono">{e.n_sources}</td>
          <td class="flags ui">{(e.flags || []).join(', ')}</td>
          <td class="acts">
            <button class="ok" onclick={() => perform(e.id, 'approve', { note: null })}>✓</button>
            <button class="no" onclick={() => confirm(`Reject #${e.id}?`) && perform(e.id, 'reject', { note: null })}>✗</button>
            <button class="think" onclick={() => perform(e.id, 'suggest')}>💡</button>
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</section>

<section>
  <h2>Recent audit</h2>
  {#if actions.length}
    <ol class="audit">
      {#each actions as a (a.id)}
        <li>
          <span class="mono when">{new Date(a.created_at).toISOString().slice(0, 19).replace('T', ' ')}</span>
          <span class="reviewer">{a.reviewer}</span>
          <span class="action">{a.action}</span>
          {#if a.field}<span class="field">· {a.field}</span>{/if}
          <span class="target">on <a href={link(`/entity/${a.entity_id}/`)}>#{a.entity_id}</a></span>
          {#if a.note}<span class="note">— {a.note}</span>{/if}
        </li>
      {/each}
    </ol>
  {:else}
    <p class="muted">No audit rows yet.</p>
  {/if}
</section>

<style>
  .stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: var(--sp-3);
    padding: var(--sp-4) 0;
    border-top: 1px solid var(--rule);
    border-bottom: 1px solid var(--rule);
    margin-bottom: var(--sp-5);
  }
  .stat .n {
    font-family: var(--font-serif);
    font-size: var(--fs-2xl);
    color: var(--ink);
  }
  .stat .label {
    color: var(--ink-faint);
    font-size: var(--fs-xs);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .stat.muted { color: var(--ink-faint); }
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
    margin-bottom: var(--sp-5);
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
  h2 {
    font-size: var(--fs-lg);
    margin-top: var(--sp-6);
    text-transform: lowercase;
    font-variant-caps: small-caps;
    letter-spacing: 0.04em;
    color: var(--ink-dim);
  }
  .queue {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--fs-sm);
  }
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
    padding: 2px 8px;
    border: 1px solid var(--rule);
    background: transparent;
    cursor: pointer;
    border-radius: var(--r-sm);
    margin-right: 2px;
  }
  .acts .ok:hover { color: var(--conf-high); }
  .acts .no:hover { color: var(--conf-low); }
  .acts .think:hover { color: var(--accent-2); }
  .audit {
    list-style: none;
    padding: 0;
    margin: 0;
    font-size: var(--fs-sm);
    font-family: var(--font-sans);
  }
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
    color: var(--accent);
  }
  .audit .field { color: var(--ink-faint); }
  .audit .target a { color: var(--accent-2); }
  .audit .note { color: var(--ink-dim); font-style: italic; }
  .muted { color: var(--ink-faint); }
</style>
