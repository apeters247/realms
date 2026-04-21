import { test, expect, type Page, type ConsoleMessage } from '@playwright/test';

/**
 * Diagnostic smoke suite. The site is mounted under /app/ — we route every
 * test through that prefix. Failures are grouped so the terminal output is
 * easy to triage.
 */

const PREFIX = '/app';

type Issue = {
  page: string;
  kind: 'console' | 'request' | 'visual' | 'semantics';
  detail: string;
};

function attachLoggers(page: Page, path: string, bucket: Issue[]) {
  page.on('console', (msg: ConsoleMessage) => {
    if (msg.type() === 'error' || msg.type() === 'warning') {
      bucket.push({ page: path, kind: 'console', detail: `[${msg.type()}] ${msg.text()}` });
    }
  });
  page.on('pageerror', (err) => {
    bucket.push({ page: path, kind: 'console', detail: `[pageerror] ${err.message}` });
  });
  page.on('requestfailed', (req) => {
    bucket.push({
      page: path,
      kind: 'request',
      detail: `${req.method()} ${req.url()} — ${req.failure()?.errorText ?? 'failed'}`,
    });
  });
  page.on('response', async (resp) => {
    if (resp.status() >= 400) {
      bucket.push({
        page: path,
        kind: 'request',
        detail: `HTTP ${resp.status()} ${resp.url()}`,
      });
    }
  });
}

async function visit(page: Page, path: string, issues: Issue[]) {
  attachLoggers(page, path, issues);
  await page.goto(`${PREFIX}${path}`, { waitUntil: 'networkidle' });
}

