// Shared helpers for the site Playwright suite.
const fs = require('fs');
const path = require('path');

const REPO_ROOT = path.resolve(__dirname, '..', '..');
const TILE_PNG = fs.readFileSync(path.join(__dirname, 'fixtures', 'tile.png'));

/** Read the real committed routes.json (not hard-coded counts). */
function readRoutesJson() {
  const raw = fs.readFileSync(path.join(REPO_ROOT, 'routes.json'), 'utf-8');
  return JSON.parse(raw);
}

/**
 * Mock every Mapy tile request with a canned local PNG — the tile
 * endpoint must never be hit for real in the saved suite (paid credits).
 * Also 404s config.local.js: a dev machine may have a real dev key
 * there, which would override injected test keys and flip the
 * keyless-baseline tests. The mocked suite must be hermetic.
 */
async function mockMapyTiles(page) {
  await page.route('**/config.local.js', (route) => {
    route.fulfill({ status: 404, contentType: 'text/plain', body: 'not found' });
  });
  // config.js on the deployed repo carries the real referrer-locked prod key;
  // stub it back to the placeholder so the keyless-baseline tests stay
  // hermetic regardless of repo state. injectFakeMapyKey() still wins: it
  // sets APP_CONFIG_LOCAL, which resolveMapyKey() prefers.
  await page.route('**/config.js', (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/javascript',
      body: "window.APP_CONFIG = { mapyKey: 'PROD_KEY_PENDING_DEPLOY' };",
    });
  });
  await page.route('https://api.mapy.com/v1/maptiles/**', (route) => {
    route.fulfill({ status: 200, contentType: 'image/png', body: TILE_PNG });
  });
}

/**
 * Sum of markercluster's cluster-badge counts + any un-clustered marker
 * icons — the cluster-aware way to assert "every route is represented on
 * the map". Real routes may legitimately cluster at the fit-all zoom (two
 * demo routes start ~220 m apart), so tests must not expect one
 * .leaflet-marker-icon per route.
 */
async function totalRenderedPins(page) {
  const clusterTexts = await page.locator('.marker-cluster').allTextContents();
  const clusterSum = clusterTexts.reduce((sum, t) => sum + (parseInt(t, 10) || 0), 0);
  const plainMarkers = await page.locator('.leaflet-marker-icon:not(.marker-cluster)').count();
  return clusterSum + plainMarkers;
}

/**
 * Click the first un-clustered route pin (.route-pin — never a cluster
 * badge, whose click only zooms) and return the selected route, looked up
 * from the #slug hash the selection set. Tests must not assume the first
 * marker in the DOM is routes[0]: markercluster's insertion order isn't
 * the routes.json order, and close-together routes cluster away entirely.
 */
async function clickFirstRoutePin(page, routes) {
  await page.locator('.route-pin').first().click();
  await page.waitForTimeout(600);
  const slug = await page.evaluate(() => decodeURIComponent(location.hash.slice(1)));
  const route = routes.routes.find((r) => r.slug === slug);
  if (!route) throw new Error(`clicked pin selected unknown slug "${slug}"`);
  return route;
}

/**
 * Inject a fake usable Mapy dev key before any page script runs, so the
 * tile layer actually gets added (site ships with only a placeholder
 * prod key, so by default no tile layer / requests happen at all).
 */
async function injectFakeMapyKey(page) {
  await page.addInitScript(() => {
    window.APP_CONFIG_LOCAL = { mapyKey: 'test-key' };
  });
}

module.exports = {
  REPO_ROOT,
  readRoutesJson,
  mockMapyTiles,
  injectFakeMapyKey,
  totalRenderedPins,
  clickFirstRoutePin,
};
