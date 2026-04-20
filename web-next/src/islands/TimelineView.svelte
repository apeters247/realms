<script lang="ts">
  import { onMount } from 'svelte';

  const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');
  const link = (p: string) => BASE + p;

  interface Bucket { century: string; count: number; }
  let summary = $state<{ total_dated: number; buckets: Bucket[] } | null>(null);
  let entities = $state<any[]>([]);
  let error = $state<string | null>(null);

  function parseCenturyLabel(label: string): number {
    const m = label.match(/(\d+)/);
    const n = m ? parseInt(m[1], 10) : 0;
    return label.includes('BCE') ? -n : n;
  }

  onMount(async () => {
    try {
      const [s, e] = await Promise.all([
        fetch('/timeline/summary').then(r => r.json()).then(r => r.data),
        fetch('/timeline/entities?limit=500').then(r => r.json()).then(r => r.data || []),
      ]);
      summary = s;
      entities = e;
    } catch (err) {
      error = (err as Error).message;
    }
  });

  const maxCount = $derived.by(() => {
    if (!summary) return 1;
    return summary.buckets.reduce((m, b) => Math.max(m, b.count), 1);
  });
</script>

{#if error}
  <p class="err ui">Could not load timeline: {error}</p>
{:else if !summary}
  <p class="ui">Loading…</p>
{:else if summary.total_dated === 0}
  <div class="empty">
    <p>No entities carry an explicit first-attested year yet.</p>
    <p class="muted">Temporal fields are populated by extractor v4 during re-ingestion.</p>
  </div>
{:else}
  <div class="histogram" role="figure" aria-label="Histogram of entities by century">
    <div class="ax ui">Century</div>
    <div class="bars" style:--max={maxCount}>
      {#each summary.buckets as b (b.century)}
        {@const h = (b.count / maxCount) * 100}
        <div class="bar-wrap">
          <div class="bar" style:height={`${h}%`} title={`${b.century}: ${b.count}`}></div>
          <div class="label ui">{b.century}</div>
          <div class="n ui mono">{b.count}</div>
        </div>
      {/each}
    </div>
  </div>

  <div class="list-head ui">
    <span>{entities.length} dated entities</span>
    <span class="muted">sorted by first_documented_year</span>
  </div>
  <ul class="ent-list">
    {#each entities as e (e.id)}
      <li>
        <span class="yr mono">
          {e.first_documented_year < 0
            ? `${Math.abs(e.first_documented_year)} BCE`
            : `${e.first_documented_year} CE`}
        </span>
        <a href={link(`/entity/${(e.name || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')}/`)}
           data-preview={e.id}>{e.name}</a>
        {#if e.cultural_associations?.[0]}
          <span class="cult">· {e.cultural_associations[0]}</span>
        {/if}
      </li>
    {/each}
  </ul>
{/if}

<style>
  .histogram {
    margin-bottom: var(--sp-6);
  }
  .ax {
    font-size: var(--fs-xs);
    color: var(--ink-faint);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: var(--sp-2);
  }
  .bars {
    display: grid;
    grid-auto-flow: column;
    grid-auto-columns: minmax(60px, 1fr);
    gap: 2px;
    height: 220px;
    align-items: end;
    border-bottom: 1px solid var(--rule);
    padding-bottom: var(--sp-2);
  }
  .bar-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: end;
    gap: 4px;
    height: 100%;
  }
  .bar {
    width: 70%;
    background: var(--ink-dim);
    min-height: 1px;
    transition: height var(--dur-slow) var(--ease);
  }
  .label {
    font-size: var(--fs-xs);
    color: var(--ink-faint);
    text-align: center;
    line-height: 1.1;
    max-width: 80px;
    word-break: break-word;
  }
  .n {
    font-size: var(--fs-xs);
    color: var(--ink);
  }
  .empty { padding: var(--sp-7); text-align: center; }
  .empty .muted { color: var(--ink-faint); font-size: var(--fs-sm); }
  .err { color: var(--conf-low); }
  .list-head {
    display: flex;
    justify-content: space-between;
    padding: var(--sp-2) 0;
    border-top: 1px solid var(--rule);
    border-bottom: 1px solid var(--rule);
    font-size: var(--fs-sm);
    color: var(--ink-dim);
  }
  .muted { color: var(--ink-faint); }
  .ent-list {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .ent-list li {
    display: grid;
    grid-template-columns: 120px 1fr;
    gap: var(--sp-3);
    padding: var(--sp-2) 0;
    border-bottom: 1px solid var(--rule-soft);
    font-family: var(--font-serif);
  }
  .yr {
    color: var(--ink-faint);
    font-size: var(--fs-sm);
    text-align: right;
  }
  .cult { color: var(--ink-faint); font-size: var(--fs-sm); }
  .mono { font-family: var(--font-mono); }
</style>
