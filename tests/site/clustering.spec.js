// Pin clustering & count vs routes.json.
const { test, expect } = require('@playwright/test');
const { mockMapyTiles, injectFakeMapyKey, readRoutesJson, totalRenderedPins } = require('./helpers');

test.describe('clustering', () => {
  test('marker/cluster count on the real routes.json matches its route count', async ({ page }) => {
    await mockMapyTiles(page);
    const routes = readRoutesJson();
    expect(routes.routes.length).toBeGreaterThan(0); // sanity: fixture actually has data

    await page.goto('/index.html');
    await page.waitForTimeout(800);

    expect(await totalRenderedPins(page)).toBe(routes.routes.length);
  });

  test('tightly-packed pins cluster below the disableClusteringAtZoom threshold and separate above it', async ({ page }) => {
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

    // Fit-all on these metres-apart pins lands at max zoom, which is above
    // disableClusteringAtZoom — every pin renders individually, no cluster.
    await expect(page.locator('.marker-cluster')).toHaveCount(0);
    await expect(page.locator('.route-pin')).toHaveCount(5);

    // Zoom out below the threshold (maxZoom 19 → 11) — the pins collapse
    // into a single cluster badge with the full count.
    for (let i = 0; i < 8; i++) {
      await page.locator('.leaflet-control-zoom-out').click();
      await page.waitForTimeout(300);
    }
    const clusters = page.locator('.marker-cluster');
    await expect(clusters).toHaveCount(1);
    await expect(clusters.first()).toHaveText('5');
    expect(await totalRenderedPins(page)).toBe(5);
  });

  // Regression for the "clustering too aggressive" complaint: two rides
  // starting ~220 m apart (jittered pins from the same trailhead) must show
  // as separate pins from zoom 13 (= maxZoom − 6) up, not only near max
  // zoom as markercluster's default 80px radius gave (~z16).
  test('pins ~220 m apart separate at zoom 13 and recluster at zoom 12', async ({ page }) => {
    await mockMapyTiles(page);
    await injectFakeMapyKey(page); // tile z on request URLs is the zoom proxy

    const twoClose = {
      generated: 'test',
      routes: [0, 1].map((i) => ({
        slug: `near-${i}`,
        file: `near-${i}.gpx`,
        name: `Near ${i}`,
        date: '2026-01-01',
        distance_km: 10.0,
        elevation_m: 100,
        pin: [50.1 + i * 0.002, 14.5], // 0.002° lat ≈ 222 m apart
        bbox: [[50.1, 14.5], [50.102, 14.502]],
      })),
    };
    await page.route('**/routes.json', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(twoClose) })
    );

    const tileZooms = [];
    page.on('request', (req) => {
      const m = req.url().match(/maptiles\/outdoor\/256\/(\d+)\//);
      if (m) tileZooms.push(parseInt(m[1], 10));
    });
    const lastZoom = () => tileZooms[tileZooms.length - 1];

    await page.goto('/index.html');
    await page.waitForTimeout(1000);
    expect(lastZoom()).toBeGreaterThan(13); // fit-all of a 222 m span zooms deep

    // Zoom out to exactly 13: still two separate pins, no cluster.
    for (let i = 0; i < 10 && lastZoom() > 13; i++) {
      await page.locator('.leaflet-control-zoom-out').click();
      await page.waitForTimeout(350);
    }
    expect(lastZoom()).toBe(13);
    await expect(page.locator('.route-pin')).toHaveCount(2);
    await expect(page.locator('.marker-cluster')).toHaveCount(0);

    // One more step (zoom 12, below the threshold): they merge into a cluster.
    await page.locator('.leaflet-control-zoom-out').click();
    await page.waitForTimeout(350);
    expect(lastZoom()).toBe(12);
    await expect(page.locator('.marker-cluster')).toHaveCount(1);
    await expect(page.locator('.marker-cluster').first()).toHaveText('2');
  });
});
