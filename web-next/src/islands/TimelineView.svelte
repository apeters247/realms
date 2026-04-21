<script lang="ts">
  import { onMount } from 'svelte';

  const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');
  const link = (p: string) => BASE + p;

  interface Bucket { century: string; count: number; }
  let summary = $state<{ total_dated: number; buckets: Bucket[] } | null>(null);
  let entities = $state<any[]>([]);
  let error = $state<string | null>(null);

  // Fallback tradition-era map — used when no entities carry a first-attested
  // year. Rough century bounds based on primary ethnographic/archaeological
  // consensus. Living traditions are bounded on the upper end by "present"
  // (2025 CE).
  const TRADITION_ERAS: Record<string, { start: number; end: number; continent: string }> = {
    'sumerian': { start: -3000, end: -1700, continent: 'near east' },
    'akkadian': { start: -2400, end: -550, continent: 'near east' },
    'egyptian': { start: -3000, end: -30, continent: 'africa' },
    'greek': { start: -800, end: 400, continent: 'europe' },
    'roman': { start: -500, end: 500, continent: 'europe' },
    'norse': { start: 500, end: 1200, continent: 'europe' },
    'celtic': { start: -400, end: 500, continent: 'europe' },
    'irish': { start: 0, end: 1500, continent: 'europe' },
    'slavic': { start: 500, end: 1500, continent: 'europe' },
    'germanic': { start: 0, end: 1000, continent: 'europe' },
    'finnish': { start: 500, end: 1900, continent: 'europe' },
    'baltic': { start: 800, end: 1500, continent: 'europe' },
    'basque': { start: 0, end: 2025, continent: 'europe' },
    'christian': { start: 30, end: 2025, continent: 'global' },
    'catholic': { start: 100, end: 2025, continent: 'europe' },
    'hindu': { start: -1500, end: 2025, continent: 'south asia' },
    'vedic': { start: -1500, end: -500, continent: 'south asia' },
    'buddhist': { start: -500, end: 2025, continent: 'asia' },
    'jain': { start: -600, end: 2025, continent: 'south asia' },
    'taoist': { start: -500, end: 2025, continent: 'east asia' },
    'chinese folk': { start: -1200, end: 2025, continent: 'east asia' },
    'japanese': { start: 500, end: 2025, continent: 'east asia' },
    'shinto': { start: 500, end: 2025, continent: 'east asia' },
    'korean': { start: 0, end: 2025, continent: 'east asia' },
    'mongol': { start: 1000, end: 1800, continent: 'asia' },
    'tengrism': { start: -200, end: 2025, continent: 'asia' },
    'turkic': { start: 500, end: 2025, continent: 'asia' },
    'siberian': { start: -2000, end: 2025, continent: 'asia' },
    'chukchi': { start: -500, end: 2025, continent: 'asia' },
    'koryak': { start: -500, end: 2025, continent: 'asia' },
    'yakut': { start: 500, end: 2025, continent: 'asia' },
    'nivkh': { start: 0, end: 2025, continent: 'asia' },
    'yup\'ik': { start: 0, end: 2025, continent: 'americas' },
    'inuit': { start: 0, end: 2025, continent: 'americas' },
    'aztec': { start: 1300, end: 1521, continent: 'americas' },
    'maya': { start: -1800, end: 1521, continent: 'americas' },
    'inca': { start: 1200, end: 1533, continent: 'americas' },
    'yanomami': { start: 0, end: 2025, continent: 'americas' },
    'quechua': { start: 1000, end: 2025, continent: 'americas' },
    'cherokee': { start: 1000, end: 2025, continent: 'americas' },
    'lakota': { start: 1500, end: 2025, continent: 'americas' },
    'navajo': { start: 1400, end: 2025, continent: 'americas' },
    'hopi': { start: 1000, end: 2025, continent: 'americas' },
    'plains indian': { start: 1500, end: 2025, continent: 'americas' },
    'yoruba': { start: 800, end: 2025, continent: 'africa' },
    'igbo': { start: 1000, end: 2025, continent: 'africa' },
    'akan': { start: 1200, end: 2025, continent: 'africa' },
    'vodou': { start: 1700, end: 2025, continent: 'americas' },
    'santería': { start: 1500, end: 2025, continent: 'americas' },
    'candomblé': { start: 1700, end: 2025, continent: 'americas' },
    'gorovodu': { start: 1800, end: 2025, continent: 'africa' },
    'zulu': { start: 1600, end: 2025, continent: 'africa' },
    'san': { start: -10000, end: 2025, continent: 'africa' },
    'yoruba-diaspora': { start: 1700, end: 2025, continent: 'global' },
    'polynesian': { start: 500, end: 2025, continent: 'oceania' },
    'maori': { start: 1200, end: 2025, continent: 'oceania' },
    'hawaiian': { start: 1000, end: 2025, continent: 'oceania' },
    'aboriginal australian': { start: -50000, end: 2025, continent: 'oceania' },
    'persian': { start: -1000, end: 2025, continent: 'near east' },
    'zoroastrian': { start: -1000, end: 2025, continent: 'near east' },
    'hebrew bible': { start: -1200, end: 200, continent: 'near east' },
    'jewish': { start: -1200, end: 2025, continent: 'global' },
    'islamic': { start: 600, end: 2025, continent: 'global' },
    'arab': { start: -200, end: 2025, continent: 'near east' },
    'hittite': { start: -1600, end: -1200, continent: 'near east' },
    'etruscan': { start: -800, end: -100, continent: 'europe' },
  };

  function eraForTradition(t: string | null | undefined) {
    if (!t) return null;
    const key = t.toLowerCase();
    // exact match first, then partial
    if (TRADITION_ERAS[key]) return TRADITION_ERAS[key];
    for (const [k, era] of Object.entries(TRADITION_ERAS)) {
      if (key.includes(k)) return era;
    }
    return null;
  }

  function parseCenturyLabel(label: string): number {
    const m = label.match(/(\d+)/);
    const n = m ? parseInt(m[1], 10) : 0;
    return label.includes('BCE') ? -n : n;
  }

  onMount(async () => {
    try {
      const [s, e, entitiesAll] = await Promise.all([
        fetch('/timeline/summary').then(r => r.json()).then(r => r.data),
        fetch('/timeline/entities?limit=500').then(r => r.json()).then(r => r.data || []),
        fetch('/entities/?per_page=500').then(r => r.json()).then(r => r.data || []),
      ]);
      summary = s;
      entities = e;
      if ((s?.total_dated ?? 0) === 0) {
        // Build fallback buckets from tradition eras.
        const bucketByCentury: Map<number, number> = new Map();
        for (const ent of entitiesAll) {
          const trad = (ent.cultural_associations || [])[0];
          const era = eraForTradition(trad);
          if (!era) continue;
          // Bucket by start century.
          const cent = Math.floor(era.start / 100) * 100;
          bucketByCentury.set(cent, (bucketByCentury.get(cent) ?? 0) + 1);
        }
        const buckets: Bucket[] = [...bucketByCentury.entries()]
          .sort((a, b) => a[0] - b[0])
          .map(([cent, count]) => ({
            century: cent < 0
              ? `${Math.ceil(Math.abs(cent) / 100)}c BCE`
              : `${Math.floor(cent / 100) + 1}c CE`,
            count,
          }));
        summary = { total_dated: buckets.reduce((s, b) => s + b.count, 0), buckets };
        // Populate a synthetic list sorted by tradition era.
        entities = entitiesAll
          .map((ent: any) => {
            const era = eraForTradition((ent.cultural_associations || [])[0]);
            return era ? { ...ent, first_documented_year: era.start, _era_inferred: true } : null;
          })
          .filter(Boolean)
          .sort((a: any, b: any) => a.first_documented_year - b.first_documented_year)
          .slice(0, 500);
      }
    } catch (err) {
      error = (err as Error).message;
    }
  });

  const maxCount = $derived.by(() => {
    if (!summary) return 1;
    return summary.buckets.reduce((m, b) => Math.max(m, b.count), 1);
  });

  const isInferred = $derived(entities.length > 0 && entities.every(e => e._era_inferred));
