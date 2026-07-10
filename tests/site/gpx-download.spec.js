// Sidebar -> GPX download link.
//
// The download is a plain same-origin <a href="gpx/…" download="…">, so we
// don't trigger a real save; we assert the link is wired correctly (present
// only while a route is selected, correct href + download filename) and that
// it disappears again on the overview.
const { test, expect } = require('@playwright/test');
const { mockMapyTiles, readRoutesJson } = require('./helpers');

test.describe('sidebar: GPX download', () => {
  test('download is hidden on the overview, appears when a route is selected, and links to the route GPX', async ({ page }) => {
    await mockMapyTiles(page);
    const routes = readRoutesJson();

    await page.goto('/index.html');
    await page.waitForTimeout(800);

    // Overview: no route selected -> sidebar (and its download) hidden.
    await expect(page.locator('#route-sidebar')).toBeHidden();
    await expect(page.locator('#download-gpx')).toBeHidden();

    // Select the first route.
    await page.locator('.leaflet-marker-icon').nth(0).click();
    await page.waitForTimeout(600);
    const expected = routes.routes[0];

    // Download button now shown, points at the route's static file, and
    // downloads under the original YYYY-MM-DD Name.gpx filename.
    const link = page.locator('#download-gpx');
    await expect(link).toBeVisible();
    await expect(link).toHaveAttribute('download', expected.file);
    const href = await link.getAttribute('href');
    expect(href).toBe('gpx/' + encodeURIComponent(expected.file));
    // href resolves to a real, fetchable file (same file the polyline used).
    const resp = await page.request.get(new URL(href, page.url()).toString());
    expect(resp.status()).toBe(200);
  });

  test('download disappears again when returning to the overview', async ({ page }) => {
    await mockMapyTiles(page);

    await page.goto('/index.html');
    await page.waitForTimeout(800);
    await page.locator('.leaflet-marker-icon').nth(0).click();
    await page.waitForTimeout(600);
    await expect(page.locator('#download-gpx')).toBeVisible();

    // Home logo returns to overview -> sidebar + download hidden.
    await page.locator('#home-link').click();
    await page.waitForTimeout(300);
    await expect(page.locator('#route-sidebar')).toBeHidden();
    await expect(page.locator('#download-gpx')).toBeHidden();
  });

  test('the sidebar close button keeps the route highlighted and zoomed', async ({ page }) => {
    await mockMapyTiles(page);

    await page.goto('/index.html');
    await page.waitForTimeout(800);
    await page.locator('.leaflet-marker-icon').nth(0).click();
    await page.waitForTimeout(600);
    await expect(page.locator('#route-sidebar')).toBeVisible();
    const hashWhenOpen = await page.evaluate(() => location.hash);

    // Close button collapses the panel but leaves the route drawn, its pin
    // selected, and the #slug permalink intact — proof the map stayed on the
    // route instead of snapping back to the overview (which removes the
    // polyline, deselects the pin, and clears the hash).
    await page.locator('#sidebar-close').click();
    await page.waitForTimeout(300);
    await expect(page.locator('#route-sidebar')).toBeHidden();
    await expect(page.locator('path.leaflet-interactive')).toHaveCount(1);
    await expect(page.locator('.route-pin.is-selected')).toHaveCount(1);
    expect(await page.evaluate(() => location.hash)).toBe(hashWhenOpen);

    // Re-clicking the same pin reopens the detail panel.
    await page.locator('.leaflet-marker-icon').nth(0).click();
    await page.waitForTimeout(300);
    await expect(page.locator('#route-sidebar')).toBeVisible();
  });
});
