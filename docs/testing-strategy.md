# Testing Strategy

This project has **no CI** (deliberate — see the privacy crux). Tests therefore run **locally**, driven by the tester agent. Two tools, split by role.

## Playwright (headless) — the automated suite

The repeatable regression suite. Fast, scriptable, agent-runnable unattended. Runs headless by default; headed on demand for debugging.

**What it covers (public site):**
- Map loads; Mapy `outdoor` tiles render; **attribution + logo present** (terms compliance is a test, not a hope).
- Pins cluster via markercluster; expected pin count from `routes.json`.
- Clicking a pin draws exactly **one** route (new selection replaces the old — no overlay).
- Popup shows name · date · distance · elevation, matching `routes.json`.
- **Permalink**: opening `#<slug>` loads the map with that route drawn and zoomed.
- Fit-all-pins is the default landing view.
- Responsive: route panel is a bottom sheet on mobile, popup on desktop.

**Privacy regression (critical — endpoint-relative model, open-questions #28):**
- Assert every committed GPX is whitelist-shaped (no `<time>`/`<metadata>`/`<wpt>`/`<extensions>`).
- Assert each `routes.json` pin equals the first point of its GPX file.
- For synthetic fixtures whose raw input is regenerable: assert the published first/last points sit ≥ 300 m (the radius floor) from the raw start/end anchors.
- A guard test that fails if any file under `raw/`/`done/` is tracked by git, or any `.gpx` is tracked outside `gpx/`.

**Python pipeline:** unit tests for endpoint-relative trim (points near the ride's own start/end anchors removed, mid-route pass-backs included; fully-trimmed track → skip; content-keyed jitter determinism + [300,600) range), emit-by-whitelist (no `<metadata>`/`<wpt>`/`<extensions>` survive), Douglas–Peucker tolerance, distance/elevation computation, and `routes.json` generation.

> **Fixtures policy (non-negotiable, tightened — open-questions #8):** committed test GPX must be **fully synthetic geometry** — generated shapes (loops, out-and-backs) at fabricated coordinates over open water or an obviously fake origin. Do **not** transpose the real ride's geometry to fake coordinates: a route's *shape* can be map-matched back to the real road network and re-located. The real `raw/eBike ride.gpx` is **local dev input only** and must never become a committed fixture.

## claude-in-chrome (real browser) — visual spot-checks + GIFs

Not a saved suite. Used for:
- Visual confirmation on real Chrome (tiles, clustering, layout) when a change is visual.
- **GIF recordings** of key flows (pin → route draw, permalink open, Route Manager review page) for the user to review/share.
- Ad-hoc exploration the scripted suite doesn't cover.

## Route Manager (PySide6 + QtWebEngine)

- Python-side logic (GPX parse, trim, naming, move `raw/`→`done/`) → Playwright-independent unit tests.
- The embedded preview reuses the **real Leaflet page**, so the Playwright site suite already covers preview rendering. Manual/visual GUI checks via screenshots.

## Who runs what

- **tester agent (Sonnet)** writes and runs the Playwright suite and does claude-in-chrome spot-checks.
- **verifier agent (Opus)** independently re-drives the finished deliverable end-to-end (fresh eyes) before it's accepted — it does not just re-read tests, it exercises behavior.
