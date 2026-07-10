// Responsive: the selected route lives in a sidebar (right column on desktop,
// bottom sheet on mobile). Both layouts show the same name/distance/elevation.
const { test, expect } = require('@playwright/test');
const { mockMapyTiles, readRoutesJson } = require('./helpers');

async function selectFirstAndAssertSidebar(page, routes) {
  await page.goto('/index.html');
  await page.waitForTimeout(800);
  await page.locator('.leaflet-marker-icon').nth(0).click();
  await page.waitForTimeout(600);

  const expected = routes.routes[0];
  await expect(page.locator('#route-sidebar')).toBeVisible();
  await expect(page.locator('#sidebar-name')).toHaveText(expected.name);
  await expect(page.locator('#sidebar-distance')).toContainText(String(expected.distance_km));
  await expect(page.locator('#sidebar-elevation')).toContainText(String(expected.elevation_m));

  // No popup on any viewport.
  await expect(page.locator('.leaflet-popup-content')).toHaveCount(0);
}

test.describe('responsive route sidebar', () => {
  test('desktop viewport (>700px) shows the route sidebar beside the map', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await mockMapyTiles(page);
    const routes = readRoutesJson();
    await selectFirstAndAssertSidebar(page, routes);

    // Desktop: sidebar sits to the RIGHT of the map (same row), so the map
    // does not span the full width.
    const mapBox = await page.locator('#map-wrap').boundingBox();
    const barBox = await page.locator('#route-sidebar').boundingBox();
    expect(barBox.x).toBeGreaterThan(mapBox.x + mapBox.width - 2); // sidebar starts where the map ends
    expect(mapBox.width).toBeLessThan(1280);
  });

  test('mobile viewport (<=700px) shows the route sidebar as a bottom sheet', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 }); // iPhone-ish
    await mockMapyTiles(page);
    const routes = readRoutesJson();
    await selectFirstAndAssertSidebar(page, routes);

    // Mobile: sidebar stacks BELOW the map (bottom sheet), spanning full width.
    const mapBox = await page.locator('#map-wrap').boundingBox();
    const barBox = await page.locator('#route-sidebar').boundingBox();
    expect(barBox.y).toBeGreaterThan(mapBox.y + mapBox.height - 2); // sidebar starts where the map ends
    expect(Math.round(barBox.width)).toBe(390);
  });
});
