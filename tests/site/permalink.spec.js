// #slug permalink: draws + zooms the route on direct load; unknown slug is a no-op.
const { test, expect } = require('@playwright/test');
const { mockMapyTiles, injectFakeMapyKey, readRoutesJson, totalRenderedPins } = require('./helpers');

test.describe('permalink', () => {
  // Regression test for a cold-load permalink bug that was found and
  // fixed: opening index.html#<slug> as a genuinely fresh/cold load (the
  // real-world "someone opens a shared permalink" case) used to draw the
  // polyline and open the popup correctly, but leave the MAP VIEW at the
  // fit-all zoom instead of zooming to the selected route (fitAll() ran
  // synchronously on initial load, then selectRouteBySlug(initialSlug)'s
  // own map.fitBounds() — only applied later, inside the async gpx-fetch
  // .then() — lost the race). Fixed in app.js by skipping the initial
  // fitAll() when the hash already matches a known route. Verified via
  // tile z: route-level zoom (>=12ish) rather than the whole-country
  // fit-all zoom (~10 for these demo pins).
  test('opening /#<slug> directly (cold load) draws that route, shows it in the sidebar, and zooms to it (not fit-all)', async ({ page }) => {
    await mockMapyTiles(page);
    await injectFakeMapyKey(page); // so tile z can be read off request URLs as a zoom proxy
    const routes = readRoutesJson();
    const target = routes.routes[routes.routes.length - 1]; // any route away from index 0

    const tileZooms = [];
    page.on('request', (req) => {
      const m = req.url().match(/maptiles\/outdoor\/256\/(\d+)\//);
      if (m) tileZooms.push(parseInt(m[1], 10));
    });

    await page.goto(`/index.html#${target.slug}`);
    await page.waitForTimeout(1200);

    await expect(page.locator('path.leaflet-interactive')).toHaveCount(1);
    await expect(page.locator('#sidebar-name')).toHaveText(target.name);
    await expect(page.locator('#sidebar-distance')).toContainText(String(target.distance_km));
    // The date is only in the URL, never rendered on the page.
    await expect(page.locator('#route-sidebar')).not.toContainText(target.date);

    // Zoomed to the single route, not fit-all: other routes' pins should
    // be outside the (tight) viewport and pruned from the DOM by
    // markercluster's removeOutsideVisibleBounds.
    if (routes.routes.length > 1) {
      expect(await page.locator('.leaflet-marker-icon').count()).toBeLessThan(routes.routes.length);
    }
    // The tile zoom actually used should be a route-level zoom (>=12ish
    // for a ~10km route), clearly deeper than the whole-country fit-all
    // zoom (~10 for these demo pins).
    const finalZoom = tileZooms[tileZooms.length - 1];
    expect(finalZoom, `tile zoom levels requested: ${JSON.stringify(tileZooms)}`).toBeGreaterThan(10);
  });

  test('opening an unknown #slug does not crash and falls back to the default fit-all view', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (err) => errors.push(err));
    await mockMapyTiles(page);
    const routes = readRoutesJson();

    await page.goto('/index.html#nope-this-slug-does-not-exist');
    await page.waitForTimeout(1000);

    expect(errors).toEqual([]);
    await expect(page.locator('path.leaflet-interactive')).toHaveCount(0);
    await expect(page.locator('.leaflet-popup-content')).toHaveCount(0);
    // Header stays on the plain site title and the sidebar stays hidden for an
    // unknown slug.
    await expect(page.locator('#route-title')).toHaveText('Cyklocesta');
    await expect(page.locator('#route-sidebar')).toBeHidden();
    // Default fit-all view still renders every route — as its own pin or
    // inside a cluster badge (close routes cluster at the fit-all zoom).
    expect(await totalRenderedPins(page)).toBe(routes.routes.length);
  });

  test('same-hash re-selection (hash unchanged) still works via direct call path', async ({ page }) => {
    await mockMapyTiles(page);
    const routes = readRoutesJson();
    const target = routes.routes[0];

    await page.goto(`/index.html#${target.slug}`);
    await page.waitForTimeout(1000);
    await expect(page.locator('path.leaflet-interactive')).toHaveCount(1);

    // Re-set the identical hash via location.hash = slug (goToSlug()'s
    // "same hash won't fire hashchange" branch) -- should remain stable,
    // not duplicate the polyline.
    await page.evaluate((slug) => {
      window.location.hash = slug;
    }, target.slug);
    await page.waitForTimeout(400);
    await expect(page.locator('path.leaflet-interactive')).toHaveCount(1);
  });
});
