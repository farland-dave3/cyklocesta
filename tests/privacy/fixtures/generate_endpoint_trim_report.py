#!/usr/bin/env python3
"""Test helper ONLY — not part of the pipeline or the site.

Regenerates the synthetic demo raw rides (scripts/make_demo_data.py's own
build_demo_raw_files()) into a THROWAWAY temp raw/ dir, and runs them
through the real pipeline (pipeline.cli.cmd_process) into a THROWAWAY
temp output dir — never gpx/, never routes.json. Prints a JSON report
consumed by tests/privacy/endpoint-trim.spec.js to verify, against
regenerable synthetic data only (never against the two real committed
rides, whose raw anchors are gitignored and unknown to this repo):

  - endpoint-relative trim floor (open-questions #28): every PUBLISHED
    point sits >= radius_m (the floor, never the jittered radius) from
    BOTH the raw ride's own first raw point and its own last raw point.
  - jitter determinism: processing the identical raw bytes twice (two
    independent output dirs) produces byte-identical published GPX.

Usage: python3 generate_endpoint_trim_report.py
(prints one JSON object to stdout; no side effects outside its own
tempfile.TemporaryDirectory()s)
"""
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # tests/privacy/fixtures -> repo root
sys.path.insert(0, str(REPO_ROOT))

from scripts.make_demo_data import build_demo_raw_files  # noqa: E402
from pipeline.cli import cmd_process  # noqa: E402
from pipeline.gpx_parse import parse_points  # noqa: E402
from pipeline.naming import find_gpx_files  # noqa: E402

RADIUS_M = 300
RADIUS_MAX_M = 600


class _Args:
    """Plain namespace matching what pipeline.cli.cmd_process expects."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


def _run_pipeline(raw_dir, out_dir):
    args = _Args(
        raw_dir=str(raw_dir),
        out_dir=str(out_dir),
        done_dir=str(out_dir / "_unused_done"),  # no_move=True -> never used
        index=str(out_dir / "routes.json"),
        simplify_tolerance=8.0,
        radius_m=RADIUS_M,
        radius_max_m=RADIUS_MAX_M,
        no_move=True,
    )
    # cmd_process() prints per-file progress lines to stdout; swallow them
    # so only our final json.dumps() reaches stdout (stderr still passes
    # through for debugging if something goes wrong).
    with contextlib.redirect_stdout(io.StringIO()):
        rc = cmd_process(args)
    if rc != 0:
        raise SystemExit(f"cmd_process failed with rc={rc}")


def main():
    report = {"radius_m": RADIUS_M, "radius_max_m": RADIUS_MAX_M, "determinism_ok": None, "rides": []}

    with tempfile.TemporaryDirectory(prefix="ebike-test-raw-") as raw_tmp, tempfile.TemporaryDirectory(
        prefix="ebike-test-out-a-"
    ) as out_tmp_a, tempfile.TemporaryDirectory(prefix="ebike-test-out-b-") as out_tmp_b:
        raw_dir = Path(raw_tmp)
        out_dir_a = Path(out_tmp_a)
        out_dir_b = Path(out_tmp_b)

        build_demo_raw_files(raw_dir)
        raw_files = find_gpx_files(raw_dir)  # sorted, deterministic order

        # Snapshot each raw ride's own first/last raw point BEFORE any
        # trimming -- these are exactly the anchors trim_endpoints() uses.
        raw_anchors = {}
        for f in raw_files:
            pts = parse_points(f)
            raw_anchors[f.name] = {
                "first": {"lat": pts[0]["lat"], "lon": pts[0]["lon"]},
                "last": {"lat": pts[-1]["lat"], "lon": pts[-1]["lon"]},
            }

        # Run the real pipeline TWICE on the identical raw bytes, into two
        # independent output dirs, to check jitter determinism.
        _run_pipeline(raw_dir, out_dir_a)
        _run_pipeline(raw_dir, out_dir_b)

        out_files_a = find_gpx_files(out_dir_a)
        out_files_b = find_gpx_files(out_dir_b)

        determinism_ok = [f.name for f in out_files_a] == [f.name for f in out_files_b]
        for fa in out_files_a:
            fb = out_dir_b / fa.name
            if not fb.exists() or fa.read_bytes() != fb.read_bytes():
                determinism_ok = False
        report["determinism_ok"] = determinism_ok

        for f in out_files_a:
            pts = parse_points(f)
            report["rides"].append(
                {
                    "file": f.name,
                    "raw_first": raw_anchors[f.name]["first"],
                    "raw_last": raw_anchors[f.name]["last"],
                    "published_points": [{"lat": p["lat"], "lon": p["lon"]} for p in pts],
                }
            )

    print(json.dumps(report))


if __name__ == "__main__":
    main()
