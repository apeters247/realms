/** Build-time snapshot of the entire knowledge base.
 *  Every page that needs lots of data should call `loadSnapshot()` and read
 *  from the cached value so we make at most one API pass per build. */

import fs from 'node:fs';
import path from 'node:path';
import { api, apiAll } from './api';
import { slugWithId } from './slug';
import type { EntityDetail, EntitySummary, Tradition, Region } from './types';

export interface Snapshot {
  builtAt: string;
  entities: EntitySummary[];
  entityById: Record<number, EntitySummary>;
  entityBySlug: Record<string, EntitySummary>;
  entitySlugById: Record<number, string>;
  traditions: Tradition[];
  traditionBySlug: Record<string, Tradition>;
  regions: Region[];
  regionBySlug: Record<string, Region>;
}

const CACHE_DIR = path.resolve('.astro-cache');
const CACHE_FILE = path.join(CACHE_DIR, 'realms-snapshot.json');
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 min during dev

let memCache: Snapshot | null = null;

function readDiskCache(): Snapshot | null {
  try {
    if (!fs.existsSync(CACHE_FILE)) return null;
    const stat = fs.statSync(CACHE_FILE);
    if (Date.now() - stat.mtimeMs > CACHE_TTL_MS) return null;
    const raw = fs.readFileSync(CACHE_FILE, 'utf8');
    return JSON.parse(raw) as Snapshot;
  } catch {
    return null;
  }
}

function writeDiskCache(snap: Snapshot): void {
  try {
    fs.mkdirSync(CACHE_DIR, { recursive: true });
    fs.writeFileSync(CACHE_FILE, JSON.stringify(snap));
  } catch (err) {
    console.warn('[realms.loader] could not write disk cache:', err);
  }
}

export async function loadSnapshot(opts: { refresh?: boolean } = {}): Promise<Snapshot> {
  if (!opts.refresh) {
    if (memCache) return memCache;
    const disk = readDiskCache();
    if (disk) {
      memCache = disk;
      return disk;
    }
  }

  console.info('[realms.loader] fetching fresh snapshot from API');
  let entities: EntitySummary[];
  let traditions: Tradition[];
  let regions: Region[];
  try {
    [entities, traditions, regions] = await Promise.all([
      apiAll<EntitySummary>('/entities/', 100),
      apiAll<Tradition>('/cultures/', 100),
      apiAll<Region>('/regions/', 100),
    ]);
  } catch (err) {
    console.warn('[realms.loader] API fetch failed, building empty snapshot:', err);
    entities = [];
    traditions = [];
    regions = [];
  }

  const seen = new Map<string, number>();
  const entitySlugById: Record<number, string> = {};
  for (const e of entities) {
    entitySlugById[e.id] = slugWithId(e.name, e.id, seen);
  }
  const entityBySlug: Record<string, EntitySummary> = {};
  const entityById: Record<number, EntitySummary> = {};
  for (const e of entities) {
    entityById[e.id] = e;
    entityBySlug[entitySlugById[e.id]] = e;
  }

  const tseen = new Map<string, number>();
  const traditionBySlug: Record<string, Tradition> = {};
  for (const t of traditions) {
    const s = slugWithId(t.name, t.id, tseen);
    (t as unknown as { slug: string }).slug = s;
    traditionBySlug[s] = t;
  }

  const rseen = new Map<string, number>();
  const regionBySlug: Record<string, Region> = {};
  for (const r of regions) {
    const s = slugWithId(r.name, r.id, rseen);
    (r as unknown as { slug: string }).slug = s;
    regionBySlug[s] = r;
  }

  const snap: Snapshot = {
    builtAt: new Date().toISOString(),
    entities,
    entityById,
    entityBySlug,
    entitySlugById,
    traditions,
    traditionBySlug,
    regions,
    regionBySlug,
  };

  writeDiskCache(snap);
  memCache = snap;
  return snap;
}

/** Fetch full detail for a single entity at build time. */
export async function loadEntityDetail(id: number): Promise<EntityDetail | null> {
  try {
    const payload = await api<{ data: EntityDetail }>(`/entities/${id}`);
    return payload.data;
  } catch (err) {
    console.warn(`[realms.loader] detail fetch failed for entity ${id}:`, err);
    return null;
  }
}
