<script lang="ts">
  import { onMount } from 'svelte';

  const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');
  const link = (p: string) => BASE + p;

  let container: HTMLDivElement | null = $state(null);
  let status = $state('loading');
  let semanticOnly = $state(true);
  let maxNodes = $state(300);

  async function render() {
    if (!container) return;
    status = 'loading';
    try {
      const cytoscape = (await import('cytoscape')).default;
      const params = new URLSearchParams({
        max_nodes: String(maxNodes),
        rel_type: semanticOnly ? 'semantic' : 'all',
      });
      const resp = await fetch(`/graph/?${params}`);
      if (!resp.ok) throw new Error(`graph API ${resp.status}`);
      const payload = await resp.json();
      // API already returns Cytoscape-format {data: {...}}
      const rawNodes: any[] = payload.data?.nodes ?? payload.nodes ?? [];
      const rawEdges: any[] = payload.data?.edges ?? payload.edges ?? [];
      const nodes = rawNodes.map(n => ({ data: n.data ?? n }));
      const edges = rawEdges.map(e => ({ data: e.data ?? e }));

      const root = getComputedStyle(document.documentElement);
      const ink = root.getPropertyValue('--ink').trim();
      const inkDim = root.getPropertyValue('--ink-dim').trim();
      const inkFaint = root.getPropertyValue('--ink-faint').trim();
      const rule = root.getPropertyValue('--rule').trim();
      const bg = root.getPropertyValue('--bg').trim();

      // Destroy previous instance
      container.innerHTML = '';
      const cy = cytoscape({
        container,
        elements: [...nodes, ...edges],
        minZoom: 0.2,
        maxZoom: 3,
        style: [
          {
            selector: 'node',
            style: {
              'background-color': bg,
              'border-color': inkDim,
              'border-width': 1,
              'color': ink,
              'width': 8,
              'height': 8,
              'text-valign': 'bottom',
              'text-margin-y': 3,
              'min-zoomed-font-size': 7,
            },
          },
          {
            selector: 'node[label]',
            style: {
              'label': 'data(label)',
              'font-family': 'Fraunces Variable, serif',
              'font-size': 10,
            },
          },
          {
            selector: 'edge',
            style: {
              'width': 0.8,
              'line-color': rule,
              'target-arrow-color': rule,
              'target-arrow-shape': 'triangle',
              'arrow-scale': 0.6,
              'curve-style': 'bezier',
              'opacity': 0.75,
            },
          },
          {
            selector: 'node:selected',
            style: {
              'border-color': 'var(--accent)',
              'border-width': 2,
            },
          },
        ],
        layout: {
          name: 'cose',
          animate: false,
          padding: 20,
          nodeRepulsion: () => 3600,
          idealEdgeLength: () => 80,
          numIter: 1500,
        },
      });

      cy.on('tap', 'node', async (evt) => {
        const id = Number(evt.target.id());
        try {
          const resp = await fetch(`/entities/${id}`);
          if (!resp.ok) return;
          const { data } = await resp.json();
          const s = (data.name || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '')
            .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
          window.location.assign(link(`/entity/${s || id}/`));
        } catch { /* noop */ }
      });

      status = `${nodes.length} nodes, ${edges.length} edges`;
    } catch (err) {
      status = `failed: ${(err as Error).message}`;
    }
  }

  onMount(() => {
    render();
  });
</script>

<div class="controls ui">
  <label>
    <input type="checkbox" bind:checked={semanticOnly} onchange={render} />
    Typed relationships only
  </label>
  <label>
    Max nodes
    <input type="number" min="50" max="1000" step="50" bind:value={maxNodes} onchange={render} />
  </label>
  <span class="status">{status}</span>
</div>
<div class="graph" bind:this={container}></div>

<style>
  .controls {
    display: flex;
    align-items: center;
    gap: var(--sp-5);
    padding: var(--sp-3);
    border: 1px solid var(--rule);
    border-bottom: 0;
    border-radius: var(--r-md) var(--r-md) 0 0;
    background: var(--bg-alt);
    font-size: var(--fs-sm);
    color: var(--ink-dim);
    flex-wrap: wrap;
  }
  .controls label { display: flex; align-items: center; gap: var(--sp-2); }
  .controls input[type='number'] {
    width: 72px;
    padding: 2px 6px;
    border: 1px solid var(--rule);
    border-radius: var(--r-sm);
    background: var(--bg);
    color: var(--ink);
    font-family: var(--font-mono);
  }
  .status { margin-left: auto; color: var(--ink-faint); font-family: var(--font-mono); font-size: var(--fs-xs); }
  .graph {
    width: 100%;
    height: 72vh;
    border: 1px solid var(--rule);
    border-radius: 0 0 var(--r-md) var(--r-md);
    background: var(--bg-alt);
  }
</style>
