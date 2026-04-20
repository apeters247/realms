<script lang="ts">
  import { onMount } from 'svelte';

  interface Preview {
    id: number;
    name: string;
    entity_type: string | null;
    realm: string | null;
    description: string | null;
    cultural_associations: string[];
  }

  const HOVER_DELAY = 300;
  let active = $state(false);
  let pos = $state({ x: 0, y: 0 });
  let current = $state<Preview | null>(null);
  let loadingId = $state<number | null>(null);
  const cache = new Map<number, Preview>();
  let hoverTimer: ReturnType<typeof setTimeout> | null = null;

  onMount(() => {
    document.addEventListener('pointerover', onOver, true);
    document.addEventListener('pointerleave', onLeave, true);
    document.addEventListener('scroll', hide, { passive: true });
    return () => {
      document.removeEventListener('pointerover', onOver, true);
      document.removeEventListener('pointerleave', onLeave, true);
      document.removeEventListener('scroll', hide);
    };
  });

  function nearestPreviewTarget(el: EventTarget | null): HTMLElement | null {
    if (!(el instanceof HTMLElement)) return null;
    return el.closest('[data-preview]') as HTMLElement | null;
  }

  function onOver(ev: Event) {
    const target = nearestPreviewTarget(ev.target);
    if (!target) return;
    const id = Number(target.getAttribute('data-preview'));
    if (!id) return;
    const rect = target.getBoundingClientRect();
    pos = { x: rect.left + rect.width / 2, y: rect.bottom + 8 };
    clearHover();
    hoverTimer = setTimeout(() => load(id), HOVER_DELAY);
  }

  function onLeave(ev: Event) {
    const target = nearestPreviewTarget(ev.target);
    if (!target) return;
    clearHover();
    active = false;
  }

  function hide() {
    active = false;
    clearHover();
  }

  function clearHover() {
    if (hoverTimer) clearTimeout(hoverTimer);
    hoverTimer = null;
  }

  async function load(id: number) {
    if (cache.has(id)) {
      current = cache.get(id)!;
      active = true;
      return;
    }
    loadingId = id;
    try {
      const resp = await fetch(`/entities/${id}`);
      if (!resp.ok) return;
      const { data } = await resp.json();
      const preview: Preview = {
        id: data.id,
        name: data.name,
        entity_type: data.entity_type,
        realm: data.realm,
        description: data.description,
        cultural_associations: data.cultural_associations || [],
      };
      cache.set(id, preview);
      if (loadingId === id) {
        current = preview;
        active = true;
      }
    } catch {
      // swallow — preview is best-effort
    } finally {
      if (loadingId === id) loadingId = null;
    }
  }
</script>

{#if active && current}
  <div
    class="preview"
    style:left={`${pos.x}px`}
    style:top={`${pos.y}px`}
    role="tooltip"
  >
    <div class="name">{current.name}</div>
    <div class="meta ui">
      {#if current.entity_type}<span class="tag">{current.entity_type}</span>{/if}
      {#if current.realm}<span class="tag">{current.realm}</span>{/if}
    </div>
    {#if current.description}
      <p class="descr">{current.description.slice(0, 220)}{current.description.length > 220 ? '…' : ''}</p>
    {/if}
    {#if current.cultural_associations.length}
      <div class="cultures ui">{current.cultural_associations.slice(0, 3).join(' · ')}</div>
    {/if}
  </div>
{/if}

<style>
  .preview {
    position: fixed;
    transform: translateX(-50%);
    width: min(360px, 90vw);
    background: var(--bg);
    color: var(--ink);
    border: 1px solid var(--rule);
    border-radius: var(--r-md);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
    padding: var(--sp-4);
    z-index: 300;
    pointer-events: none;
    animation: preview-in var(--dur-fast) var(--ease) both;
  }
  .name {
    font-family: var(--font-serif);
    font-size: var(--fs-lg);
    font-weight: 500;
    margin-bottom: 4px;
  }
  .meta {
    display: flex;
    gap: var(--sp-3);
    font-size: var(--fs-xs);
    color: var(--ink-faint);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: var(--sp-2);
  }
  .tag { color: var(--ink-dim); }
  .descr {
    color: var(--ink-dim);
    font-size: var(--fs-sm);
    line-height: 1.5;
    margin: 0;
  }
  .cultures {
    color: var(--ink-faint);
    font-size: var(--fs-xs);
    margin-top: var(--sp-2);
  }
  @keyframes preview-in {
    from { opacity: 0; transform: translateX(-50%) translateY(-4px); }
    to   { opacity: 1; transform: translateX(-50%) translateY(0); }
  }
</style>
