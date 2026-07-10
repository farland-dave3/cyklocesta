# CLAUDE.md — eBike Route Map

A public web map of ~1400 eBike routes (clustered pins → click to draw one route) plus a Windows **Route Manager** `.exe` a non-technical user runs to add rides safely. **Pure static site** on GitHub Pages, no backend. Full rationale & decision log: [docs/open-questions.md](docs/open-questions.md) (the pre-build handoffs are now in git history). **Phase 1 is built** (2026-07-06): the site, the pipeline, the privacy gate, and both test suites exist and are green; Phase 2 (Route Manager — add/edit/remove routes) is not started — design basis in [route-management-design.md](route-management-design.md). Deploy steps: [docs/deploy-checklist.md](docs/deploy-checklist.md).

## ⛔ Non-negotiables (getting these wrong breaks the project)

- **Raw GPX must NEVER enter git.** `raw/` and `done/` are gitignored. ALL privacy-zone trimming + simplification happens **locally, pre-commit**. A public repo keeps history forever — one committed raw file permanently leaks real home coordinates. **Never move processing into CI/GitHub Actions.**
- **Endpoint-relative trim + pin at first surviving point (REDESIGNED 2026-07-06, open-questions #28).** There is no zones config and no coordinates are ever entered: the sensitive place is *wherever that ride started/ended* (home, camp, hotel). Trim removes **every** point (mid-route too) within a jittered radius of the ride's own **first raw point** and, independently, of its **last raw point**. Pin at the first surviving point. Track entirely trimmed → skip + warn (never emit a null pin). Accepted residuals: mid-route pass-bys near home stay published; many rides from one area still disclose the neighborhood.
- **Per-route radius jitter, keyed on raw content (anti "pin ring").** A fixed trim radius puts pins from repeat rides ~on a circle around the shared start — three pins fit the circle and recover the doorstep. Each anchor's effective radius is stretched into `[300 m, 600 m)` derived from **SHA-256 of the raw file bytes** (start and end radii independent). No salt, no secret to manage: outsiders can never know the raw bytes, so radii are unreconstructable; same raw file → deterministic, idempotent re-runs; renames never affect the radius, so renaming a published route never requires re-trimming. Never "simplify" back to a fixed radius.
- **Emit GPX by whitelist, never edit-in-place.** Re-serialize output as `<trk><trkseg><trkpt lat lon><ele>` only, so `<metadata>`/`<wpt>`/`<extensions>` (present in real Flow files, or added by future firmware) can never survive into a published file. Per-point `<time>` is **stripped** on emit (patterns-of-life leak); the ride date survives in the filename.
- **Commit-time privacy gate (DECIDED, zero-config).** A *local* git `pre-commit` hook (not CI), installed by the Route Manager and run via the bundled `.exe`, blocks any commit that stages: anything from `raw/`/`done/`; any `.gpx` outside `gpx/`; any `.gpx` that isn't whitelist-shaped (carries `<time>`/`<metadata>`/`<wpt>`/`<extensions>` — this catches raw-format files); a `routes.json` whose pins don't equal the first trkpt of their referenced `gpx/` file; or the deny-listed secrets (`privacy-zones.json` legacy, `config.local.js`, `*.log`). Needs no config file. The dev/agent tests don't run on the BFU's Windows commits — the hook is the only enforcement there.
- **Test fixtures must be synthetic/anonymized.** The real `raw/eBike ride.gpx` is **local dev input only**; committed test GPX use fabricated coordinates.
- **No CI build step.** GitHub Pages serves straight from the branch; the committed repo is already a complete static site.
- **GPX-only** source of truth. FIT was considered and rejected — don't add a FIT pipeline.
- **One route drawn at a time** (new pin replaces current). No overlay-by-default.
- **Filename `YYYY-MM-DD Name.gpx`** is the route ID *and* display name *and* uniqueness key. Changing the scheme ripples into slugs/permalinks/dedup.
- **Secrets (DECIDED, implemented):** never hard-code the Mapy key in page code. **`config.js` is committed** and holds only the referrer-locked **prod** key (safe in a public repo; placeholder until deploy). The **dev** key lives in gitignored `config.local.js` (`config.example.js` is its committed template), loaded after `config.js` as an override. Never put the dev key in `config.js`. See open-questions #2 + [docs/mapy-api.md](docs/mapy-api.md).
- **Mapy attribution (logo + copyright)** is mandatory on the site AND the Route Manager preview.

## Architecture at a glance

- **Public site:** `index.html` + Leaflet app, Leaflet.markercluster, Mapy **outdoor** tiles, fit-all-pins default. Route panel = bottom sheet (mobile) / popup (desktop). Routes are **URL-addressable** (`#slug` permalink). The map is the index — no browse/list/search.
- **Data:** `gpx/` (committed, trimmed + Douglas–Peucker simplified ~8 m) · `routes.json` (committed, generated; precomputed distance + elevation) · `raw/` + `done/` (gitignored).
- **Pipeline:** local Python (stdlib-only, zero setup): parse → extract ride date (from raw first trackpoint, converted to Europe/Prague — GPX times are UTC) → endpoint-relative trim with content-keyed radius jitter → simplify → strip `<time>` → emit-by-whitelist → regenerate `routes.json` by scanning `gpx/`. Run pre-commit. **Phase 1 input:** files in `raw/` are manually renamed to `YYYY-MM-DD Name.gpx`, then batch-processed via CLI (no GUI until Phase 2).
- **Route Manager (Phase 2):** Python + PySide6 + QtWebEngine, packaged `.exe`. Preview reuses the **real Leaflet page** (WYSIWYG). Flow: drop files in `raw/` → launch GUI → review/name (scrollable, 10 live maps/page) → GitHub Desktop commit/push. Maintainer is non-technical, on Windows: no terminal, no git CLI, no Python install.

## Delivery phases (DECIDED)

**Phase 1 = the public site** (fully buildable + testable on this macOS box). **Phase 2 = the Route Manager `.exe`** — deferred until a Windows build/verify host exists (PyInstaller can't cross-compile from macOS). The Python pipeline + Leaflet preview develop on macOS now; Windows packaging/QtWebEngine + hook install verify later on Windows.

## Source data

Bosch eBike Flow GPX exports only — bare tracks (`lat`/`lon`/`<ele>`/`<time>`), single `<trk>`/`<trkseg>`, constant name "eBike ride", date from first trackpoint, non-unique filenames. Example fixture: `eBike_ride.gpx` (2195 pts, ~43 min).

## How we work (orchestration)

- **Main session = orchestrator (Opus).** Plans, delegates, verifies, integrates. Per deliverable: **developer (Sonnet) → verifier (Opus) → grill-reviewer (Opus) → fix → present.**
- **Autonomy:** run autonomously, **halt only at genuine forks** (consequential/hard-to-reverse decisions or spec gaps). Surface the fork, get a decision, continue.
- **Agents** (`.claude/agents/`): `developer` (builds, Sonnet) · `tester` (Playwright + claude-in-chrome, Sonnet) · `verifier` (independent end-to-end, Opus, read-only) · `grill-reviewer` (adversarial critique of plans/docs, Opus, read-only).
- Details: [docs/agent-orchestration.md](docs/agent-orchestration.md).

## Testing (no CI — runs locally)

- **Playwright headless** = the automated regression suite agents run (incl. privacy-regression + attribution tests).
- **claude-in-chrome** = real-browser visual spot-checks + GIFs.
- Details: [docs/testing-strategy.md](docs/testing-strategy.md).

## Environment note

Dev machine is **macOS**; the Route Manager ships as a **Windows `.exe`**. The Leaflet site + Python logic develop fine here, but QtWebEngine packaging/behavior needs a separate Windows verification pass.

## Reference docs

- [docs/agent-orchestration.md](docs/agent-orchestration.md) — how we run agents.
- [docs/mapy-api.md](docs/mapy-api.md) — Mapy tiles, keys, attribution.
- [docs/testing-strategy.md](docs/testing-strategy.md) — Playwright + claude-in-chrome split.
- [docs/deploy-checklist.md](docs/deploy-checklist.md) — local setup → first real routes → going live.
- [docs/claude-md-practices.md](docs/claude-md-practices.md) — how to maintain this file.
- [docs/open-questions.md](docs/open-questions.md) — full decision log & unresolved decisions (⏳ = needs user).
- [route-management-design.md](route-management-design.md) — Phase 2 (add/edit/remove routes) design basis.
