// Pin clustering & count vs routes.json.
const { test, expect } = require('@playwright/test');
const { mockMapyTiles, readRoutesJson } = require('./helpers');

/** Sum of markercluster's cluster-badge counts + any un-clustered marker icons. */
async function totalRenderedPins(page) {
  const clusterTexts = await page.locator('.marker-cluster').allTextContents();
  const clusterSum = clusterTexts.reduce((sum, t) => sum + (parseInt(t, 10) || 0), 0);
  const plainMarkers = await page.locator('.leaflet-marker-icon:not(.marker-cluster)').count();
  return clusterSum + plainMarkers;
}

test.describe('clustering', () => {
  test('marker/cluster count on the real routes.json matches its route count', async ({ page }) => {
    await mockMapyTiles(page);
    const routes = readRoutesJson();
    expect(routes.routes.length).toBeGreaterThan(0); // sanity: fixture actually has data

    await page.goto('/index.html');
    await page.waitForTimeout(800);

    expect(await totalRenderedPins(page)).toBe(routes.routes.length);
  });

  test('markercluster groups tightly-packed pins into a cluster badge showing the correct count', async ({ page }) => {
    await mockMapyTiles(page);

    const closeRoutes = { generated: 'test', routes: [] };
    for (let i = 0; i < 5; i++) {
      closeRoutes.routes.push({
        slug: `close-${i}`,
        file: `close-${i}.gpx`,
        name: `Close ${i}`,
        date: '2026-01-01',
        distance_km: 1.0,
        elevation_m: 1,
        pin: [50.1 + i * 0.00001, 14.5 + i * 0.00001],
        bbox: [[50.1, 14.5], [50.1002, 14.5002]],
      });
    }
    await page.route('**/routes.json', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(closeRoutes) })
    );

    await page.goto('/index.html');
    await page.waitForTimeout(1000);

    const clusters = page.locator('.marker-cluster');
    await expect(clusters).toHaveCount(1);
    await expect(clusters.first()).toHaveText('5');
    expect(await totalRenderedPins(page)).toBe(5);
  });
});
