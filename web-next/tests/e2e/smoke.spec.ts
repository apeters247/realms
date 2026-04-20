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
