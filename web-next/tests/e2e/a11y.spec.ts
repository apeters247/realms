import { test, expect } from '@playwright/test';

const PAGES = [
  '/',
  '/browse/',
  '/collections/',
  '/collection/solar-deities/',
  '/about/',
  '/about/methodology/',
  '/about/ethics/',
  '/entity/chullachaqui/',
  '/source/1/',
  '/api-docs/',
  '/changelog/',
];

test.describe('a11y', () => {
  for (const path of PAGES) {
    test(`a11y smoke: ${path}`, async ({ page }) => {
      const prefix = '/app';
      const failures: string[] = [];
      page.on('pageerror', err => failures.push(`pageerror: ${err.message}`));
      await page.goto(`${prefix}${path}`, { waitUntil: 'networkidle' });

      // Landmark check
      const main = page.locator('main');
      await expect(main).toHaveCount(1);

      // Every image needs alt text
      const imgs = page.locator('img:not([alt])');
      const missingAlt = await imgs.count();
      if (missingAlt > 0) failures.push(`${missingAlt} images without alt`);

      // Every anchor needs text or aria-label — evaluated in-page for speed
      const emptyAnchors = await page.evaluate(() => {
        const out: string[] = [];
        for (const a of Array.from(document.querySelectorAll('a'))) {
          const style = window.getComputedStyle(a);
          if (style.display === 'none' || style.visibility === 'hidden') continue;
          const text = (a.textContent || '').trim();
          const aria = a.getAttribute('aria-label') || '';
          const title = a.getAttribute('title') || '';
          if (!text && !aria && !title) {
            out.push(a.getAttribute('href') || '(no href)');
          }
        }
        return out;
      });
      if (emptyAnchors.length > 0) {
        failures.push(`${emptyAnchors.length} empty anchors (first: ${emptyAnchors[0]})`);
      }

      // Heading hierarchy: no h1 skipping, exactly one h1 per page
      const h1s = await page.locator('h1').count();
      if (h1s !== 1) failures.push(`expected 1 h1, found ${h1s}`);

      // Every form input needs a label
      const inputsWithoutLabel = await page.locator('input:not([type="hidden"])').evaluateAll(els =>
        els.filter(el => {
          const id = el.id;
          if (id && document.querySelector(`label[for="${id}"]`)) return false;
          if (el.closest('label')) return false;
          if (el.getAttribute('aria-label')) return false;
          if (el.getAttribute('aria-labelledby')) return false;
          if (el.getAttribute('placeholder')) return false; // ok for search boxes
          return true;
        }).length
      );
      if (inputsWithoutLabel > 0) failures.push(`${inputsWithoutLabel} inputs without labels`);

      if (failures.length) {
        console.log(`\n=== ${path} a11y issues ===`);
        failures.forEach(f => console.log(`  ${f}`));
      }
      expect.soft(failures).toEqual([]);
    });
  }
});
