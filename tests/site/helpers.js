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
  await page.route('https://api.mapy.com/v1/maptiles/**', (route) => {
    route.fulfill({ status: 200, contentType: 'image/png', body: TILE_PNG });
  });
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

module.exports = { REPO_ROOT, readRoutesJson, mockMapyTiles, injectFakeMapyKey };
