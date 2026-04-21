/**
 * Visual audit — full-page screenshots at multiple viewports. Not a test so
 * much as a diagnostic: we spit images into playwright-report/visual-audit/
 * so the whole UI can be reviewed at a glance after each build.
 */
import { test } from '@playwright/test';

const PAGES = [
  { path: '/', name: 'home' },
  { path: '/browse/', name: 'browse' },
  { path: '/entity/chullachaqui/', name: 'entity-single-source' },
  { path: '/entity/osun/', name: 'entity-rich' },
  { path: '/entity/jesus-christ/', name: 'entity-popular' },
  { path: '/entity/fire/', name: 'entity-short-name' },
  { path: '/graph/', name: 'graph' },
  { path: '/timeline/', name: 'timeline' },
  { path: '/map/', name: 'map' },
  { path: '/sources/', name: 'sources' },
  { path: '/about/', name: 'about' },
  { path: '/about/methodology/', name: 'methodology' },
  { path: '/about/cite/', name: 'cite' },
  { path: '/tradition/yoruba/', name: 'tradition-yoruba' },
  { path: '/search/', name: 'search' },
  { path: '/researcher/', name: 'researcher' },
  { path: '/researcher/review/', name: 'researcher-review' },
  { path: '/researcher/actions/', name: 'researcher-actions' },
  { path: '/researcher/link/', name: 'researcher-link' },
  { path: '/source/1/', name: 'source-detail' },
  { path: '/collections/', name: 'collections-index' },
  { path: '/collection/solar-deities/', name: 'collection-solar' },
  { path: '/collection/death-psychopomps/', name: 'collection-psychopomps' },
  { path: '/about/ethics/', name: 'ethics' },
];

const VIEWPORTS = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'tablet', width: 900, height: 1024 },
  { name: 'mobile', width: 390, height: 844 },
];

for (const v of VIEWPORTS) {
  test.describe(`visual-audit @ ${v.name} ${v.width}x${v.height}`, () => {
    for (const p of PAGES) {
      test(`${p.name}`, async ({ page }) => {
        page.setViewportSize({ width: v.width, height: v.height });
        try {
          await page.goto(`/app${p.path}`, { waitUntil: 'networkidle', timeout: 12_000 });
          // Let islands mount + layout settle
          await page.waitForTimeout(1500);
        } catch (err) {
          // Continue to take a screenshot even on timeout — often still renders
        }
        await page.screenshot({
          path: `playwright-report/visual-audit/${v.name}-${p.name}.png`,
          fullPage: true,
        });
      });
    }
  });
}
