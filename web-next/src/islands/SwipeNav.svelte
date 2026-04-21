<script lang="ts">
  import { onMount } from 'svelte';

  interface Props {
    prevHref: string | null;
    nextHref: string | null;
  }
  let { prevHref, nextHref }: Props = $props();

  const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');
  function link(p: string): string {
    if (p.startsWith('http') || p.startsWith(BASE)) return p;
    return BASE + p;
  }

  let startX = 0;
  let startY = 0;
  let startTime = 0;
  const THRESHOLD = 60;          // px horizontal
  const VERT_TOL = 40;           // px vertical allowed
  const MAX_DUR_MS = 400;        // fast swipe only

  function onTouchStart(e: TouchEvent) {
    const t = e.touches[0];
    startX = t.clientX;
    startY = t.clientY;
    startTime = Date.now();
  }

  function onTouchEnd(e: TouchEvent) {
    const t = e.changedTouches[0];
    const dx = t.clientX - startX;
    const dy = t.clientY - startY;
    const dt = Date.now() - startTime;
    if (dt > MAX_DUR_MS) return;
    if (Math.abs(dy) > VERT_TOL) return;
    if (dx >= THRESHOLD && prevHref) {
      window.location.assign(link(prevHref));
    } else if (dx <= -THRESHOLD && nextHref) {
      window.location.assign(link(nextHref));
    }
  }

  onMount(() => {
    // Only bind on coarse pointer (touch) devices to avoid confusing
    // mouse drags.
    if (!window.matchMedia('(pointer: coarse)').matches) return;
    document.addEventListener('touchstart', onTouchStart, { passive: true });
    document.addEventListener('touchend', onTouchEnd, { passive: true });
    return () => {
      document.removeEventListener('touchstart', onTouchStart);
      document.removeEventListener('touchend', onTouchEnd);
    };
  });
</script>

<!-- Compact visual prev/next bar that also works with keyboard & mouse. -->
<nav class="prev-next ui" aria-label="Entity navigation">
  {#if prevHref}
    <a href={link(prevHref)} rel="prev" class="pn">← Prev</a>
  {:else}
    <span class="pn disabled">← Prev</span>
  {/if}
  <span class="hint mobile-only">Swipe ↔</span>
  {#if nextHref}
    <a href={link(nextHref)} rel="next" class="pn">Next →</a>
  {:else}
    <span class="pn disabled">Next →</span>
  {/if}
</nav>

<style>
  .prev-next {
    display: flex;
    gap: var(--sp-3);
    align-items: center;
    justify-content: space-between;
    margin-top: var(--sp-5);
    padding-top: var(--sp-3);
    border-top: 1px solid var(--rule-soft);
    font-size: var(--fs-sm);
    color: var(--ink-dim);
  }
  .pn {
    color: var(--ink-dim);
    text-decoration: none;
    padding: 4px 10px;
    border-radius: var(--r-sm);
  }
  .pn:hover { color: var(--accent); background: var(--bg-alt); }
  .pn.disabled { color: var(--ink-faint); opacity: 0.5; cursor: not-allowed; }
  .hint { color: var(--ink-faint); font-size: var(--fs-xs); text-transform: uppercase; letter-spacing: 0.08em; }
  .mobile-only { display: none; }
  @media (pointer: coarse) { .mobile-only { display: inline; } }
</style>
