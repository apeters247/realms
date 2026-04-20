export function slugify(input: string): string {
  if (!input) return '';
  const base = input
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '') // strip combining diacritics
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80);
  return base || 'entity';
}

/** Deterministic slug with id suffix on collisions. */
export function slugWithId(name: string, id: number, seen: Map<string, number>): string {
  const base = slugify(name);
  if (!seen.has(base)) {
    seen.set(base, id);
    return base;
  }
  return `${base}-${id}`;
}
