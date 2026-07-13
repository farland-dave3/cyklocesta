// Route sidebar content: name + the two labeled stats (Czech "Vzdálenost" /
// "Převýšení") with their values. Replaces the old header tap/hover tooltips —
// the labels are now always-visible <dt> text, no hover state to drive.
const { test, expect } = require('@playwright/test');
const { mockMapyTiles, readRoutesJson, clickFirstRoutePin } = require('./helpers');

test.describe('route sidebar content', () => {
  test('shows the name and both labeled stats with their values', async ({ page }) => {
    await mockMapyTiles(page);
    const routes = readRoutesJson();

    await page.goto('/index.html');
    await page.waitForTimeout(800);
    const expected = await clickFirstRoutePin(page, routes);
    await expect(page.locator('#route-sidebar')).toBeVisible();

    await expect(page.locator('#sidebar-name')).toHaveText(expected.name);

    // Labels are static <dt> text; each is visible alongside its value <dd>.
    const stats = page.locator('.sidebar-stats .sidebar-stat');
    await expect(stats).toHaveCount(2);
    await expect(page.locator('.sidebar-stat dt', { hasText: 'Vzdálenost' })).toBeVisible();
    await expect(page.locator('.sidebar-stat dt', { hasText: 'Převýšení' })).toBeVisible();

    await expect(page.locator('#sidebar-distance')).toHaveText(expected.distance_km + ' km');
    await expect(page.locator('#sidebar-elevation')).toHaveText(expected.elevation_m + ' m');
  });
});
