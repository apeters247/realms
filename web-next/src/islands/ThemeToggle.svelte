<script lang="ts">
  import { onMount } from 'svelte';

  let theme = $state<'light' | 'dark' | 'system'>('system');

  onMount(() => {
    const stored = localStorage.getItem('realms.theme');
    if (stored === 'light' || stored === 'dark') theme = stored;
    else theme = 'system';
  });

  function cycle() {
    const next = theme === 'light' ? 'dark' : theme === 'dark' ? 'system' : 'light';
    theme = next;
    if (next === 'system') {
      localStorage.removeItem('realms.theme');
      document.documentElement.removeAttribute('data-theme');
    } else {
      localStorage.setItem('realms.theme', next);
      document.documentElement.setAttribute('data-theme', next);
    }
  }

  const label = $derived.by(() => {
    if (theme === 'light') return 'Light';
    if (theme === 'dark') return 'Dark';
    return 'Auto';
  });

  const glyph = $derived.by(() => {
    if (theme === 'light') return '☼';
    if (theme === 'dark') return '☾';
    return '◐';
  });
</script>

<button class="nav-btn" onclick={cycle} title={`Theme: ${label} (click to cycle)`} aria-label="Change theme">
  <span class="glyph">{glyph}</span>
</button>

<style>
  .nav-btn {
    background: transparent;
    border: 1px solid var(--rule);
    color: var(--ink-dim);
    padding: 4px 8px;
    border-radius: var(--r-md);
    cursor: pointer;
    font-family: var(--font-serif);
    font-size: var(--fs-base);
    line-height: 1;
    min-width: 30px;
    transition: all var(--dur-fast) var(--ease);
  }
  .nav-btn:hover {
    color: var(--ink);
    border-color: var(--ink-faint);
  }
  .glyph { display: inline-block; }
</style>
