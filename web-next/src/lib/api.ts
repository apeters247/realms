/** Typed fetch wrapper against the realms FastAPI.
 *  Used both at build time (SSG) and at runtime (browser) for fresh data. */

const DEFAULT_ORIGIN = 'http://127.0.0.1:8005';

export function apiOrigin(): string {
  // Build-time: use env var (set by Dockerfile to talk to realms-api container).
  if (typeof process !== 'undefined' && process.env?.REALMS_API_ORIGIN) {
    return process.env.REALMS_API_ORIGIN;
  }
  // Browser runtime: same origin as the deployed static site.
  if (typeof window !== 'undefined') {
    return window.location.origin;
  }
  return DEFAULT_ORIGIN;
}

async function _sleep(ms: number): Promise<void> {
  return new Promise(r => setTimeout(r, ms));
}

export async function api<T = unknown>(path: string, init: RequestInit = {}): Promise<T> {
  const url = path.startsWith('http') ? path : `${apiOrigin()}${path}`;
  // Rate-limit aware with up to 4 retries on 429 / 5xx.
  let lastStatus = 0;
  for (let attempt = 0; attempt < 5; attempt++) {
    const resp = await fetch(url, {
      ...init,
      headers: {
        accept: 'application/json',
        ...(init.headers || {}),
      },
    });
    if (resp.ok) return resp.json() as Promise<T>;
    lastStatus = resp.status;
    if (resp.status === 429 || resp.status >= 500) {
      // Exponential backoff: 0.5s, 1s, 2s, 4s, 8s.
      const delay = 500 * Math.pow(2, attempt) + Math.floor(Math.random() * 200);
      if (attempt < 4) {
        await _sleep(delay);
        continue;
      }
    }
    throw new Error(`API ${resp.status} ${resp.statusText} on ${path}`);
  }
  throw new Error(`API retries exhausted (last=${lastStatus}) on ${path}`);
}

/** Iterate a paginated endpoint until exhausted.
 *  Assumes the server returns { data: T[], pagination: { page, total_pages } }. */
export async function apiAll<T>(path: string, perPage = 100): Promise<T[]> {
  const all: T[] = [];
  let page = 1;
  for (;;) {
    const qs = path.includes('?') ? '&' : '?';
    const url = `${path}${qs}page=${page}&per_page=${perPage}`;
    const payload = await api<{ data: T[]; pagination?: { total_pages?: number; page?: number } }>(url);
    const rows = Array.isArray(payload.data) ? payload.data : [];
    all.push(...rows);
    const tp = payload.pagination?.total_pages ?? 1;
    if (page >= tp || rows.length === 0) break;
    page += 1;
    if (page > 500) break; // hard cap
    // Gentle pacing at build time to avoid tripping the server's rate limiter.
    if (page % 10 === 0) {
      await _sleep(120);
    }
  }
  return all;
}
