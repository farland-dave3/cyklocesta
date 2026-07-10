// Single-route draw (new replaces old), header stats, fit-all default.
//
// Note on test design: the 3 demo routes are far apart and do NOT
// cluster at the fit-all zoom (verified: 3 separate .leaflet-marker-icon
// elements). Selecting a route calls map.fitBounds() to that route's
// (tight) polyline bounds; markercluster's default
// removeOutsideVisibleBounds then removes the other routes' markers from
// the DOM while that tight view is showing. There is no deselect control
// any more — the only way to change state is to click a different pin.
// Because a second pin isn't clickable while zoomed into the first
// route's tight bounds, "new selection replaces old" is exercised via one
// real pointer click (first selection) followed by a direct hash change
// (equivalent code path to a permalink click) for the second selection.
const { test, expect } = require('@playwright/test');
const { mockMapyTiles, injectFakeMapyKey, readRoutesJson } = require('./helpers');

test.describe('fit-all default view', () => {
  test('landing view fits all pins (all markers rendered, none clustered away)', async ({ page }) => {
    await mockMapyTiles(page);
    const routes = readRoutesJson();

    await page.goto('/index.html');
    await page.waitForTimeout(800);

    // All routes visible as individual markers on the default landing
    // view = the map bounds contain every pin (nothing clustered off
    // to one side, nothing cut off outside the viewport).
    await expect(page.locator('.leaflet-marker-icon')).toHaveCount(routes.routes.length);
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

    const markers = page.locator('.leaflet-marker-icon');
    await markers.nth(0).click();
    await page.waitForTimeout(600);

    await expect(page.locator('path.leaflet-interactive')).toHaveCount(1);

    // No popup — the route lives in the sidebar.
    await expect(page.locator('.leaflet-popup-content')).toHaveCount(0);

    // routes.json is sorted date-desc then name-asc (routes_index.py);
    // the first marker added therefore corresponds to routes[0].
    const expected = routes.routes[0];
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
    await page.locator('.leaflet-marker-icon').nth(0).click();
    await page.waitForTimeout(600);
    await expect(page.locator('path.leaflet-interactive')).toHaveCount(1);
    await expect(page.locator('#sidebar-name')).toHaveText(routes.routes[0].name);

    // Second selection via hash change (same selectRouteBySlug() code
    // path a click ultimately drives) — see file-level note on why a
    // second real marker click isn't reliably available here.
    const second = routes.routes[1];
    await page.evaluate((slug) => {
      location.hash = slug;
    }, second.slug);
    await page.waitForTimeout(600);

    // Still exactly one polyline (replaced, not overlaid).
    await expect(page.locator('path.leaflet-interactive')).toHaveCount(1);
    // Sidebar swapped to the second route.
    await expect(page.locator('#sidebar-name')).toHaveText(second.name);
    await expect(page.locator('#sidebar-name')).not.toHaveText(routes.routes[0].name);
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

    await page.goto('/index.html');
    await page.waitForTimeout(800);
    await page.locator('.leaflet-marker-icon').nth(0).click();
    await page.waitForTimeout(700);
    const fitZoom = lastZoom();

    // Zoom out (too far to fit the route), keeping the pin on screen.
    for (let i = 0; i < 3; i++) {
      await page.locator('.leaflet-control-zoom-out').click();
      await page.waitForTimeout(300);
    }
    const tooFar = lastZoom();
    expect(tooFar).toBeLessThan(fitZoom);
    await expect(page.locator('.leaflet-marker-icon').first()).toBeVisible();

    // Re-click the same pin -> re-fit -> zoom back in to the route.
    await page.locator('.leaflet-marker-icon').nth(0).click();
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

    await page.goto('/index.html');
    await page.waitForTimeout(800);
    await page.locator('.leaflet-marker-icon').nth(0).click();
    await page.waitForTimeout(700);
    const fitZoom = lastZoom();

    for (let i = 0; i < 3; i++) {
      await page.locator('.leaflet-control-zoom-out').click();
      await page.waitForTimeout(300);
    }
    const tooFar = lastZoom();
    expect(tooFar).toBeLessThan(fitZoom);

    // Click the polyline itself (not the pin) -> re-fit.
    await page.locator('path.leaflet-interactive').first().click({ force: true });
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
    await page.locator('.leaflet-marker-icon').nth(0).click();
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
