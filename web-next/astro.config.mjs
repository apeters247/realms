// @ts-check
import { defineConfig } from 'astro/config';
import svelte from '@astrojs/svelte';
import sitemap from '@astrojs/sitemap';
import tailwindcss from '@tailwindcss/vite';

const SITE = process.env.REALMS_PUBLIC_ORIGIN || 'http://127.0.0.1:8004';
const BASE = process.env.REALMS_BASE_PATH || '/app';

export default defineConfig({
  site: SITE,
  base: BASE,
  trailingSlash: 'always',
  output: 'static',
  compressHTML: true,
  prefetch: {
    prefetchAll: false,
    defaultStrategy: 'viewport',
  },
  integrations: [
    svelte(),
    sitemap({
      // Researcher routes stay out of the public index.
      filter: (page) => !page.includes('/researcher'),
    }),
  ],
  vite: {
    plugins: [tailwindcss()],
    ssr: {
      noExternal: ['cytoscape', 'd3', 'leaflet'],
    },
  },
  experimental: {
    clientPrerender: true,
  },
});
