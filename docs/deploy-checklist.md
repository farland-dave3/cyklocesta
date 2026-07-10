# Deploy Checklist — from "green on localhost" to live on GitHub Pages

The gap between a working local build and a safe public deploy is where the privacy crux
actually bites. Work through this **in order**. Written 2026-07-06 after the Phase 1 build.

## 0. One-time local setup (before processing any real ride)

There is **no privacy config** — trimming is automatic (each ride is trimmed 300–600 m around
its own start and end points; open-questions #28). Only two things to set up:

- [ ] Copy `config.example.js` → `config.local.js` (gitignored) and paste the **dev** Mapy key —
      needed only to see real tiles locally; the pipeline and tests run without it.
- [ ] Confirm the hook is installed: `.git/hooks/pre-commit` exists and is executable
      (`python3 pipeline/install_hooks.py` re-installs it).

## 1. Before the first real commit of routes

- [x] **Purge the demo data** — done 2026-07-07: `gpx/` no longer contains any synthetic
      demo routes (only real, pipeline-trimmed rides). Demo data now lives exclusively in
      tests (`scripts/make_demo_data.py` generates into temp dirs, never `gpx/`). If demo
      files ever reappear in `gpx/`, delete them and `python3 -m pipeline rebuild-index`
      BEFORE committing — a public repo keeps history forever.
- [ ] Process real rides: rename in `raw/` to `YYYY-MM-DD Name.gpx`
      (`python3 -m pipeline report` prints each file's date/distance to help), then
      `python3 -m pipeline process`.
- [ ] Stage with plain `git add gpx routes.json` — **never `git add -f`**, never stage
      `raw/`, `done/`, or `config.local.js` (the gate blocks these, but don't lean on it).
- [ ] `git add -n .` first and eyeball: no `.gpx` outside `gpx/`, no secrets.
- [ ] Commit. The pre-commit gate must run (you'll see its output). If it blocks, it says why.

## 2. Going live (needs open-questions #18/#19 decided first)

- [ ] Decide domain + public repo name (#18/#19) — the prod key's referrer lock depends on them.
- [ ] Create the **prod** Mapy key at <https://developer.mapy.com/en/my-account/>,
      HTTP-referrer-restricted to the live domain. Put it in the committed `config.js`
      (replacing `PROD_KEY_PENDING_DEPLOY`). **Never the dev key.**
      Shipping the placeholder = a live site with a "tiles disabled" banner.
- [ ] Enable GitHub Pages, serve from the branch root (no build step; `.nojekyll` is committed).
- [ ] Open the live URL: tiles render, attribution (Seznam copyright + Mapy logo) present,
      a `#slug` permalink deep-links correctly.
- [ ] **Rotate/retire the dev key if it was ever pasted anywhere public** (it was shared in a
      chat once — treat as compromised; see handoff).
- [ ] Apply for the Mapy **Extended tariff** (10M credits/mo for public free projects —
      docs/mapy-api.md) once the site is public.

## 3. After every future batch of rides

`raw/` → rename → `python3 -m pipeline process` → review `git status`/`git add -n .` →
commit gpx + routes.json → push. The gate re-checks every staged GPX (whitelist shape)
and every routes.json pin (must equal the first point of its GPX).
