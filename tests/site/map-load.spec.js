// Map init, Mapy attribution/logo, and the no-key banner.
//
// Mapy copyright attribution is unconditional (app.js calls
// map.attributionControl.addAttribution() at init regardless of
// key/tile-layer state), so "Seznam.cz" must appear in the Leaflet
// attribution control even with the placeholder key (no tile layer
// added, banner shown). The Mapy *logo* control is likewise always
// added. Both are asserted below in the keyless-default test; the
// fake-key test additionally confirms tiles + attribution together.
const { test, expect } = require('@playwright/test');
const { mockMapyTiles, injectFakeMapyKey } = require('./helpers');

test.describe('map load', () => {
  test('map container, markercluster layer, and Mapy logo control are present (keyless default)', async ({ page }) => {
    await mockMapyTiles(page);
    await page.goto('/index.html');

    await expect(page.locator('#map')).toBeVisible();
    await expect(page.locator('.leaflet-tile-pane')).toHaveCount(1);

    // Mapy logo control is mandatory and unconditional (CLAUDE.md).
    const logoLink = page.locator('.mapy-logo-control a');
    await expect(logoLink).toHaveAttribute('href', 'https://mapy.com/');
    const logoImg = logoLink.locator('img');
    await expect(logoImg).toHaveAttribute('src', 'lib/mapy/logo.svg');
  });

  test('no usable key -> key banner shown, no tile layer added, no tile requests fired', async ({ page }) => {
    await mockMapyTiles(page);
    let tileRequested = false;
    page.on('request', (req) => {
      if (req.url().includes('api.mapy.com/v1/maptiles')) tileRequested = true;
    });

    await page.goto('/index.html');
    await page.waitForTimeout(500);

    await expect(page.locator('#key-banner')).toBeVisible();
    expect(tileRequested).toBe(false);

    // Attribution is unconditional (see file-level comment): the Mapy
    // copyright text must be present even with no tile layer added.
    const attribution = await page.locator('.leaflet-control-attribution').innerHTML();
    expect(attribution).toContain('Seznam.cz');
  });

  test('usable key injected -> banner absent, tiles requested against the mocked Mapy outdoor endpoint, attribution text present', async ({ page }) => {
    await mockMapyTiles(page);
    await injectFakeMapyKey(page);

    const tileUrls = [];
    page.on('request', (req) => {
      if (req.url().includes('api.mapy.com/v1/maptiles')) tileUrls.push(req.url());
    });

    await page.goto('/index.html');
    await page.waitForTimeout(800);

    await expect(page.locator('#key-banner')).toBeHidden();
    expect(tileUrls.length).toBeGreaterThan(0);
    expect(tileUrls[0]).toMatch(/^https:\/\/api\.mapy\.com\/v1\/maptiles\/outdoor\/256\//);
    expect(tileUrls[0]).toContain('apikey=test-key');

    const attribution = await page.locator('.leaflet-control-attribution').innerHTML();
    expect(attribution).toContain('Seznam.cz');

    // Logo control still present alongside the copyright text.
    await expect(page.locator('.mapy-logo-control img')).toHaveAttribute('src', 'lib/mapy/logo.svg');
  });
});

// Exactly one opt-in real-tiles test, skipped by default (no CI, and
// mocked tiles are the norm to avoid burning paid Mapy credits). Run
// deliberately with: MAPY_DEV_KEY=xxx REAL_TILES=1 npx playwright test map-load
test.describe('real tiles (opt-in, verifies against the live Mapy endpoint)', () => {
  test.skip(!process.env.REAL_TILES || !process.env.MAPY_DEV_KEY, 'set REAL_TILES=1 and MAPY_DEV_KEY=<key> to run this against real Mapy servers');

  test('real Mapy outdoor tiles load with a real dev key (burns credits — opt-in only)', async ({ page }) => {
    await page.addInitScript((key) => {
      window.APP_CONFIG_LOCAL = { mapyKey: key };
    }, process.env.MAPY_DEV_KEY);

    const responses = [];
    page.on('response', (res) => {
      if (res.url().includes('api.mapy.com/v1/maptiles')) responses.push(res);
    });

    await page.goto('/index.html');
    await page.waitForTimeout(2000);

    expect(responses.length).toBeGreaterThan(0);
    expect(responses[0].status()).toBe(200);
    await expect(page.locator('#key-banner')).toBeHidden();
    const attribution = await page.locator('.leaflet-control-attribution').innerHTML();
    expect(attribution).toContain('Seznam.cz');
  });
});
