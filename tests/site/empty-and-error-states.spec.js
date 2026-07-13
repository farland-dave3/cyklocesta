// Graceful handling of an empty routes.json and an unreachable (404) routes.json.
const { test, expect } = require('@playwright/test');
const { mockMapyTiles } = require('./helpers');

test.describe('empty / error routes.json states', () => {
  test('empty routes ({"routes":[]}) shows a "no routes" note and does not crash', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (err) => errors.push(err));
    await mockMapyTiles(page);
    await page.route('**/routes.json', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ generated: 'x', routes: [] }) })
    );

    await page.goto('/index.html');
    await page.waitForTimeout(800);

    expect(errors).toEqual([]);
    await expect(page.locator('#status-note')).toBeVisible();
    await expect(page.locator('#status-note')).toContainText('No routes yet');
    await expect(page.locator('.leaflet-marker-icon')).toHaveCount(0);
  });

  test('404 routes.json shows a visible error note and does not crash', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (err) => errors.push(err));
    await mockMapyTiles(page);
    await page.route('**/routes.json', (route) => route.fulfill({ status: 404, contentType: 'text/plain', body: 'not found' }));

    await page.goto('/index.html');
    await page.waitForTimeout(800);

    expect(errors).toEqual([]);
    await expect(page.locator('#status-note')).toBeVisible();
    await expect(page.locator('#status-note')).toContainText('Could not load routes');
    await expect(page.locator('.leaflet-marker-icon')).toHaveCount(0);
  });

  test('a failed GPX fetch after clicking a pin shows an error note, not a crash', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (err) => errors.push(err));
    await mockMapyTiles(page);
    await page.route('**/gpx/**', (route) => route.fulfill({ status: 404, contentType: 'text/plain', body: 'not found' }));

    await page.goto('/index.html');
    await page.waitForTimeout(800);
    await page.locator('.route-pin').first().click();
    await page.waitForTimeout(800);

    expect(errors).toEqual([]);
    await expect(page.locator('#status-note')).toBeVisible();
    await expect(page.locator('#status-note')).toContainText('Could not load this route');
    await expect(page.locator('path.leaflet-interactive')).toHaveCount(0);
  });
});
