/** Build an internal URL respecting Astro's configured base path.
 *
 * Usage (in .astro / .svelte):
 *    import { url } from '../lib/url';
 *    <a href={url('/browse')}>Browse</a>
 *
 * With base='/app', `url('/browse')` → '/app/browse'.
 * With base='/',    `url('/browse')` → '/browse'.
 */
const BASE = import.meta.env.BASE_URL || '/';

export function url(path: string): string {
  if (!path.startsWith('/')) return BASE.replace(/\/$/, '') + '/' + path;
  const base = BASE.replace(/\/$/, ''); // drop trailing slash if any
  return base + path;
}

/** API paths are served by FastAPI at the server root — never under /app. */
export function apiUrl(path: string): string {
  return path; // same-origin, absolute from root
}
