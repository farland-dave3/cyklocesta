"""Commit-time privacy gate (CLAUDE.md ⛔, open-questions #1).

Runs as a local git pre-commit hook — never in CI. Zero-config (2026-
07-06 design change: there is no privacy-zones.json anymore — trim is
endpoint-relative, keyed on each raw file's own bytes, see privacy.py).
Blocks a commit that stages:
  - anything under raw/ or done/,
  - any .gpx outside gpx/,
  - a .gpx in gpx/ that isn't whitelist-shaped (carries <time>/
    <metadata>/<wpt>/<extensions> — this is now the MAIN line of
    defense: any raw-format file fails this outright),
  - a routes.json whose `pin` doesn't equal the first trkpt of its
    referenced gpx/<file> (staged content if that gpx is staged this
    commit, else the current working-tree copy; missing gpx -> block)
    — every published pin must be the first point of a pipeline-
    emitted (i.e. trimmed) file, closing hand-edited-pin and
    index/gpx inconsistency holes,
  - anything on the never-commit deny-list: `privacy-zones.json` (kept
    defensively in case a stale copy from the old zone-based model
    still exists somewhere), `config.local.js`, any `*.log`.

Core checking functions take already-loaded data (staged path list +
loader callables) so tests can drive them directly without making real
commits. `main()` / `--staged` wire that up to real git plumbing
(`git diff --cached --name-only`, `git show :path`, working-tree reads).
"""

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

try:  # runnable both as `python3 pipeline/privacy_gate.py` and as a package module
    from .xmlutil import localname
except ImportError:  # pragma: no cover - exercised only when run as a bare script
    from xmlutil import localname

ALLOWED_TAGS = {"gpx", "trk", "trkseg", "trkpt", "ele"}
FORBIDDEN_TAGS = {"time", "metadata", "wpt", "extensions"}

#: Never-commit deny-list, checked unconditionally. `privacy-zones.json`
#: is obsolete (the zone model is gone) but kept here defensively in
#: case a stale copy exists. `config.local.js` holds the dev Mapy key.
#: `*.log` can contain paths/coordinates from a Route Manager traceback.
DENY_EXACT_NAMES = {"privacy-zones.json", "config.local.js"}


def _is_denied(norm_path):
    basename = norm_path.rsplit("/", 1)[-1]
    if basename in DENY_EXACT_NAMES:
        return True
    if norm_path.lower().endswith(".log"):
        return True
    return False


def classify_staged_paths(paths):
    """Split staged repo-relative paths into the buckets the gate cares
    about."""
    denied = []
    raw_or_done = []
    gpx_outside = []
    gpx_in_dir = []
    routes_json = None

    for p in paths:
        norm = p.replace("\\", "/")
        if _is_denied(norm):
            denied.append(p)
            continue
        if norm.startswith("raw/") or norm.startswith("done/"):
            raw_or_done.append(p)
        elif norm.endswith(".gpx"):
            if norm.startswith("gpx/"):
                gpx_in_dir.append(p)
            else:
                gpx_outside.append(p)
        elif norm == "routes.json":
            routes_json = p

    return {
        "denied": denied,
        "raw_or_done": raw_or_done,
        "gpx_outside": gpx_outside,
        "gpx_in_dir": gpx_in_dir,
        "routes_json": routes_json,
    }


def check_structure(gpx_bytes):
    """Structural whitelist check: only gpx/trk/trkseg/trkpt/ele tags
    allowed. Returns a list of violation strings (empty = OK)."""
    try:
        root = ET.fromstring(gpx_bytes)
    except ET.ParseError as exc:
        return [f"not valid XML ({exc})"]

    violations = []
    for elem in root.iter():
        tag = localname(elem.tag)
        if tag in FORBIDDEN_TAGS:
            violations.append(f"forbidden element <{tag}> present")
        elif tag not in ALLOWED_TAGS:
            violations.append(f"unexpected element <{tag}> (not in whitelist)")
    return violations


def _first_trkpt_from_gpx_bytes(gpx_bytes):
    """Return (lat, lon) of the first <trkpt>, or None if there isn't
    one. Raises ET.ParseError on invalid XML."""
    root = ET.fromstring(gpx_bytes)
    for elem in root.iter():
        if localname(elem.tag) == "trkpt":
            return float(elem.attrib["lat"]), float(elem.attrib["lon"])
    return None


