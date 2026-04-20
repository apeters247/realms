<script lang="ts">
  import { onMount } from 'svelte';

  const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');
  const link = (p: string) => BASE + p;

  interface Props {
    centerId: number;
    depth?: number;
  }
  let { centerId, depth = 1 }: Props = $props();

  let container: HTMLDivElement | null = $state(null);
  let loaded = $state(false);
  let error = $state<string | null>(null);
  let empty = $state(false);

  onMount(async () => {
    if (!container) return;
    try {
      const cytoscape = (await import('cytoscape')).default;
      const resp = await fetch(`/graph/ego/${centerId}?depth=${depth}&semantic_only=true`);
      if (!resp.ok) throw new Error(`graph API ${resp.status}`);
      const payload = await resp.json();
      // API returns nodes/edges already in Cytoscape {data: {...}} shape.
      const rawNodes: any[] = payload.data?.nodes || [];
      const rawEdges: any[] = payload.data?.edges || [];
      const nodes = rawNodes.map(n => ({ data: n.data ?? n }));
      const edges = rawEdges.map(e => ({ data: e.data ?? e }));

      if (nodes.length <= 1) {
        empty = true;
        return;
      }

      const ink = getComputedStyle(document.documentElement).getPropertyValue('--ink').trim();
      const inkDim = getComputedStyle(document.documentElement).getPropertyValue('--ink-dim').trim();
      const inkFaint = getComputedStyle(document.documentElement).getPropertyValue('--ink-faint').trim();
      const accent = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim();
      const rule = getComputedStyle(document.documentElement).getPropertyValue('--rule').trim();
      const bg = getComputedStyle(document.documentElement).getPropertyValue('--bg').trim();

      const cy = cytoscape({
        container,
        elements: [...nodes, ...edges],
        minZoom: 0.4,
        maxZoom: 2.5,
        style: [
          {
            selector: 'node',
            style: {
              'background-color': bg,
              'border-width': 1,
              'border-color': inkDim,
              'color': ink,
              'text-valign': 'bottom',
              'text-margin-y': 4,
              'width': 10,
              'height': 10,
            },
          },
          {
            selector: 'node[label]',
            style: {
              'label': 'data(label)',
              'font-family': 'Fraunces Variable, serif',
              'font-size': 12,
            },
          },
          {
            selector: 'node[?is_center]',
            style: {
              'border-color': accent,
              'border-width': 2,
              'background-color': accent,
              'width': 16,
              'height': 16,
              'font-weight': 600,
            },
          },
          {
            selector: 'edge',
            style: {
              'width': 1,
              'line-color': rule,
              'target-arrow-color': rule,
              'target-arrow-shape': 'triangle',
              'arrow-scale': 0.8,
              'curve-style': 'bezier',
              'color': inkFaint,
            },
          },
          {
            selector: 'edge[rel_type]',
            style: {
              'label': 'data(rel_type)',
              'font-family': 'Inter Tight Variable, sans-serif',
              'font-size': 9,
              'text-background-color': bg,
              'text-background-opacity': 0.85,
              'text-background-padding': 2,
              'edge-text-rotation': 'autorotate',
            },
          },
        ],
        layout: {
          name: 'cose',
          animate: false,
          padding: 12,
          nodeRepulsion: () => 2600,
          idealEdgeLength: () => 60,
          gravity: 0.35,
          numIter: 700,
        },
      });

      cy.on('tap', 'node', (evt) => {
        const id = evt.target.id();
        if (Number(id) === centerId) return;
        window.dispatchEvent(new CustomEvent('realms:nav-entity', { detail: { id: Number(id) } }));
      });
      loaded = true;
    } catch (e) {
      error = (e as Error).message;
    }
  });

  // Handle node-tap: navigate to entity page by id. We resolve the slug via
  // the /entities/{id} endpoint which returns the canonical name, and the
  // server-provided `slug` field if present — otherwise fall back to id.
  onMount(() => {
    const handler = async (ev: Event) => {
      const id = (ev as CustomEvent<{ id: number }>).detail?.id;
      if (!id) return;
      try {
        const resp = await fetch(`/entities/${id}`);
        if (!resp.ok) return;
        const { data } = await resp.json();
        const slug = data.slug || slugify(data.name, id);
        window.location.assign(link(`/entity/${slug}/`));
      } catch {
        // noop
      }
    };
    window.addEventListener('realms:nav-entity', handler as EventListener);
    return () => window.removeEventListener('realms:nav-entity', handler as EventListener);
  });

  function slugify(name: string, id: number): string {
    const s = name.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
    return s ? s : String(id);
  }
</script>

<div class="wrap">
  <div class="graph" bind:this={container} class:hidden={empty}></div>
  {#if empty}
    <p class="empty ui">This entity has no typed relationships with other entries yet. Weak co-occurrence edges are hidden from the inline graph; see the full <a href={link('/graph/') + '?center=' + centerId}>Graph view</a>.</p>
  {/if}
  {#if error}<p class="err ui">could not load neighborhood graph: {error}</p>{/if}
</div>

<style>
  .wrap {
    border: 1px solid var(--rule);
    border-radius: var(--r-md);
    background: var(--bg-alt);
    overflow: hidden;
  }
  .graph {
    width: 100%;
    height: 360px;
  }
  .graph.hidden { display: none; }
  .empty, .err {
    padding: var(--sp-5);
    color: var(--ink-faint);
    font-size: var(--fs-sm);
    margin: 0;
    text-align: center;
    font-style: italic;
  }
  .empty a { color: var(--accent); }
</style>
