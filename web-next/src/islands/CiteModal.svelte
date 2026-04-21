<script lang="ts">
  import { onMount } from 'svelte';

  interface Props {
    entityId: number;
    entityName: string;
  }

  let { entityId, entityName }: Props = $props();

  let open = $state(false);
  let loading = $state(false);
  let bibtex = $state('');
  let cslJson = $state<any[] | null>(null);
  let error = $state<string | null>(null);
  let copied = $state<string | null>(null);

  // Compute the three common plain-prose formats client-side.
  let apaCitation = $derived(buildAPA());
  let mlaCitation = $derived(buildMLA());
  let chicagoCitation = $derived(buildChicago());

  function canonicalUrl(): string {
    if (typeof window === 'undefined') return '';
    return window.location.href.split('#')[0];
  }

  function buildAPA(): string {
    const year = new Date().getFullYear();
    return `REALMS. (${year}). ${entityName}. REALMS — Research Entity Archive for Light and Metaphysical Spirit Hierarchies. Retrieved from ${canonicalUrl()}`;
  }

  function buildMLA(): string {
    return `"${entityName}." REALMS — Research Entity Archive for Light and Metaphysical Spirit Hierarchies, ${canonicalUrl()}. Accessed ${new Date().toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' })}.`;
  }

  function buildChicago(): string {
    const date = new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
    return `REALMS. "${entityName}." Accessed ${date}. ${canonicalUrl()}.`;
  }

  async function load() {
    if (bibtex && cslJson) return;
    loading = true;
    error = null;
    try {
      const [bib, csl] = await Promise.all([
        fetch(`/export/entity/${entityId}.bib`).then(r => r.ok ? r.text() : Promise.reject(r.status)),
        fetch(`/export/entity/${entityId}.csl.json`).then(r => r.ok ? r.json() : Promise.reject(r.status)),
      ]);
      bibtex = bib;
      cslJson = csl;
    } catch (e) {
      error = `Could not load: ${e}`;
    } finally {
      loading = false;
    }
  }

  async function openModal() {
    open = true;
    await load();
    // Focus the close button for a11y
    await Promise.resolve();
    document.querySelector<HTMLButtonElement>('#cite-close')?.focus();
  }

  function closeModal() { open = false; copied = null; }

  async function copy(value: string, label: string) {
    try {
      await navigator.clipboard.writeText(value);
      copied = label;
      setTimeout(() => { if (copied === label) copied = null; }, 1600);
    } catch (e) {
      error = 'Clipboard denied; select the text and copy manually.';
    }
  }

  function handleKey(e: KeyboardEvent) {
    if (!open) return;
    if (e.key === 'Escape') closeModal();
  }

  onMount(() => {
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  });
</script>

<button class="cite-trigger ui" onclick={openModal} aria-label="Cite this entity">
  Cite this entity ↗
</button>