def check_routes_json_pin_consistency(routes_json_bytes, gpx_content_resolver):
    """Every route's `pin` must equal the first trkpt of its referenced
    gpx/<file> — this is the enforceable invariant that replaces the
    old zone-floor check: a pin can only be the first point of a
    whitelist-shaped (i.e. pipeline-emitted, i.e. trimmed) file.

    `gpx_content_resolver(filename) -> bytes or None` resolves a bare
    filename (as stored in routes.json's `file` field) to that gpx's
    current content — staged content if it's staged this commit, else
    the working-tree copy; None if it can't be found at all.

    Returns a list of violation strings (empty = OK).
    """
    try:
        data = json.loads(routes_json_bytes)
    except json.JSONDecodeError as exc:
        return [f"routes.json is not valid JSON ({exc})"]

    violations = []
    for route in data.get("routes", []):
        file = route.get("file")
        pin = route.get("pin")
        if not file or not pin or len(pin) != 2:
            violations.append(f"route entry missing 'file' or a valid 'pin': {route!r}")
            continue

        gpx_bytes = gpx_content_resolver(file)
        if gpx_bytes is None:
            violations.append(
                f"route '{file}': referenced gpx/{file} not found (staged or "
                "working tree) — routes.json must not reference a missing file"
            )
            continue

        try:
            first_point = _first_trkpt_from_gpx_bytes(gpx_bytes)
        except ET.ParseError as exc:
            violations.append(f"route '{file}': gpx/{file} is not valid XML ({exc})")
            continue

        if first_point is None:
            violations.append(f"route '{file}': gpx/{file} has no trkpt")
            continue

        lat, lon = first_point
        if round(lat, 6) != round(pin[0], 6) or round(lon, 6) != round(pin[1], 6):
            violations.append(
                f"route '{file}': pin {pin} does not match the first point of "
                f"gpx/{file} ({round(lat, 6)}, {round(lon, 6)}) — pin must be "
                "the first point of the pipeline-emitted (trimmed) file"
            )

    return violations


def run_gate(staged_paths, content_loader, working_tree_reader):
    """Core gate logic, fully injectable for direct unit testing.

    - staged_paths: list of repo-relative path strings.
    - content_loader(path) -> bytes for a STAGED file's content.
    - working_tree_reader(path) -> bytes for a file's current
      working-tree content; must raise FileNotFoundError if missing.
      Used to resolve a routes.json-referenced gpx/<file> when that
      gpx isn't itself staged in this commit.

    Returns a list of violation strings; empty = allow the commit.
    """
    violations = []
    buckets = classify_staged_paths(staged_paths)

    for p in buckets["denied"]:
        violations.append(
            f"staged file on the never-commit deny-list (secrets/logs): {p}"
        )

    for p in buckets["raw_or_done"]:
        violations.append(f"staged file under raw/ or done/: {p}")

    for p in buckets["gpx_outside"]:
        violations.append(f".gpx staged outside gpx/: {p}")

    for p in buckets["gpx_in_dir"]:
        content = content_loader(p)
        for v in check_structure(content):
            violations.append(f"{p}: {v}")

    if buckets["routes_json"]:
        content = content_loader(buckets["routes_json"])
        staged_gpx_set = set(buckets["gpx_in_dir"])

        def gpx_resolver(filename):
            path = f"gpx/{filename}"
            if path in staged_gpx_set:
                return content_loader(path)
            try:
                return working_tree_reader(path)
            except FileNotFoundError:
                return None

        for v in check_routes_json_pin_consistency(content, gpx_resolver):
            violations.append(f"{buckets['routes_json']}: {v}")

    return violations


# --- real git plumbing wiring (not used by unit tests) ---------------

def _repo_root():
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(out.stdout.strip())


def _git_staged_paths():
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in out.stdout.splitlines() if line]


def _git_staged_content_loader():
    def loader(path):
        out = subprocess.run(
            ["git", "show", f":{path}"],
            check=True,
            capture_output=True,
        )
        return out.stdout

    return loader


def _working_tree_reader(repo_root):
    def reader(rel_path):
        path = repo_root / rel_path
        if not path.exists():
            raise FileNotFoundError(str(path))
        return path.read_bytes()

    return reader


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--staged" not in argv:
        print("usage: privacy_gate.py --staged", file=sys.stderr)
        return 2

    repo_root = _repo_root()
    staged_paths = _git_staged_paths()
    if not staged_paths:
        return 0

    violations = run_gate(
        staged_paths,
        _git_staged_content_loader(),
        _working_tree_reader(repo_root),
    )

    if violations:
        print("COMMIT BLOCKED by the privacy gate:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
