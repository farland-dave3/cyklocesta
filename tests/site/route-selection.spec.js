// Single-route draw (new replaces old), header stats, fit-all default.
//
// Note on test design: the demo routes are allowed to cluster at the
// fit-all zoom (two of them start ~220 m apart and DO cluster there), so
// tests click `.route-pin` (a real un-clustered pin, never a cluster
// badge) and look the selected route up from the #slug hash instead of
// assuming DOM order matches routes.json. Selecting a route calls
// map.fitBounds() to that route's (tight) polyline bounds; markercluster's
// default removeOutsideVisibleBounds then removes the other routes'
// markers from the DOM while that tight view is showing. There is no
// deselect control any more — the only way to change state is to click a
// different pin. Because a second pin isn't clickable while zoomed into
// the first route's tight bounds, "new selection replaces old" is
// exercised via one real pointer click (first selection) followed by a
// direct hash change (equivalent code path to a permalink click) for the
// second selection. The zoom-out/re-fit tests select the route whose pin
// is farthest from every other pin, so zooming out a few steps can't
// swallow it into a cluster.
const { test, expect } = require('@playwright/test');
const {
  mockMapyTiles,
  injectFakeMapyKey,
  readRoutesJson,
  totalRenderedPins,
  clickFirstRoutePin,
} = require('./helpers');

/** Route whose pin has the greatest distance to its nearest neighbour. */
function mostIsolatedRoute(routes) {
  const d2 = (a, b) => (a.pin[0] - b.pin[0]) ** 2 + (a.pin[1] - b.pin[1]) ** 2;
  let best = routes.routes[0];
  let bestMin = -1;
  for (const r of routes.routes) {
    let min = Infinity;
    for (const o of routes.routes) if (o !== r) min = Math.min(min, d2(r, o));
    if (min > bestMin) {
      bestMin = min;
      best = r;
    }
  }
  return best;
}

test.describe('fit-all default view', () => {
  test('landing view fits all pins (all markers rendered, none clustered away)', async ({ page }) => {
    await mockMapyTiles(page);
    const routes = readRoutesJson();

    await page.goto('/index.html');
    await page.waitForTimeout(800);

    // Every route is represented on the default landing view — as its own
    // pin or inside a cluster badge (close-together routes legitimately
    // cluster at the fit-all zoom); nothing is cut off outside the viewport.
    expect(await totalRenderedPins(page)).toBe(routes.routes.length);
    await expect(page.locator('path.leaflet-interactive')).toHaveCount(0); // no route drawn yet
    await expect(page.locator('#status-note')).toBeHidden();

    // Header keeps the plain site title; the route sidebar stays hidden until
    // a route is picked.
    await expect(page.locator('#route-title')).toHaveText('Cyklocesta');
    await expect(page.locator('#route-sidebar')).toBeHidden();
  });
});

