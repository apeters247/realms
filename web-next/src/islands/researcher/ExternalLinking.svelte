<script lang="ts">
  import { onMount } from 'svelte';

  interface EntityRow {
    id: number;
    name: string;
    external_ids: Record<string, string> | null;
  }

  let token = $state<string>('');
  let entities = $state<EntityRow[]>([]);
  let status = $state('');
  let showOnlyUnlinked = $state(true);
  let systemPicks = $state<Record<number, string>>({});
  let idInputs = $state<Record<number, string>>({});

  const SYSTEMS = ['wikidata', 'viaf', 'wordnet', 'geonames'];
  const URL_TEMPLATES: Record<string, (id: string) => string> = {
    wikidata: id => `https://www.wikidata.org/wiki/${id}`,
    viaf: id => `https://viaf.org/viaf/${id}`,
    wordnet: id => `http://wordnet-rdf.princeton.edu/lemma/${id}`,
    geonames: id => `https://www.geonames.org/${id}`,
  };

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
      const r = await fetch(`/entities/?per_page=500`);
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      const payload = await r.json();
      entities = (payload.data || []).map((e: any) => ({
        id: e.id,
        name: e.name,
        external_ids: e.external_ids || null,
      }));
      status = '';
    } catch (e) {
      status = `error: ${(e as Error).message}`;
    }
  }

  async function linkTo(e: EntityRow) {
    const system = systemPicks[e.id] || 'wikidata';
    const externalId = (idInputs[e.id] || '').trim();
    if (!externalId) { alert('Enter an external ID first.'); return; }
    try {
      const resp = await fetch(`/review/entities/${e.id}/link`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ system, external_id: externalId, note: null }),
      });
      if (resp.status === 401 || resp.status === 403) {
        alert('Token rejected — configure the review token from the toggle in the top bar.');
        return;
      }
      if (!resp.ok) { alert(`Link failed: ${resp.status}`); return; }
      idInputs[e.id] = '';
      await refresh();
    } catch (err) {
      alert((err as Error).message);
    }
  }

  async function unlink(e: EntityRow, system: string) {
    if (!confirm(`Remove ${system} link from ${e.name}?`)) return;
    try {
      const resp = await fetch(`/review/entities/${e.id}/unlink`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ system }),
      });
      if (!resp.ok) { alert(`Unlink failed: ${resp.status}`); return; }
      await refresh();
    } catch (err) {
      alert((err as Error).message);
    }
  }

  function slugify(name: string): string {
    return (name || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  }

  let filtered = $derived.by(() => {
    if (!showOnlyUnlinked) return entities;
    return entities.filter(e => !e.external_ids || Object.keys(e.external_ids).length === 0);
  });
</script>

<section class="controls ui">
  <label><input type="checkbox" bind:checked={showOnlyUnlinked} /> Unlinked only</label>
  <button onclick={refresh}>Refresh</button>
  <span class="status">{status}</span>
</section>

<p class="count ui">{filtered.length} entities shown</p>

<table class="link-table">
  <thead>
    <tr>
      <th>ID</th>
      <th>Name</th>
      <th>Existing links</th>
      <th>Attach new link</th>
    </tr>
  </thead>
  <tbody>
    {#each filtered as e (e.id)}
      <tr>
        <td class="mono">{e.id}</td>
        <td><a href={link(`/entity/${slugify(e.name)}/`)} data-preview={e.id}>{e.name}</a></td>
        <td class="links">
          {#if e.external_ids && Object.keys(e.external_ids).length}
            {#each Object.entries(e.external_ids) as [sys, eid]}
              <span class="chip">
                <a href={URL_TEMPLATES[sys]?.(eid) ?? '#'} target="_blank" rel="noopener">{sys}:{eid}</a>
                <button class="x" aria-label="unlink" onclick={() => unlink(e, sys)}>×</button>
              </span>
            {/each}
          {:else}
            <span class="muted">—</span>
          {/if}
        </td>
        <td class="attach">
          <select bind:value={systemPicks[e.id]}>
            {#each SYSTEMS as s}<option value={s}>{s}</option>{/each}
          </select>
          <input type="text" placeholder="Q12345 / 12345…"
                 bind:value={idInputs[e.id]}
                 onkeydown={(ev) => ev.key === 'Enter' && linkTo(e)} />
          <button onclick={() => linkTo(e)}>link</button>
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
  .link-table { width: 100%; border-collapse: collapse; font-size: var(--fs-sm); }
  .link-table th, .link-table td {
    padding: var(--sp-2) var(--sp-3);
    border-bottom: 1px solid var(--rule-soft);
    text-align: left;
    vertical-align: middle;
  }
  .link-table th {
    font-family: var(--font-sans);
    font-size: var(--fs-xs);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--ink-faint);
    border-bottom-color: var(--rule);
  }
  .mono { font-family: var(--font-mono); color: var(--ink-dim); }
  .links { display: flex; flex-wrap: wrap; gap: 4px; }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    border: 1px solid var(--rule);
    border-radius: var(--r-sm);
    padding: 1px 6px;
    font-family: var(--font-mono);
    font-size: var(--fs-xs);
    background: var(--bg-alt);
  }
  .chip a { color: var(--ink); text-decoration: none; }
  .chip a:hover { color: var(--accent); text-decoration: underline; }
  .chip .x {
    border: 0;
    background: transparent;
    color: var(--ink-faint);
    cursor: pointer;
    padding: 0 2px;
    font-size: var(--fs-sm);
    line-height: 1;
  }
  .chip .x:hover { color: var(--conf-low); }
  .attach { display: flex; gap: 4px; align-items: center; }
  .attach select, .attach input {
    background: transparent;
    border: 1px solid var(--rule);
    color: var(--ink);
    font-family: var(--font-mono);
    font-size: var(--fs-xs);
    padding: 2px 6px;
    border-radius: var(--r-sm);
  }
  .attach input { max-width: 140px; }
  .attach button {
    padding: 2px 10px;
    border: 1px solid var(--rule);
    background: transparent;
    cursor: pointer;
    border-radius: var(--r-sm);
    font-size: var(--fs-xs);
    font-family: var(--font-sans);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--ink-dim);
  }
  .attach button:hover { color: var(--accent); border-color: var(--accent); }
  .muted { color: var(--ink-faint); }
</style>
