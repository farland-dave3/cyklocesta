// Desktop pin hover: brand divIcon renders, hover shows a tooltip with the
// route's distance · elevation, and selecting a route turns its pin orange
// (is-selected). Touch has no :hover so this behaviour is desktop-only; the
// suite's default project is Desktop Chrome (pointer: fine, hover: hover).
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const routes = JSON.parse(
  fs.readFileSync(path.join(__dirname, '../../routes.json'), 'utf8')
);

test.describe('desktop pin hover + tooltip', () => {
  test('pins render as brand divIcons (.route-pin with a .route-pin__dot)', async ({ page }) => {
    await page.goto('/index.html');
    await expect(page.locator('.route-pin').first()).toBeVisible();
    await expect(page.locator('.route-pin .route-pin__dot').first()).toBeVisible();
    // No stock Leaflet <img> pins remain.
    expect(await page.locator('.leaflet-marker-icon img.leaflet-marker-icon').count()).toBe(0);
  });

  test('hovering a pin shows a tooltip with that route distance and elevation', async ({ page }) => {
    await page.goto('/index.html');
    const pin = page.locator('.route-pin').first();
    await expect(pin).toBeVisible();
    await pin.hover();
    const tip = page.locator('.leaflet-tooltip.pin-tooltip');
    await expect(tip).toBeVisible();
    const text = (await tip.first().textContent()).trim();
    // Matches "<km> km · <m> m ↑" for SOME route (the first-rendered pin need
    // not be routes[0]); assert it equals one of the real route strings.
    const expected = routes.routes.map(
      (r) => `${r.distance_km} km · ${r.elevation_m} m ↑`
    );
    expect(expected).toContain(text);
  });

  test('selecting a route turns its pin orange (is-selected) and reverts on home', async ({ page }) => {
    await page.goto('/index.html');
    await page.locator('.route-pin').first().click();
    // Selected pin picks up the is-selected class (via setIcon).
    await expect(page.locator('.route-pin.is-selected')).toHaveCount(1);
    // Returning to the overview clears it.
    await page.locator('#home-link').click();
    await expect(page.locator('.route-pin.is-selected')).toHaveCount(0);
  });
});