{#if open}
  <div class="backdrop" onclick={closeModal} role="presentation"></div>
  <div class="cite-modal" role="dialog" aria-labelledby="cite-title" aria-modal="true">
    <header>
      <h2 id="cite-title">Cite {entityName}</h2>
      <button id="cite-close" class="close" onclick={closeModal} aria-label="Close">×</button>
    </header>

    {#if error}<p class="err">{error}</p>{/if}
    {#if loading}<p class="loading ui">Fetching…</p>{/if}

    <section class="fmt">
      <label>APA
        <button class="copy" onclick={() => copy(apaCitation, 'apa')}>{copied === 'apa' ? 'Copied' : 'Copy'}</button>
      </label>
      <pre>{apaCitation}</pre>
    </section>

    <section class="fmt">
      <label>MLA
        <button class="copy" onclick={() => copy(mlaCitation, 'mla')}>{copied === 'mla' ? 'Copied' : 'Copy'}</button>
      </label>
      <pre>{mlaCitation}</pre>
    </section>

    <section class="fmt">
      <label>Chicago
        <button class="copy" onclick={() => copy(chicagoCitation, 'chi')}>{copied === 'chi' ? 'Copied' : 'Copy'}</button>
      </label>
      <pre>{chicagoCitation}</pre>
    </section>

    {#if bibtex}
    <section class="fmt">
      <label>BibTeX
        <button class="copy" onclick={() => copy(bibtex, 'bib')}>{copied === 'bib' ? 'Copied' : 'Copy'}</button>
      </label>
      <pre class="mono">{bibtex}</pre>
    </section>
    {/if}

    {#if cslJson}
    <section class="fmt">
      <label>CSL-JSON (Zotero/Mendeley)
        <button class="copy" onclick={() => copy(JSON.stringify(cslJson, null, 2), 'csl')}>{copied === 'csl' ? 'Copied' : 'Copy'}</button>
      </label>
      <pre class="mono">{JSON.stringify(cslJson, null, 2)}</pre>
    </section>
    {/if}

    <p class="licence ui">
      REALMS data is licensed <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener">CC&nbsp;BY&nbsp;4.0</a> — reuse with attribution.
    </p>
  </div>
{/if}

<style>
  .cite-trigger {
    padding: 6px 12px;
    border: 1px solid var(--rule);
    background: transparent;
    color: var(--ink-dim);
    font-size: var(--fs-sm);
    border-radius: var(--r-sm);
    cursor: pointer;
    font-family: inherit;
  }
  .cite-trigger:hover { color: var(--accent); border-color: var(--accent); }
  .backdrop {
    position: fixed;
    inset: 0;
    background: rgb(0 0 0 / 0.45);
    backdrop-filter: blur(2px);
    z-index: 50;
  }
  .cite-modal {
    position: fixed;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    max-width: 720px;
    max-height: 85vh;
    width: calc(100% - 32px);
    overflow-y: auto;
    z-index: 51;
    border: 1px solid var(--rule);
    border-radius: var(--r-md);
    background: var(--bg);
    color: var(--ink);
    padding: var(--sp-5);
    box-shadow: 0 16px 48px rgb(0 0 0 / 0.18);
  }
  header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-bottom: var(--sp-4);
    border-bottom: 1px solid var(--rule);
    padding-bottom: var(--sp-2);
  }
  h2 { margin: 0; font-size: var(--fs-xl); font-weight: 450; }
  .close {
    background: transparent;
    border: 0;
    color: var(--ink-faint);
    font-size: 24px;
    cursor: pointer;
    padding: 0 8px;
    line-height: 1;
  }
  .close:hover { color: var(--accent); }
  .err { color: var(--conf-low); font-size: var(--fs-sm); }
  .loading { color: var(--ink-faint); font-size: var(--fs-sm); }
  .fmt { margin-bottom: var(--sp-4); }
  .fmt label {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    font-size: var(--fs-xs);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--ink-faint);
    margin-bottom: 4px;
  }
  .copy {
    padding: 2px 10px;
    font-size: var(--fs-xs);
    border: 1px solid var(--rule);
    background: transparent;
    cursor: pointer;
    color: var(--ink-dim);
    border-radius: var(--r-sm);
    font-family: inherit;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .copy:hover { color: var(--ink); border-color: var(--ink-faint); }
  pre {
    margin: 0;
    padding: var(--sp-3);
    background: var(--bg-alt);
    border: 1px solid var(--rule-soft);
    border-radius: var(--r-sm);
    white-space: pre-wrap;
    word-break: break-word;
    font-family: var(--font-serif);
    font-size: var(--fs-sm);
    color: var(--ink);
  }
  pre.mono { font-family: var(--font-mono); font-size: var(--fs-xs); }
  .licence {
    font-size: var(--fs-xs);
    color: var(--ink-faint);
    border-top: 1px solid var(--rule-soft);
    padding-top: var(--sp-3);
    margin-top: var(--sp-4);
  }
  .licence a { color: var(--accent-2); }
</style>
