<script lang="ts">
  import { onMount } from 'svelte';

  const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');
  const link = (p: string) => BASE + p;

  let container: HTMLDivElement | null = $state(null);
  let status = $state('loading');

  onMount(async () => {
    if (!container) return;
    try {
      const L = (await import('leaflet')).default;
      await import('leaflet/dist/leaflet.css');
      const resp = await fetch('/regions/?per_page=100');
      if (!resp.ok) throw new Error(`regions API ${resp.status}`);
      const payload = await resp.json();
      const regions = (payload.data || []).filter(
        (r: any) => typeof r.center_latitude === 'number' && typeof r.center_longitude === 'number',
      );

      const map = L.map(container, {
        center: [20, 0],
        zoom: 2,
        zoomControl: true,
        scrollWheelZoom: true,
        attributionControl: true,
      });
      // Minimal muted tile set — CartoDB Positron (attribution required)
      L.tileLayer('https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> · <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 9,
      }).addTo(map);

      const root = getComputedStyle(document.documentElement);
      const accent = root.getPropertyValue('--accent').trim();
      const inkDim = root.getPropertyValue('--ink-dim').trim();

      for (const r of regions) {
        const circle = L.circleMarker([r.center_latitude, r.center_longitude], {
          radius: 6,
          color: inkDim,
          weight: 1,
          fillColor: accent,
          fillOpacity: 0.5,
        }).addTo(map);
        const slug = (r.name || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '')
          .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
        circle.bindPopup(
          `<strong>${r.name}</strong><br>
           <span style="color:var(--ink-faint);font-size:12px">${(r.countries || []).slice(0, 3).join(', ')}</span><br>
           <a href="${link(`/region/${slug}/`)}">View entities →</a>`
        );
      }
      status = `${regions.length} regions`;
    } catch (err) {
      status = `failed: ${(err as Error).message}`;
    }
  });
</script>

<div class="status ui">{status}</div>
<div class="map" bind:this={container}></div>

<style>
  .status {
    padding: var(--sp-2) var(--sp-4);
    border: 1px solid var(--rule);
    border-bottom: 0;
    background: var(--bg-alt);
    color: var(--ink-faint);
    font-size: var(--fs-xs);
    border-radius: var(--r-md) var(--r-md) 0 0;
  }
  .map {
    width: 100%;
    height: 72vh;
    border: 1px solid var(--rule);
    border-radius: 0 0 var(--r-md) var(--r-md);
    background: var(--bg-alt);
  }
  :global(.leaflet-container) {
    background: var(--bg-alt) !important;
    font-family: var(--font-sans) !important;
  }
  :global(.leaflet-popup-content-wrapper) {
    background: var(--bg) !important;
    color: var(--ink) !important;
    border-radius: var(--r-md) !important;
  }
  :global(.leaflet-popup-tip) { background: var(--bg) !important; }
</style>
