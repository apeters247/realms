import rss from '@astrojs/rss';
import type { APIRoute } from 'astro';
import { loadSnapshot } from '../lib/loader';

export const GET: APIRoute = async (context) => {
  const snap = await loadSnapshot();
  const recent = snap.entities
    .slice()
    .sort((a, b) => b.id - a.id)
    .slice(0, 50);
  const site = context.site ?? new URL('http://127.0.0.1:8004');

  return rss({
    title: 'REALMS — recent entities',
    description:
      'Recently-added or updated spiritual entities in the Research Entity Archive for Light & Metaphysical Spirit Hierarchies.',
    site,
    items: recent.map(e => ({
      title: e.name,
      link: `/entity/${snap.entitySlugById[e.id]}`,
      description: (e.description || '').slice(0, 300),
      pubDate: new Date(),
      customData: `<category>${e.entity_type || 'entity'}</category>`,
    })),
  });
};