</script>

{#if error}
  <p class="err ui">Could not load timeline: {error}</p>
{:else if !summary}
  <p class="ui">Loading…</p>
{:else if summary.total_dated === 0}
  <div class="empty">
    <p>No entities carry an explicit or inferrable first-attested year yet.</p>
    <p class="muted">Temporal fields are populated by extractor v4 during re-ingestion.</p>
  </div>
{:else}
  {#if isInferred}
    <p class="inferred ui">
      ⚠ Showing <strong>tradition-era estimates</strong>, not per-entity attested years.
      Re-ingestion with extractor v4 will populate exact years.
    </p>
  {/if}

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
    <span>{entities.length} entities</span>
    <span class="muted">sorted {isInferred ? 'by tradition era (inferred)' : 'by first_documented_year'}</span>
  </div>
  <ul class="ent-list">
    {#each entities as e (e.id)}
      <li>
        <span class="yr mono">
          {e.first_documented_year < 0
            ? `${Math.abs(e.first_documented_year)} BCE`
            : `${e.first_documented_year} CE`}
          {#if e._era_inferred}<span class="approx" title="tradition-era estimate">~</span>{/if}
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
  .inferred {
    background: color-mix(in srgb, var(--accent-2) 12%, transparent);
    border-left: 2px solid var(--accent-2);
    color: var(--ink-dim);
    padding: var(--sp-3);
    font-size: var(--fs-sm);
    margin-bottom: var(--sp-4);
  }
  .inferred strong { color: var(--ink); }
  .histogram { margin-bottom: var(--sp-6); }
  .ax { font-size: var(--fs-xs); color: var(--ink-faint); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: var(--sp-2); }
  .bars {
    display: grid;
    grid-auto-flow: column;
    grid-auto-columns: minmax(60px, 1fr);
    gap: 2px;
    height: 220px;
    align-items: end;
    border-bottom: 1px solid var(--rule);
    padding-bottom: var(--sp-2);
    overflow-x: auto;
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
  .n { font-size: var(--fs-xs); color: var(--ink); }
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
  .ent-list { list-style: none; margin: 0; padding: 0; }
  .ent-list li {
    display: grid;
    grid-template-columns: 120px 1fr;
    gap: var(--sp-3);
    padding: var(--sp-2) 0;
    border-bottom: 1px solid var(--rule-soft);
    font-family: var(--font-serif);
  }
  .yr { color: var(--ink-faint); font-size: var(--fs-sm); text-align: right; }
  .yr .approx { margin-left: 2px; color: var(--accent-2); }
  .cult { color: var(--ink-faint); font-size: var(--fs-sm); }
  .mono { font-family: var(--font-mono); }
</style>
