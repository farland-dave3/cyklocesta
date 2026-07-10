# Mapy.com REST API — Project Reference

Researched 2026-07-06. What we need to know to use Mapy.com tiles on the public site and in the Route Manager preview. **Verify exact URL templates against the live docs before relying on them** — the interactive spec is the source of truth: <https://api.mapy.com/v1/docs/>.

## Account & keys

- Keys live under an **API Project** (Basic tier for us). Manage at <https://developer.mapy.com/en/my-account/>.
- Mapy explicitly recommends **separate keys for production vs development** (and web vs mobile). We do exactly this:
  - **Dev key** (the one already in hand) — used on `localhost` only, kept in gitignored `config.local.js`. See [../CLAUDE.md](../CLAUDE.md) "Secrets".
  - **Prod key** — created later, **HTTP-referrer restricted to the live domain**, committed in `config.js` (currently a placeholder). Because it's referrer-locked, a client-side key is safe — this is the load-bearing assumption behind the "pure static site, no backend" architecture.
- Referrer restriction is what makes the public key safe: a key scraped from the site won't work from another origin. It does **not** stop someone spoofing the Referer header, so also set a **billing/credit alert** as the real backstop.

## Tile layer (raster)

- Endpoint family: `https://api.mapy.com/v1/maptiles/{tileset}/{tileSize}/{z}/{x}/{y}?apikey=YOUR_KEY`
  - `{tileset}`: `basic`, **`outdoor`** (tourist/trail — our choice), `aerial`, `winter`, `names-overlay`.
  - `{tileSize}`: `256`, or `512` (retina) — retina only available for `basic` and `outdoor`.
- **Leaflet usage (shape — confirm against live docs):**
  ```js
  L.tileLayer('https://api.mapy.com/v1/maptiles/outdoor/256/{z}/{x}/{y}?apikey=' + MAPY_KEY, {
    minZoom: 0,
    maxZoom: 19,
    attribution: '<a href="https://api.mapy.com/copyright" target="_blank">&copy; Seznam.cz a.s. a další</a>',
  }).addTo(map);
  ```
- **TileJSON** endpoint (`.../tiles.json`) returns the canonical set URL, valid zoom range, and the correct attribution string — fetch it rather than hard-coding zoom/attribution when possible.

## Integration risks (see open-questions.md)

- ✅ **RESOLVED — Key delivery on a no-build static site.** Decided 2026-07-06: committed `config.js` holds the referrer-locked prod key (placeholder until deploy); gitignored `config.local.js` overrides with the dev key. `index.html` loads `config.js` then `config.local.js` (tolerate 404). (open-questions #2)
- **Route Manager preview tiles.** QtWebEngine renders a local origin; a localhost-locked dev key and a domain-locked prod key both mismatch that origin → blank preview. Options: an in-app `http://localhost` server whose origin matches the dev key, or a dedicated preview key. Also decide pre- vs post-trim preview (a pre-trim preview fetches home-area tiles). (open-questions #6)

## Attribution — MANDATORY

Displaying Mapy tiles **requires** both:
1. The **Mapy.com logo** (a clickable logo control, bottom-left by convention), and
2. The **copyright text** (© Seznam.cz a.s. + data providers).

This applies on **both** the public site **and** the Route Manager preview (it renders real tiles). Missing attribution is a terms violation. Add a Leaflet logo control (an `L.Control` with the Mapy logo `<img>` linking to mapy.com) plus the tile layer's `attribution`.

Specifics (researched 2026-07-06):
- **Logo asset:** `https://api.mapy.com/img/api/logo.svg` (green variant: `logo_green.svg`). Min height ~30 px on-map. Must be clickable → `https://mapy.com/`, visible, and ≥ any other logo on the map.
- **Copyright text:** "Seznam.cz a.s. and others" linked to `https://api.mapy.com/copyright`.
- Copy the exact control code from their [map-display tutorial](https://developer.mapy.com/rest-api-mapy-cz/tutorials/map-display/) (Leaflet tab) when scaffolding.

## Other functions (available, not yet needed)

- **Static Maps API** — returns a map image with layers. Possible future use for social/OG preview thumbnails without loading Leaflet. Consumes credits per image.
- **Geocoding / Routing APIs** — not needed; our routes come from GPX, not computed.

## Cost / limits (researched 2026-07-06)

- **1 credit = 1 tile.** Basic tariff: **250,000 free credits/month**.
- **Extended tariff: 10,000,000 free credits/month** for public projects — conditions: publicly/freely accessible to all, uses **only Mapy.com map data**, displays logo + copyright, listed in their Reference Projects Catalogue, annual affidavit. **This site qualifies on all counts → apply at deploy.**
- **No surprise bills:** "no charged consumption without your consent" — paid overage only if you explicitly enable it via Seznam Wallet. Exhausted credits = tiles stop, not charges. No automated billing-alert feature found in the docs.
- Paid overage (if enabled): tiered, 1.6 CZK/1000 credits and down.
- Tests must still mock tiles (see testing-strategy) — 250k/month is generous but preview pages (10 live maps) and Playwright runs add up.

## Key restrictions (researched 2026-07-06)

- Supported: **HTTP referrer**, IP, **User-Agent**, per-service. Referrer matching uses host+port only (no slashes); wildcards like `*.domena.cz`; **`localhost:*` is explicitly supported** → the dev key story works as planned.
- The **User-Agent restriction** is a promising option for the Phase 2 QtWebEngine preview key (a custom UA set in the embedded browser), instead of running a localhost server just to satisfy a referrer lock. (open-questions #6)

## Sources

- [REST API overview](https://developer.mapy.com/rest-api-mapy-cz/)
- [API key](https://developer.mapy.com/rest-api-mapy-cz/api-key/)
- [Map tiles](https://developer.mapy.com/rest-api-mapy-cz/function/map-tiles/)
- [Map display tutorial](https://developer.mapy.com/rest-api-mapy-cz/tutorials/map-display/)
- [Interactive spec](https://api.mapy.com/v1/docs/)
