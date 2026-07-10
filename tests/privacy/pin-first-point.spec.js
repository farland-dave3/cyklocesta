// Privacy regression: each routes.json pin sits at the first *surviving*
// point of its GPX (the pipeline plants the pin post-trim, at the first
// point outside both endpoint-relative trim radii — open-questions #28)
// — never the real raw ride start.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const REPO_ROOT = path.resolve(__dirname, '..', '..');
const GPX_DIR = path.join(REPO_ROOT, 'gpx');

function firstTrkpt(gpxText) {
  const m = /<trkpt\s+lat="([^"]+)"\s+lon="([^"]+)"/.exec(gpxText);
  if (!m) return null;
  return { lat: parseFloat(m[1]), lon: parseFloat(m[2]) };
}

test.describe('pin == first surviving GPX point', () => {
  const routesJson = JSON.parse(fs.readFileSync(path.join(REPO_ROOT, 'routes.json'), 'utf-8'));

  test('sanity: routes.json has routes to check', () => {
    expect(routesJson.routes.length).toBeGreaterThan(0);
  });

  for (const route of routesJson.routes) {
    test(`${route.file}: pin matches the GPX file's first trackpoint`, () => {
      const gpxPath = path.join(GPX_DIR, route.file);
      expect(fs.existsSync(gpxPath), `${gpxPath} should exist`).toBe(true);
      const text = fs.readFileSync(gpxPath, 'utf-8');
      const first = firstTrkpt(text);
      expect(first, `${route.file} should have at least one trkpt`).not.toBeNull();

      // routes_index.py rounds to 6 decimals when building the pin.
      expect(route.pin[0]).toBeCloseTo(first.lat, 6);
      expect(route.pin[1]).toBeCloseTo(first.lon, 6);
    });
  }
});
