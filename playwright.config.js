// Playwright config for the eBike route-map public site.
//
// Serves the repo root as a plain static site (no build step, per
// CLAUDE.md "No CI build step") via `python3 -m http.server`, then runs
// the headless regression suite against it.
const { defineConfig, devices } = require('@playwright/test');

const PORT = 8934;

module.exports = defineConfig({
  // Both the site suite (tests/site/) and the privacy-regression suite
  // (tests/privacy/) run under Playwright's test runner (some as pure
  // Node assertions, no browser needed). tests/pipeline/ is Python
  // unittest and is naturally excluded (no .spec.js files there).
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: 'retain-on-failure',
  },
  webServer: {
    command: `python3 -m http.server ${PORT}`,
    url: `http://127.0.0.1:${PORT}/index.html`,
    reuseExistingServer: true,
    cwd: __dirname,
  },
  // Single desktop project by default; the responsive spec overrides the
  // viewport per-test (test.use({ viewport })) to exercise the ≤768px
  // bottom-sheet path, rather than doubling the whole suite's runtime
  // across a second project.
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
