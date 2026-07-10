# Route Management (Phase 2) — Design Basis

> **Purpose:** Phase 1 (the public site + the local GPX pipeline) is built, tested, and green.
> This is the working document for **Phase 2: how the non-technical maintainer adds, renames,
> and removes routes** without a terminal, git CLI, or Python install. It frames the design,
> maps each task onto the pipeline that already exists, and surfaces the one open fork worth
> deciding before we build. Read `CLAUDE.md` first (source of truth); this doc expands its
> Phase 2 stub. Decision history lives in `docs/open-questions.md` (#6, #22, #23, #27).
>
> **From:** orchestrator session · **Date:** 2026-07-09 · **Machine:** macOS · replaces the two
> pre-build root handoffs (`handoff-ebike-route-map.md`, `handoff-architecture-prep-2026-07-06.md`,
> now in git history).

---

## 1. Where Phase 1 left us (what already exists)

The privacy-critical work is **done and tested**. Route management is a UI wrapper around it —
it must not reimplement any of it.

| Piece | Location | What it does |
|---|---|---|
| `report` | `pipeline/cli.py` | Read-only: prints each `raw/` file's ride date (Europe/Prague) + distance, to help pick the `YYYY-MM-DD Name` filename. |
| `process` | `pipeline/cli.py` | Validates filenames → endpoint-relative trim (content-keyed 300–600 m jitter) → Douglas–Peucker ~8 m → strip `<time>` → emit-by-whitelist into `gpx/` → move raw→`done/` → regenerate `routes.json`. Skips + warns on fully-trimmed tracks; refuses to overwrite. |
| `rebuild-index` | `pipeline/cli.py` | Regenerates `routes.json` by scanning `gpx/`. **This is the whole edit/delete backend** — renames and deletions in `gpx/` self-heal on the next run (#11, #23). |
| privacy gate | `pipeline/privacy_gate.py` + `hooks/pre-commit` | Blocks any commit that stages raw/done GPX, a non-whitelist-shaped GPX, a `routes.json` whose pins ≠ first trkpt, or a deny-listed secret. Zero-config. |
| hook installer | `pipeline/install_hooks.py` | Installs the `pre-commit` gate into `.git/hooks/`. |

**Consequence for Phase 2:** the manager is essentially a *friendly front-end that calls
`process` / `rebuild-index` and helps the user name & visually review routes before committing.*
No new privacy logic. The crux is already enforced by the gate on every commit regardless of UI.

---

## 2. The maintainer & the hard constraints (unchanged)

- **Non-technical, on Windows.** No terminal, no git CLI, no Python install, no rename-by-hand
  in a file explorer as the primary path.
- **Commits/pushes via GitHub Desktop** (already installed & configured for the repo).
- The add-a-route flow must stay: **get GPX out of the Flow app → into the tool → name → review → publish.**
- Everything runs **locally, pre-commit** (privacy crux). The tool never uploads anything itself.
- Mapy attribution (logo + copyright) is mandatory anywhere a map is shown, incl. previews.

---

## 3. What "managing routes" actually means — three workflows

### 3a. Add (the frequent path — ~4 rides/week, plus an initial backlog import)
1. Export ride(s) from Bosch Flow → GPX files land somewhere (Downloads / `raw/`).
2. For each: choose a **date** (defaulted from the ride's first trackpoint) and a **name** →
   filename `YYYY-MM-DD Name.gpx`.
3. **Process** (trim + simplify + emit + index) — the existing `process` command.
4. **Review each result on a real map** — the privacy checkpoint: confirm the published track
   no longer reveals a sensitive start/end. (Endpoint trim is automatic, but a ride starting at
   a *brand-new* sensitive spot the user cares about is only caught by eyeballing it — parked
   v2 item is in-preview manual trim.)
5. Commit `gpx/` + `routes.json` and push via GitHub Desktop.

Batch shape: **10 routes per review page, each a live map** (caps preview tile fetches; doubles
as the backlog importer). Backlog size today: **still unconfirmed — ask before sizing bulk import.**

### 3b. Edit (rename / change display name)
Filename = ID = display name (`YYYY-MM-DD Name.gpx`). "Edit" = **rename the file in `gpx/`**,
then `rebuild-index`. No re-trim, ever (radius is content-keyed to the raw bytes, so it's
rename-irrelevant by construction — #21b/#28). Known accepted cost: the old `#slug` permalink breaks.

### 3c. Remove
**Delete the file from `gpx/`**, then `rebuild-index`. Nothing else references a route.

> Edit and Remove need **no raw file** and **no privacy processing** — they are pure `gpx/`
> file operations + an index rebuild. This is why they're cheap and safe, and why the manager's
> "manage existing routes" screen can list `gpx/` straight from disk.

---

## 4. The open fork — delivery mechanism

The pre-build plan (recorded, but explicitly "free to swap") was **PySide6 + QtWebEngine, packaged
`.exe`**, embedding the real Leaflet page for a WYSIWYG preview. Now that Phase 1 exists as a
clean stdlib-only Python package + a real Leaflet site, three options are on the table. **This is
the decision to make before building Phase 2.**

### Option A — PySide6 + QtWebEngine `.exe` (the original plan)
- **+** One native window; embeds the real Leaflet page.
- **−** Cannot build or test on this macOS box (PyInstaller can't cross-compile; QtWebEngine
  needs a Windows host) — nothing is verifiable until that host exists.
- **−** Heavy (~150 MB bundle).
- **−** Hits open-question **#6**: QtWebEngine renders a local origin, but the dev key is
  localhost-locked and the prod key is domain-locked → **blank preview tiles** unless we run a
  local server or mint a User-Agent-locked preview key anyway. So even Qt ends up needing the
  local-server machinery below.

### Option B — Local tool that opens in the user's browser  ⭐ recommended
A single bundled Python `.exe` (PyInstaller **one-file, no Qt**) that:
1. runs a tiny **localhost HTTP server**, and
2. serves the **real Leaflet app** plus a thin "manager" overlay (drop-zone, name fields,
   10-per-page live-map review, a "manage existing" list for rename/delete), then opens it in
   the user's default browser (Edge/Chrome).
- **+** Reuses the **entire tested pipeline** unchanged — honors "never reimplement the crux."
- **+** **Genuinely WYSIWYG**: it *is* the real site in a real browser.
- **+** Cleanly resolves **#6** — a `localhost`-referrer Mapy key works in a real browser, no
  origin gymnastics; and **#27** — Python is bundled in the exe, so the pre-commit hook can shell
  out to that same exe on the BFU's Windows box (no separate Python install).
- **+** Far lighter than Qt; **designable and fully testable on macOS now** (it's our existing
  Python + HTML/JS) — only the final PyInstaller packaging step needs a Windows pass.
- **−** Opens in a browser tab rather than a native window (arguably *more* familiar to a BFU),
  and adds a small local-server component.

### Option C — Minimal "process + open preview" batch (no persistent UI)
Double-click launcher → processes `raw/` → opens a generated static preview HTML (real Leaflet,
pointed at the new routes) in the browser for the privacy eyeball → naming done via a simple list.
- **+** Lightest to build. **−** Naming-before-processing is awkward; rename/delete still needs
  *some* list UI, so it tends to grow into Option B anyway.

**Recommendation: Option B.** Phase 1's clean split (tested Python pipeline + real Leaflet page)
is exactly what makes B cheap: the manager becomes glue, not a second implementation of anything
load-bearing, and it dissolves both remaining Phase-2 blockers instead of working around them.
A/C remain viable if a native window or absolute minimalism is preferred.

---

## 5. Privacy invariants any UI must preserve (non-negotiable)

The gate enforces these at commit time no matter what, but the manager must never *fight* them:

- Never write a `.gpx` anywhere but `gpx/`; never stage anything from `raw/`/`done/`.
- Never emit a route whose track was fully trimmed — surface the skip+warn to the user, don't
  paper over it with a null pin.
- The privacy **review step shows the trim result** the public will see. (If a preview ever shows
  the *untrimmed* track to help spot a new sensitive start — a parked v2 idea — it must fetch
  tiles for the home area, which is itself a disclosure to Mapy; decide deliberately, see #6.)
- Do all processing locally; the tool itself uploads nothing. Publishing is GitHub Desktop's job.

---

## 6. Build phasing (what's doable on macOS now)

Independent of the A/B/C choice, most of Phase 2 is buildable/testable here:

- **Now, on macOS:** the "manage existing routes" list (list `gpx/` → rename/delete →
  `rebuild-index`); the add/name/review web UI (Option B) or its Python logic; wiring to the
  existing `process`/`rebuild-index`; a one-page "how to add a ride" guide for the BFU.
- **Deferred to a Windows host:** final PyInstaller packaging, the hook-invokes-the-exe wiring
  (#27), first-run experience, and a Windows verification pass of the whole flow.

---

## 7. Testing the manager

- **Python logic** (naming, list-`gpx/`, rename/delete → rebuild-index, backlog batch) →
  unit tests alongside the existing pipeline suite.
- **The review UI** reuses the real Leaflet page, so the existing Playwright site suite already
  covers map/preview rendering; add coverage for the manager overlay + the rename/delete flow.
- claude-in-chrome for a visual spot-check + a GIF of the add-a-ride flow for the user to review.
- Fixtures stay **fully synthetic** (open-questions #8) — never derived from the real ride.

---

## 8. Open questions to close before/while building Phase 2

- **The A/B/C delivery fork (§4)** — decide first; it shapes everything below.
- **#6 Preview tiles** — resolved by Option B (localhost key in a real browser); still a live
  decision under Option A.
- **#27 Hook execution on Windows** — resolved by Option B (hook shells out to the bundled exe);
  otherwise needs a Python-install answer.
- **Backlog size** — how many existing rides land in the first bulk import? Sizes the batch UI.
- **Same-day duplicate filenames** (#9) and **NFC/NFD filename normalization** (#10) — the
  pipeline already NFC-normalizes on emit; the manager's naming UI should prevent same-day
  collisions (silent overwrite) up front.
- **In-preview manual trim** (parked v2) — do we need it for rides starting at a *new* sensitive
  place, or is "spot it in the review and just don't publish that one" enough for v1?
