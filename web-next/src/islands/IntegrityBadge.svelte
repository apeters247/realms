<script lang="ts">
  import { onMount } from 'svelte';

  interface Stats {
    window_days: number;
    corpus_error_rate: number;
    integrity_score: number;
    n_audits: number;
    n_samples: number;
    n_supported: number;
    n_ambiguous: number;
    n_contradicted: number;
    last_audit_at: string | null;
    flagged_ingestions_in_window: number;
  }

  let stats = $state<Stats | null>(null);
  let error = $state<string | null>(null);

  onMount(async () => {
    try {
      const r = await fetch('/integrity/stats');
      if (!r.ok) throw new Error(`${r.status}`);
      const payload = await r.json();
      stats = payload.data;
    } catch (e) {
      error = (e as Error).message;
    }
  });

  let pct = $derived(stats ? Math.round(stats.integrity_score * 1000) / 10 : 0);
  let state = $derived.by(() => {
    if (!stats) return 'loading';
    if (stats.n_samples === 0) return 'no_data';
    if (stats.integrity_score >= 0.99) return 'good';
    if (stats.integrity_score >= 0.95) return 'warn';
    return 'alert';
  });
</script>

<div class="badge" data-state={state}>
  {#if state === 'loading'}
    <span class="muted">Loading integrity metrics…</span>
  {:else if error}
    <span class="muted">Integrity data unavailable.</span>
  {:else if state === 'no_data'}
    <span class="muted">
      No oracle samples yet. Pipeline runs nightly; come back in 24h.
    </span>
  {:else if stats}
    <div class="score" aria-label={`integrity score ${pct} percent`}>
      <span class="n">{pct}%</span>
      <span class="l ui">integrity score</span>
    </div>
    <div class="meta ui">
      <div>{stats.n_samples} claims audited over {stats.window_days} days</div>
      <div>
        {stats.n_supported} supported ·
        <span class="amb">{stats.n_ambiguous}</span> ambiguous ·
        <span class="con">{stats.n_contradicted}</span> contradicted
      </div>
      {#if stats.last_audit_at}
        <div class="muted">last audit {new Date(stats.last_audit_at).toISOString().slice(0, 10)}</div>
      {/if}
      {#if stats.flagged_ingestions_in_window > 0}
        <div class="muted">{stats.flagged_ingestions_in_window} entities flagged for review</div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .badge {
    display: grid;
    grid-template-columns: 160px 1fr;
    gap: var(--sp-4);
    align-items: center;
    padding: var(--sp-4);
    border: 1px solid var(--rule);
    border-radius: var(--r-md);
    background: var(--bg-alt);
    margin: var(--sp-4) 0;
  }
  .badge[data-state="good"] { border-color: var(--conf-high); }
  .badge[data-state="warn"] { border-color: var(--accent-2); }
  .badge[data-state="alert"] { border-color: var(--conf-low); }
  .score {
    display: flex;
    flex-direction: column;
    align-items: baseline;
  }
  .score .n {
    font-family: var(--font-serif);
    font-size: 48px;
    line-height: 1;
    color: var(--ink);
    font-variation-settings: 'opsz' 144;
  }
  .badge[data-state="good"] .score .n { color: var(--conf-high); }
  .badge[data-state="warn"] .score .n { color: var(--accent-2); }
  .badge[data-state="alert"] .score .n { color: var(--conf-low); }
  .score .l {
    font-size: var(--fs-xs);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--ink-faint);
    margin-top: 2px;
  }
  .meta {
    display: grid;
    gap: 4px;
    font-size: var(--fs-sm);
    color: var(--ink-dim);
  }
  .meta .muted { color: var(--ink-faint); font-size: var(--fs-xs); }
  .meta .amb { color: var(--accent-2); }
  .meta .con { color: var(--conf-low); }
  .muted { color: var(--ink-faint); }
  @media (max-width: 600px) {
    .badge { grid-template-columns: 1fr; text-align: left; }
  }
</style>
