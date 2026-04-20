<script lang="ts">
  import { onMount } from 'svelte';

  let active = $state(false);
  let promptOpen = $state(false);
  let tokenInput = $state('');

  onMount(() => {
    active = localStorage.getItem('realms.researcher') === 'true';
    applyAttr();
  });

  function applyAttr() {
    if (active) document.documentElement.setAttribute('data-researcher', 'true');
    else document.documentElement.removeAttribute('data-researcher');
  }

  function toggle() {
    if (active) {
      active = false;
      localStorage.removeItem('realms.researcher');
      localStorage.removeItem('realms.reviewToken');
      applyAttr();
    } else {
      promptOpen = true;
    }
  }

  function saveToken() {
    if (!tokenInput.trim()) return;
    localStorage.setItem('realms.reviewToken', tokenInput.trim());
    localStorage.setItem('realms.researcher', 'true');
    active = true;
    applyAttr();
    tokenInput = '';
    promptOpen = false;
  }

  function cancel() {
    promptOpen = false;
    tokenInput = '';
  }
</script>

<button class="nav-btn" onclick={toggle} title={active ? 'Researcher mode on' : 'Enter researcher mode'} aria-pressed={active}>
  <span class="glyph" class:active>¶</span>
</button>

{#if promptOpen}
  <div class="overlay" role="dialog" aria-modal="true" aria-label="Researcher token">
    <div class="sheet">
      <h3>Researcher mode</h3>
      <p class="muted">Requires the REALMS_REVIEW_TOKEN set on the server.</p>
      <input
        type="password"
        bind:value={tokenInput}
        placeholder="review token"
        autofocus
      />
      <div class="actions">
        <button class="secondary" onclick={cancel}>Cancel</button>
        <button class="primary" onclick={saveToken}>Enable</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .nav-btn {
    background: transparent;
    border: 1px solid var(--rule);
    color: var(--ink-dim);
    padding: 4px 10px;
    border-radius: var(--r-md);
    cursor: pointer;
    font-family: var(--font-serif);
    font-size: var(--fs-base);
    line-height: 1;
    transition: all var(--dur-fast) var(--ease);
  }
  .nav-btn:hover {
    color: var(--ink);
    border-color: var(--ink-faint);
  }
  .glyph.active {
    color: var(--accent);
  }
  .overlay {
    position: fixed;
    inset: 0;
    background: color-mix(in srgb, var(--ink) 45%, transparent);
    backdrop-filter: blur(4px);
    display: grid;
    place-items: center;
    z-index: 100;
  }
  .sheet {
    background: var(--bg);
    border: 1px solid var(--rule);
    border-radius: var(--r-md);
    padding: var(--sp-6);
    width: min(420px, 90vw);
    font-family: var(--font-sans);
  }
  .sheet h3 {
    margin: 0 0 var(--sp-3);
    font-family: var(--font-serif);
  }
  .muted {
    color: var(--ink-dim);
    font-size: var(--fs-sm);
    margin-bottom: var(--sp-4);
  }
  input {
    width: 100%;
    padding: var(--sp-3);
    font-family: var(--font-mono);
    border: 1px solid var(--rule);
    border-radius: var(--r-md);
    background: var(--bg-alt);
    color: var(--ink);
    font-size: var(--fs-base);
    margin-bottom: var(--sp-4);
  }
  input:focus-visible {
    outline: 2px solid var(--accent);
    border-color: var(--accent);
  }
  .actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--sp-2);
  }
  button.primary, button.secondary {
    font-family: var(--font-sans);
    padding: var(--sp-2) var(--sp-4);
    border-radius: var(--r-md);
    cursor: pointer;
    font-size: var(--fs-sm);
  }
  button.primary {
    background: var(--accent);
    color: var(--bg);
    border: 1px solid var(--accent);
  }
  button.secondary {
    background: transparent;
    color: var(--ink-dim);
    border: 1px solid var(--rule);
  }
</style>
