import type { Corroboration, EntityDetail } from './types';

function authorsList(a: unknown): unknown[] {
  if (!a) return [];
  if (Array.isArray(a)) {
    return a.map(x => {
      if (typeof x === 'string') return { '@type': 'Person', name: x };
      if (x && typeof x === 'object' && 'name' in x) return { '@type': 'Person', name: String((x as { name: string }).name) };
      return null;
    }).filter(Boolean) as unknown[];
  }
  return [];
}

export function entityJsonLd(
  entity: EntityDetail,
  corroboration: Corroboration | null,
  canonicalUrl: string,
  siteUrl: string,
): Record<string, unknown> {
  const altNames: string[] = Object.values(entity.alternate_names || {}).flat();
  const sameAs: string[] = [];
  const ext = entity.external_ids || {};
  if (ext.wikidata) sameAs.push(`https://www.wikidata.org/wiki/${ext.wikidata}`);
  if (ext.viaf) sameAs.push(`https://viaf.org/viaf/${ext.viaf}`);
  if (ext.wordnet) sameAs.push(`http://wordnet-rdf.princeton.edu/lemma/${ext.wordnet}`);
  if (ext.geonames) sameAs.push(`https://www.geonames.org/${ext.geonames}`);

  const citations: unknown[] = [];
  if (corroboration?.sources_by_type) {
    for (const list of Object.values(corroboration.sources_by_type)) {
      for (const s of list) {
        citations.push({
          '@type': s.peer_reviewed ? 'ScholarlyArticle' : 'CreativeWork',
          name: s.source_name,
          datePublished: s.publication_year ? String(s.publication_year) : undefined,
          url: s.url ?? undefined,
          author: authorsList(s.authors),
          ...(s.doi ? { identifier: `doi:${s.doi}` } : {}),
        });
      }
    }
  } else if (entity.sources) {
    for (const s of entity.sources) {
      citations.push({
        '@type': 'CreativeWork',
        name: s.source_name,
        datePublished: s.publication_year ? String(s.publication_year) : undefined,
      });
    }
  }

  const descriptionTrim = (entity.description || '').replace(/\s+/g, ' ').trim().slice(0, 320);

  return {
    '@context': 'https://schema.org',
    '@type': ['Thing', 'CreativeWork'],
    '@id': canonicalUrl,
    url: canonicalUrl,
    name: entity.name,
    alternateName: altNames.length ? altNames : undefined,
    description: descriptionTrim || undefined,
    sameAs: sameAs.length ? sameAs : undefined,
    identifier: [
      { '@type': 'PropertyValue', propertyID: 'REALMS', value: String(entity.id) },
      ...(ext.wikidata ? [{ '@type': 'PropertyValue', propertyID: 'Wikidata', value: ext.wikidata }] : []),
      ...(ext.viaf ? [{ '@type': 'PropertyValue', propertyID: 'VIAF', value: ext.viaf }] : []),
    ],
    citation: citations.length ? citations : undefined,
    isPartOf: {
      '@type': 'Dataset',
      name: 'REALMS — Research Entity Archive for Light & Metaphysical Spirit Hierarchies',
      url: siteUrl,
      license: 'https://creativecommons.org/licenses/by/4.0/',
    },
    dateModified: entity.updated_at,
    dateCreated: entity.created_at,
  };
}

export function breadcrumbJsonLd(items: Array<{ name: string; url: string }>): Record<string, unknown> {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((it, idx) => ({
      '@type': 'ListItem',
      position: idx + 1,
      name: it.name,
      item: it.url,
    })),
  };
}

export function websiteJsonLd(siteUrl: string): Record<string, unknown> {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: 'REALMS',
    alternateName: 'Research Entity Archive for Light & Metaphysical Spirit Hierarchies',
    url: siteUrl,
    potentialAction: {
      '@type': 'SearchAction',
      target: {
        '@type': 'EntryPoint',
        urlTemplate: `${siteUrl.replace(/\/$/, '')}/search?q={search_term_string}`,
      },
      'query-input': 'required name=search_term_string',
    },
  };
}