test.describe('smoke', () => {
  test('home page renders & no console errors', async ({ page }) => {
    const issues: Issue[] = [];
    await visit(page, '/', issues);
    await expect(page.locator('h1, .display').first()).toBeVisible();
    await expect(page).toHaveTitle(/REALMS/);

    // Screenshot for visual baseline
    await page.screenshot({ path: 'playwright-report/home.png', fullPage: true });

    // Check the nav renders
    const navBrand = page.locator('.brand-name').first();
    await expect(navBrand).toBeVisible();

    // Report issues
    if (issues.length) {
      console.log('\n=== HOME issues ===');
      for (const i of issues) console.log(`  [${i.kind}] ${i.detail}`);
    }
    expect.soft(issues.filter(i => i.kind === 'console')).toHaveLength(0);
    expect.soft(issues.filter(i => i.kind === 'request')).toHaveLength(0);
  });

  test('browse page renders entities', async ({ page }) => {
    const issues: Issue[] = [];
    await visit(page, '/browse/', issues);
    await expect(page.locator('h1').first()).toBeVisible();
    // Browse uses a dense name-list grouping by letter + type.
    const nameLinks = page.locator('.name-list li a');
    const count = await nameLinks.count();
    console.log(`browse: ${count} entity links`);
    expect(count).toBeGreaterThan(50);
    // Alpha nav anchors
    const alphas = page.locator('.alpha-rail .alpha');
    expect(await alphas.count()).toBeGreaterThan(5);
    await page.screenshot({ path: 'playwright-report/browse.png', fullPage: false });
    if (issues.length) {
      console.log('\n=== BROWSE issues ===');
      for (const i of issues) console.log(`  [${i.kind}] ${i.detail}`);
    }
    expect.soft(issues.filter(i => i.kind === 'console')).toHaveLength(0);
  });

  test('entity page layout + JSON-LD + sidenotes', async ({ page }) => {
    const issues: Issue[] = [];
    await visit(page, '/entity/chullachaqui/', issues);
    await expect(page.locator('h1')).toHaveText(/Chullachaqui/i);

    // Check structured data is present
    const jsonLd = await page.locator('script[type="application/ld+json"]').first().textContent();
    expect(jsonLd).toBeTruthy();
    const parsed = JSON.parse(jsonLd!);
    expect(parsed['@type']).toContain('Thing');
    expect(parsed.name).toBe('Chullachaqui');

    // Sidenotes (right column) must exist
    const sidenotes = page.locator('aside.sidenotes .sidenote');
    const snCount = await sidenotes.count();
    console.log(`entity: ${snCount} sidenotes`);
    expect(snCount).toBeGreaterThan(0);

    // Serif display font should be loaded (Fraunces)
    const h1Font = await page.locator('h1').first().evaluate((el) => getComputedStyle(el).fontFamily);
    console.log(`entity h1 fontFamily: ${h1Font}`);
    expect(h1Font.toLowerCase()).toMatch(/fraunces/);

    await page.screenshot({ path: 'playwright-report/entity.png', fullPage: true });

    if (issues.length) {
      console.log('\n=== ENTITY issues ===');
      for (const i of issues) console.log(`  [${i.kind}] ${i.detail}`);
    }
    expect.soft(issues.filter(i => i.kind === 'console' && !i.detail.includes('cytoscape'))).toHaveLength(0);
  });

  test('graph page loads Cytoscape', async ({ page }) => {
    const issues: Issue[] = [];
    await visit(page, '/graph/', issues);
    await expect(page.locator('h1')).toBeVisible();
    // Wait briefly for the island to mount
    await page.waitForTimeout(2500);
    await page.screenshot({ path: 'playwright-report/graph.png', fullPage: false });
    if (issues.length) {
      console.log('\n=== GRAPH issues ===');
      for (const i of issues) console.log(`  [${i.kind}] ${i.detail}`);
    }
  });

  test('timeline page', async ({ page }) => {
    const issues: Issue[] = [];
    await visit(page, '/timeline/', issues);
    await expect(page.locator('h1')).toBeVisible();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'playwright-report/timeline.png', fullPage: false });
    if (issues.length) {
      console.log('\n=== TIMELINE issues ===');
      for (const i of issues) console.log(`  [${i.kind}] ${i.detail}`);
    }
  });

  test('map page', async ({ page }) => {
    const issues: Issue[] = [];
    await visit(page, '/map/', issues);
    await expect(page.locator('h1')).toBeVisible();
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'playwright-report/map.png', fullPage: false });
    if (issues.length) {
      console.log('\n=== MAP issues ===');
      for (const i of issues) console.log(`  [${i.kind}] ${i.detail}`);
    }
  });

  test('search page', async ({ page }) => {
    const issues: Issue[] = [];
    await visit(page, '/search/', issues);
    await expect(page.locator('h1')).toBeVisible();
    if (issues.length) {
      console.log('\n=== SEARCH issues ===');
      for (const i of issues) console.log(`  [${i.kind}] ${i.detail}`);
    }
  });

  test('tradition page', async ({ page }) => {
    const issues: Issue[] = [];
    // Take the first tradition from the search index to avoid hard-coding
    const indexResp = await page.request.get(`${PREFIX}/search-index.json`);
    const idx = await indexResp.json();
    const t = idx.traditions?.[0];
    test.skip(!t, 'no tradition in index');
    await visit(page, `/tradition/${t.slug}/`, issues);
    await expect(page.locator('h1')).toBeVisible();
    if (issues.length) {
      console.log('\n=== TRADITION issues ===');
      for (const i of issues) console.log(`  [${i.kind}] ${i.detail}`);
    }
  });

  test('sources page', async ({ page }) => {
    const issues: Issue[] = [];
    await visit(page, '/sources/', issues);
    await expect(page.locator('h1')).toBeVisible();
    if (issues.length) {
      console.log('\n=== SOURCES issues ===');
      for (const i of issues) console.log(`  [${i.kind}] ${i.detail}`);
    }
  });

  test('about pages', async ({ page }) => {
    const issues: Issue[] = [];
    await visit(page, '/about/', issues);
    await expect(page.locator('h1')).toBeVisible();
    await visit(page, '/about/methodology/', issues);
    await expect(page.locator('h1')).toBeVisible();
    if (issues.length) {
      console.log('\n=== ABOUT issues ===');
      for (const i of issues) console.log(`  [${i.kind}] ${i.detail}`);
    }
  });

  test('command palette opens', async ({ page }) => {
    const issues: Issue[] = [];
    await visit(page, '/', issues);
    await page.keyboard.press('Control+KeyK');
    const palette = page.locator('[role="dialog"][aria-label="Command palette"]');
    await expect(palette).toBeVisible({ timeout: 3000 });
    await page.screenshot({ path: 'playwright-report/cmdk.png' });
  });

  test('source detail page', async ({ page }) => {
    const issues: Issue[] = [];
    await visit(page, '/source/1/', issues);
    await expect(page.locator('h1')).toBeVisible();
    // Should show the source-type chip and entities-extracted section
    await expect(page.locator('.source-type').first()).toBeVisible();
    await expect(page.locator('h2').filter({ hasText: /entities extracted/i })).toBeVisible();
    // At least one ingested entity listed
    const ents = page.locator('.ents li');
    const n = await ents.count();
    console.log(`source: ${n} ingested entities`);
    expect(n).toBeGreaterThan(0);
    if (issues.length) {
      console.log('\n=== SOURCE issues ===');
      for (const i of issues) console.log(`  [${i.kind}] ${i.detail}`);
    }
    expect.soft(issues.filter(i => i.kind === 'console')).toHaveLength(0);
  });

  test('researcher hub links to sub-pages', async ({ page }) => {
    const issues: Issue[] = [];
    await visit(page, '/researcher/', issues);
    await expect(page.locator('h1')).toHaveText(/Researcher/i);
    // Three hub tiles should be visible
    const tiles = page.locator('.hub .tile');
    expect(await tiles.count()).toBe(3);
    // Each should lead to /researcher/review|actions|link
    const hrefs = await tiles.evaluateAll(els => els.map(e => (e as HTMLAnchorElement).getAttribute('href')));
    expect(hrefs.some(h => h?.includes('/researcher/review'))).toBe(true);
    expect(hrefs.some(h => h?.includes('/researcher/actions'))).toBe(true);
    expect(hrefs.some(h => h?.includes('/researcher/link'))).toBe(true);
  });

  test('researcher/review page renders queue', async ({ page }) => {
    const issues: Issue[] = [];
    await visit(page, '/researcher/review/', issues);
    await expect(page.locator('h1')).toHaveText(/Review queue/i);
    // Give the island a moment to fetch
    await page.waitForTimeout(1500);
    // The controls section is rendered by the island
    await expect(page.locator('.controls')).toBeVisible({ timeout: 5000 });
  });

  test('researcher/actions page renders audit log', async ({ page }) => {
    const issues: Issue[] = [];
    await visit(page, '/researcher/actions/', issues);
    await expect(page.locator('h1')).toHaveText(/Audit log/i);
    await page.waitForTimeout(1500);
    await expect(page.locator('.controls')).toBeVisible({ timeout: 5000 });
  });

  test('researcher/link page renders linking table', async ({ page }) => {
    const issues: Issue[] = [];
    await visit(page, '/researcher/link/', issues);
    await expect(page.locator('h1')).toHaveText(/External identifier/i);
    await page.waitForTimeout(2000);
    // The controls section is rendered by the island once mounted
    await expect(page.locator('.controls')).toBeVisible({ timeout: 5000 });
  });

  test('collections index renders tiles', async ({ page }) => {
    const issues: Issue[] = [];
    await visit(page, '/collections/', issues);
    await expect(page.locator('h1')).toHaveText(/Collections/i);
    const tiles = page.locator('.grid .tile');
    const count = await tiles.count();
    console.log(`collections: ${count} tiles`);
    expect(count).toBeGreaterThanOrEqual(5);
    // Each tile has a link to /collection/{slug}/
    const hrefs = await tiles.evaluateAll(els => els.map(e => (e as HTMLAnchorElement).getAttribute('href')));
    expect(hrefs.every(h => h?.includes('/collection/'))).toBe(true);
    expect.soft(issues.filter(i => i.kind === 'console')).toHaveLength(0);
  });

  test('collection detail page lists members', async ({ page }) => {
    const issues: Issue[] = [];
    await visit(page, '/collection/solar-deities/', issues);
    await expect(page.locator('h1')).toHaveText(/Solar Deities/i);
    // Members (EntityCards) should exist
    await page.waitForTimeout(500);
  });

  test('entity page has Cite and Feedback actions', async ({ page }) => {
    const issues: Issue[] = [];
    await visit(page, '/entity/chullachaqui/', issues);
    // Cite button
    const cite = page.locator('.cite-trigger').first();
    await expect(cite).toBeVisible({ timeout: 5000 });
    // Feedback button
    const fb = page.locator('.fb-trigger').first();
    await expect(fb).toBeVisible({ timeout: 5000 });
    // Opening Cite modal fetches exports
    await cite.click();
    await expect(page.locator('.cite-modal')).toBeVisible({ timeout: 3000 });
    await expect(page.locator('.cite-modal h2')).toContainText(/Cite/i);
    // APA/MLA/Chicago prose citations render immediately
    const sections = page.locator('.cite-modal section.fmt');
    const n = await sections.count();
    console.log(`cite sections: ${n}`);
    expect(n).toBeGreaterThanOrEqual(3);
    // Close via Escape
    await page.keyboard.press('Escape');
    await expect(page.locator('.cite-modal')).toBeHidden();
  });

  test('citation export endpoints serve correct formats', async ({ request }) => {
    // BibTeX
    const bib = await request.get(`${PREFIX}/../export/entity/1.bib`.replace('/app/..', ''));
    // The export endpoint is at the root, not under /app/
    const bibResp = await request.get('/export/entity/1.bib');
    expect(bibResp.status()).toBe(200);
    const bibText = await bibResp.text();
    expect(bibText).toMatch(/@misc\{realms-/);
    expect(bibText).toMatch(/license\s*=\s*\{CC-BY-4\.0\}/);

    const cslResp = await request.get('/export/entity/1.csl.json');
    expect(cslResp.status()).toBe(200);
    const csl = await cslResp.json();
    expect(Array.isArray(csl)).toBe(true);
    expect(csl[0]).toHaveProperty('id');
    expect(csl[0]).toHaveProperty('title');

    const jsonResp = await request.get('/export/entity/1.json');
    expect(jsonResp.status()).toBe(200);
    const jsonPayload = await jsonResp.json();
    expect(jsonPayload.data).toHaveProperty('name');
    expect(jsonPayload.meta.license).toBe('CC-BY-4.0');
  });

  test('methodology page shows integrity badge', async ({ page }) => {
    const issues: Issue[] = [];
    await visit(page, '/about/methodology/', issues);
    await expect(page.locator('h1')).toHaveText(/Methodology/i);
    // Badge island should mount
    await page.waitForTimeout(1500);
    const badge = page.locator('.badge').first();
    await expect(badge).toBeVisible({ timeout: 5000 });
  });

  test('ethics page renders', async ({ page }) => {
    const issues: Issue[] = [];
    await visit(page, '/about/ethics/', issues);
    await expect(page.locator('h1')).toHaveText(/Ethics/i);
    await expect(page.locator('h2').first()).toBeVisible();
  });

  test('integrity API endpoints respond', async ({ request }) => {
    const r1 = await request.get('/integrity/stats');
    expect(r1.status()).toBe(200);
    const stats = await r1.json();
    expect(stats.data).toHaveProperty('integrity_score');
    expect(stats.data).toHaveProperty('window_days');

    const r2 = await request.get('/integrity/recent_audits?limit=5');
    expect(r2.status()).toBe(200);
  });

  test('feedback POST rejects short messages', async ({ request }) => {
    const resp = await request.post('/feedback', {
      data: { issue_type: 'typo', message: 'too short' },
      headers: { 'Content-Type': 'application/json' },
    });
    expect(resp.status()).toBeGreaterThanOrEqual(400);
  });

  test('feedback POST accepts valid messages', async ({ request }) => {
    const resp = await request.post('/feedback', {
      data: {
        entity_id: 1,
        issue_type: 'typo',
        message: 'Test submission from Playwright smoke — please ignore.',
      },
      headers: { 'Content-Type': 'application/json' },
    });
    expect(resp.status()).toBe(200);
    const payload = await resp.json();
    expect(payload.data.status).toMatch(/received|duplicate/);
  });

  test('changelog page renders weekly buckets', async ({ page }) => {
    const issues: Issue[] = [];
    await visit(page, '/changelog/', issues);
    await expect(page.locator('h1')).toHaveText(/Changelog/i);
    const weeks = page.locator('.week');
    const n = await weeks.count();
    console.log(`changelog weeks: ${n}`);
    expect(n).toBeGreaterThanOrEqual(1);
    expect.soft(issues.filter(i => i.kind === 'console')).toHaveLength(0);
  });

  test('changelog.rss serves valid RSS', async ({ request }) => {
    const r = await request.get('/changelog.rss');
    expect(r.status()).toBe(200);
    const text = await r.text();
    expect(text).toMatch(/<rss/);
    expect(text).toMatch(/<channel>/);
    expect(text).toMatch(/<item>/);
  });

  test('api-docs page renders sections', async ({ page }) => {
    const issues: Issue[] = [];
    await visit(page, '/api-docs/', issues);
    await expect(page.locator('h1')).toHaveText(/REALMS API/i);
    // Several endpoint sections
    const eps = page.locator('.ep');
    expect(await eps.count()).toBeGreaterThan(10);
    expect.soft(issues.filter(i => i.kind === 'console')).toHaveLength(0);
  });

  test('per-entity OG PNG renders at 1200×630', async ({ request }) => {
    const r = await request.get('/og/entity/1.png');
    expect(r.status()).toBe(200);
    const buf = await r.body();
    expect(buf.byteLength).toBeGreaterThan(1000);
    expect(r.headers()['content-type']).toContain('image/png');
    // PNG signature
    const sig = Array.from(buf.slice(0, 4));
    expect(sig).toEqual([0x89, 0x50, 0x4E, 0x47]);
  });

  test('default OG PNG exists', async ({ request }) => {
    const r = await request.get('/og/default.png');
    expect(r.status()).toBe(200);
    expect(r.headers()['content-type']).toContain('image/png');
  });

  test('entity page meta og:image points to PNG endpoint', async ({ page }) => {
    await visit(page, '/entity/chullachaqui/', []);
    const ogImage = await page.locator('meta[property="og:image"]').getAttribute('content');
    console.log(`og:image = ${ogImage}`);
    expect(ogImage).toMatch(/\/og\/entity\/\d+\.png/);
  });

  test('short-form permalink /e/{id} redirects', async ({ request }) => {
    const r = await request.get('/e/1', { maxRedirects: 0 });
    expect([301, 302]).toContain(r.status());
    const loc = r.headers()['location'];
    expect(loc).toMatch(/\/app\/entity\//);
  });

  test('homepage has integrity + collections sections', async ({ page }) => {
    const issues: Issue[] = [];
    await visit(page, '/', issues);
    // Integrity section heading
    await expect(page.locator('h2').filter({ hasText: /Integrity/i })).toBeVisible();
    // Collections section if any exist
    const colls = page.locator('.coll-grid .coll');
    const count = await colls.count();
    console.log(`home collections: ${count}`);
  });

  test('collections list API responds', async ({ request }) => {
    const r = await request.get('/collections/');
    expect(r.status()).toBe(200);
    const payload = await r.json();
    expect(Array.isArray(payload.data)).toBe(true);
    expect(payload.data.length).toBeGreaterThanOrEqual(5);
  });

  test('researcher routes are noindexed (robots disallow)', async ({ request }) => {
    const r = await request.get(`${PREFIX}/robots.txt`);
    const txt = await r.text();
    expect(txt).toMatch(/Disallow:\s*.*researcher/i);
  });

  test('robots + sitemap + feed present', async ({ request }) => {
    const r1 = await request.get(`${PREFIX}/robots.txt`);
    expect(r1.status()).toBe(200);
    const r1t = await r1.text();
    expect(r1t).toMatch(/User-agent:/);

    const r2 = await request.get(`${PREFIX}/sitemap-index.xml`);
    expect(r2.status()).toBe(200);
    expect(await r2.text()).toMatch(/<sitemapindex/);

    const r3 = await request.get(`${PREFIX}/feed.xml`);
    expect(r3.status()).toBe(200);

    const r4 = await request.get(`${PREFIX}/search-index.json`);
    expect(r4.status()).toBe(200);
    const idx = await r4.json();
    expect(idx.entities?.length).toBeGreaterThan(0);
  });
});
