import type { APIRoute } from 'astro';
import { loadSnapshot } from '../lib/loader';
import { slugify } from '../lib/slug';

export const GET: APIRoute = async () => {
  const snap = await loadSnapshot();

  const entities = snap.entities.map(e => ({
    id: e.id,
    name: e.name,
    slug: snap.entitySlugById[e.id],
    entity_type: e.entity_type,
    realm: e.realm,
    culture: (e.cultural_associations || [])[0] || null,
    confidence: e.consensus_confidence ?? 0,
  }));

  const traditionNames = new Set<string>();
  for (const e of snap.entities) {
    for (const c of e.cultural_associations || []) traditionNames.add(c);
  }
  for (const t of snap.traditions) traditionNames.add(t.name);
  const traditions = [...traditionNames].map((n, idx) => ({
    id: `t${idx}`,
    name: n,
    slug: slugify(n),
  }));

  const regionNames = new Set<string>();
  for (const e of snap.entities) {
    for (const g of e.geographical_associations || []) regionNames.add(g);
  }
  for (const r of snap.regions) regionNames.add(r.name);
  const regions = [...regionNames].map((n, idx) => ({
    id: `r${idx}`,
    name: n,
    slug: slugify(n),
  }));

  return new Response(JSON.stringify({
    builtAt: snap.builtAt,
    entities,
    traditions,
    regions,
  }), {
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'public, max-age=300',
    },
  });
};