test.describe('route selection: draw, header, replace', () => {
  test('clicking a pin draws exactly one polyline and shows the route in the sidebar', async ({ page }) => {
    await mockMapyTiles(page);
    const routes = readRoutesJson();

    await page.goto('/index.html');
    await page.waitForTimeout(800);

    const expected = await clickFirstRoutePin(page, routes);

    await expect(page.locator('path.leaflet-interactive')).toHaveCount(1);

    // No popup — the route lives in the sidebar.
    await expect(page.locator('.leaflet-popup-content')).toHaveCount(0);

    const sidebar = page.locator('#route-sidebar');
    await expect(sidebar).toBeVisible();
    await expect(page.locator('#sidebar-name')).toHaveText(expected.name);
    await expect(page.locator('#sidebar-distance')).toContainText(String(expected.distance_km));
    await expect(page.locator('#sidebar-elevation')).toContainText(String(expected.elevation_m));
    // The date is never shown on the page — it lives only in the #slug.
    await expect(sidebar).not.toContainText(expected.date);

    // hash permalink updates to match selection
    expect(await page.evaluate(() => location.hash)).toBe('#' + expected.slug);
  });

  test('selecting a different route replaces the polyline (no overlay) and updates the sidebar', async ({ page }) => {
    await mockMapyTiles(page);
    const routes = readRoutesJson();
    test.skip(routes.routes.length < 2, 'need at least 2 routes to test replacement');

    await page.goto('/index.html');
    await page.waitForTimeout(800);

    // First selection: a real pointer click on a marker.
    const first = await clickFirstRoutePin(page, routes);
    await expect(page.locator('path.leaflet-interactive')).toHaveCount(1);
    await expect(page.locator('#sidebar-name')).toHaveText(first.name);

    // Second selection via hash change (same selectRouteBySlug() code
    // path a click ultimately drives) — see file-level note on why a
    // second real marker click isn't reliably available here.
    const second = routes.routes.find((r) => r.slug !== first.slug);
    await page.evaluate((slug) => {
      location.hash = slug;
    }, second.slug);
    await page.waitForTimeout(600);

    // Still exactly one polyline (replaced, not overlaid).
    await expect(page.locator('path.leaflet-interactive')).toHaveCount(1);
    // Sidebar swapped to the second route.
    await expect(page.locator('#sidebar-name')).toHaveText(second.name);
    await expect(page.locator('#sidebar-name')).not.toHaveText(first.name);
  });

  // Regression: re-clicking the already-selected route used to no-op
  // (selectRouteBySlug returned early on slug === currentSlug), so the map
  // never recentered. It must now re-fit at any zoom — fitBounds zooms IN
  // when too far out. Tile zoom (read off request URLs) is the zoom proxy,
  // same technique as permalink.spec.js.
  test('re-clicking the selected route re-fits the map (zooms back in from a too-far view)', async ({ page }) => {
    await mockMapyTiles(page);
    await injectFakeMapyKey(page); // so tiles load and their z reveals the zoom
    const routes = readRoutesJson();

    const tileZooms = [];
    page.on('request', (req) => {
      const m = req.url().match(/maptiles\/outdoor\/256\/(\d+)\//);
      if (m) tileZooms.push(parseInt(m[1], 10));
    });
    const lastZoom = () => tileZooms[tileZooms.length - 1];

    // Select the most isolated route (via hash — same selectRouteBySlug()
    // path as a click), so zooming out can't recluster its pin away.
    const target = mostIsolatedRoute(routes);
    await page.goto(`/index.html#${target.slug}`);
    await page.waitForTimeout(1200);
    const fitZoom = lastZoom();

    // Zoom out (too far to fit the route), keeping the pin on screen.
    for (let i = 0; i < 3; i++) {
      await page.locator('.leaflet-control-zoom-out').click();
      await page.waitForTimeout(300);
    }
    const tooFar = lastZoom();
    expect(tooFar).toBeLessThan(fitZoom);
    await expect(page.locator('.route-pin.is-selected')).toBeVisible();

    // Re-click the same pin -> re-fit -> zoom back in to the route.
    await page.locator('.route-pin.is-selected').click();
    await page.waitForTimeout(700);
    const refit = lastZoom();
    expect(refit).toBeGreaterThan(tooFar);
    expect(Math.abs(refit - fitZoom)).toBeLessThanOrEqual(1);
    // Still exactly one polyline (no duplicate draw on re-select).
    await expect(page.locator('path.leaflet-interactive')).toHaveCount(1);
  });

  // Zoom-to-fit must work when clicking the drawn route line, not only the pin.
  test('clicking the route polyline re-fits the map (zooms back in from a too-far view)', async ({ page }) => {
    await mockMapyTiles(page);
    await injectFakeMapyKey(page);
    const routes = readRoutesJson();

    const tileZooms = [];
    page.on('request', (req) => {
      const m = req.url().match(/maptiles\/outdoor\/256\/(\d+)\//);
      if (m) tileZooms.push(parseInt(m[1], 10));
    });
    const lastZoom = () => tileZooms[tileZooms.length - 1];

    // Select the most isolated route (via hash — same selectRouteBySlug()
    // path as a click), so zooming out can't recluster its pin away.
    const target = mostIsolatedRoute(routes);
    await page.goto(`/index.html#${target.slug}`);
    await page.waitForTimeout(1200);
    const fitZoom = lastZoom();

    for (let i = 0; i < 3; i++) {
      await page.locator('.leaflet-control-zoom-out').click();
      await page.waitForTimeout(300);
    }
    const tooFar = lastZoom();
    expect(tooFar).toBeLessThan(fitZoom);

    // Click an actual point ON the polyline (its midpoint in screen
    // coordinates) — the SVG path's bounding-box centre isn't reliably on a
    // curved stroke, so a plain force-click there can hit the map instead
    // (same technique as the reopen-panel test below).
    const pt = await page.locator('path.leaflet-interactive').first().evaluate((el) => {
      const mid = el.getPointAtLength(el.getTotalLength() / 2);
      const screen = new DOMPoint(mid.x, mid.y).matrixTransform(el.getScreenCTM());
      return { x: screen.x, y: screen.y };
    });
    await page.mouse.click(pt.x, pt.y);
    await page.waitForTimeout(700);
    const refit = lastZoom();
    expect(refit).toBeGreaterThan(tooFar);
    expect(Math.abs(refit - fitZoom)).toBeLessThanOrEqual(1);
    await expect(page.locator('path.leaflet-interactive')).toHaveCount(1);
  });

  // Closing the detail leaves the route highlighted; clicking the drawn line
  // (not just the pin) must reopen the panel as well as re-fit.
  test('clicking the route polyline reopens the closed detail panel', async ({ page }) => {
    await mockMapyTiles(page);

    await page.goto('/index.html');
    await page.waitForTimeout(800);
    await page.locator('.route-pin').first().click();
    await page.waitForTimeout(600);
    await expect(page.locator('#route-sidebar')).toBeVisible();

    // Close the panel — the route stays drawn.
    await page.locator('#sidebar-close').click();
    await page.waitForTimeout(300);
    await expect(page.locator('#route-sidebar')).toBeHidden();
    await expect(page.locator('path.leaflet-interactive')).toHaveCount(1);

    // Click an actual point on the drawn line (its midpoint, in screen
    // coordinates) — the SVG path's bounding-box centre isn't reliably on a
    // curved stroke, so a plain force-click there can hit the map instead.
    const pt = await page.locator('path.leaflet-interactive').first().evaluate((el) => {
      const mid = el.getPointAtLength(el.getTotalLength() / 2);
      const screen = new DOMPoint(mid.x, mid.y).matrixTransform(el.getScreenCTM());
      return { x: screen.x, y: screen.y };
    });
    await page.mouse.click(pt.x, pt.y);
    await page.waitForTimeout(400);
    await expect(page.locator('#route-sidebar')).toBeVisible();
  });
});
