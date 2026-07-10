"""Generate synthetic demo data so the site + tests have something real
to render, without ever touching the real raw/ ride.

Builds 3 fully synthetic rides — parametric loops / a bent point-to-
point path at fabricated Czech-countryside coordinates, NEVER derived
from or shaped like the real ride (CLAUDE.md fixtures policy) — as
raw-style GPX (with <time>/<metadata>, mimicking Bosch Flow's export
shape), runs them through the real pipeline, and writes the result
into gpx/ + regenerates routes.json.

Endpoint-relative trim (2026-07-06 design change) needs ZERO privacy
config: every ride is trimmed relative to its own raw first/last point,
with radii jittered from a hash of the raw file's bytes (see
pipeline/privacy.py). So the demo geometry just needs a cluster of
points within ~600m of BOTH the raw start and the raw end to visibly
exercise trimming at both ends, with no setup at all:
  - Rides 1 and 3 are loops, so their start and end are (almost) the
    same point — trimming both ends necessarily hits the same shared
    cluster there.
  - Ride 2 is a genuine point-to-point (two distinct fabricated
    locations, joined by a bent path so DP keeps the bend), with dense
    point spacing so several points sit within ~600m of EACH end
    independently.

Usage: python3 scripts/make_demo_data.py
"""

import math
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline.cli import cmd_process  # noqa: E402
from pipeline.naming import find_gpx_files  # noqa: E402


#: This script only ever knows how to (re)generate exactly these three
#: files. It must NEVER delete anything else in gpx/ — once real routes
#: exist there, a naive "clear gpx/ then regenerate" would destroy them.
DEMO_ROUTE_FILENAMES = {
    "2026-06-01 Demo Loop.gpx",
    "2026-06-08 Podhuri Point To Point.gpx",
    "2026-06-15 Kopcovita Smycka.gpx",
}

# Fabricated Czech-countryside-ish coordinates. Not derived from any
# real ride; picked as plausible open-countryside points.
RIDE_1_CENTER = (49.8000, 15.5000)  # "Demo Loop"
RIDE_2_START = (49.6500, 16.1000)  # "Podhuri Point To Point" — start
RIDE_2_END = (49.6900, 16.1600)  # "Podhuri Point To Point" — end (~6 km away)
RIDE_3_CENTER = (50.1000, 14.8500)  # "Kopcovita Smycka"


def _circle_loop(origin, radius_deg, n_points, ele_base, ele_amp):
    """A closed loop of points around `origin` (roughly `radius_deg`
    degrees out), so the start/end sit at the same spot — like a real
    loop ride — with a gentle elevation sine wave overlaid."""
    lat0, lon0 = origin
    points = []
    for i in range(n_points):
        theta = 2 * math.pi * i / (n_points - 1)
        lat = lat0 + radius_deg * math.sin(theta)
        lon = lon0 + radius_deg * math.cos(theta) * 1.4  # elongate slightly
        ele = ele_base + ele_amp * math.sin(theta * 2) + 0.3 * math.sin(theta * 37)
        points.append((lat, lon, ele))
    return points


def _bent_point_to_point(origin_a, origin_b, bend_frac, n_points, ele_base, ele_amp):
    """A two-segment path from origin_a to origin_b via an off-line
    bend point (so it isn't perfectly collinear — DP keeps the bend).
    Dense point spacing means several points land within ~600m of EACH
    raw endpoint just from the path's own progression, no dwell
    clusters needed."""
    lat_a, lon_a = origin_a
    lat_b, lon_b = origin_b
    mid_lat = (lat_a + lat_b) / 2
    mid_lon = (lon_a + lon_b) / 2
    dlat = lat_b - lat_a
    dlon = lon_b - lon_a
    # Perpendicular offset from the A-B midpoint, so the path visibly bends.
    bend_lat = mid_lat - dlon * bend_frac
    bend_lon = mid_lon + dlat * bend_frac

    half = n_points // 2
    points = []
    for i in range(half):
        t = i / (half - 1)
        lat = lat_a + (bend_lat - lat_a) * t
        lon = lon_a + (bend_lon - lon_a) * t
        ele = ele_base + ele_amp * 0.5 * t + 0.3 * math.sin(i * 1.7)
        points.append((lat, lon, ele))
    for i in range(half):
        t = i / (half - 1)
        lat = bend_lat + (lat_b - bend_lat) * t
        lon = bend_lon + (lon_b - bend_lon) * t
        ele = ele_base + ele_amp * 0.5 + ele_amp * 0.5 * t + 0.3 * math.sin(i * 1.7)
        points.append((lat, lon, ele))
    return points


def _write_raw_gpx(path, points, start_iso_utc):
    """Write a Bosch-Flow-shaped raw GPX: single <trk><trkseg>, per-point
    <time> (1 Hz), <metadata><name>eBike ride</name></metadata> — mimics
    the real export structure this pipeline is built to consume."""
    from datetime import datetime, timedelta, timezone

    start = datetime.fromisoformat(start_iso_utc).replace(tzinfo=timezone.utc)
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="https://www.bosch-ebike.com/" '
        'xmlns="http://www.topografix.com/GPX/1/1">',
        "<metadata><name>eBike ride</name></metadata><trk><trkseg>",
    ]
    for i, (lat, lon, ele) in enumerate(points):
        t = start + timedelta(seconds=i)
        t_str = t.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        parts.append(
            f'<trkpt lat="{lat:.6f}" lon="{lon:.6f}"><ele>{ele:.2f}</ele>'
            f"<time>{t_str}</time></trkpt>"
        )
    parts.append("</trkseg></trk></gpx>")
    path.write_text("".join(parts), encoding="utf-8")


def build_demo_raw_files(raw_dir):
    raw_dir.mkdir(parents=True, exist_ok=True)

    # Ride 1: a loop — start and end (theta=0/2pi) are the same spot,
    # so BOTH endpoint trims hit that one shared cluster of points.
    ride1 = _circle_loop(RIDE_1_CENTER, radius_deg=0.02, n_points=400, ele_base=420, ele_amp=25)
    _write_raw_gpx(raw_dir / "2026-06-01 Demo Loop.gpx", ride1, "2026-06-01T14:00:00")

    # Ride 2: a genuine point-to-point between two DIFFERENT fabricated
    # locations (~6 km apart, via a bend so it isn't a literal straight
    # line) — dense spacing (~500 points over ~6+ km, ~12m/point) means
    # ~25-50 points land within the [300, 600) m trim band at EACH end
    # independently, demonstrating that the two endpoint radii are
    # applied to two distinct places, not just one shared spot.
    ride2 = _bent_point_to_point(
        RIDE_2_START, RIDE_2_END, bend_frac=0.3, n_points=500, ele_base=380, ele_amp=60
    )
    _write_raw_gpx(raw_dir / "2026-06-08 Podhuri Point To Point.gpx", ride2, "2026-06-08T08:30:00")

    # Ride 3: a bigger loop with more elevation — same shared-cluster
    # start/end characteristic as ride 1.
    ride3 = _circle_loop(RIDE_3_CENTER, radius_deg=0.035, n_points=600, ele_base=310, ele_amp=90)
    _write_raw_gpx(raw_dir / "2026-06-15 Kopcovita Smycka.gpx", ride3, "2026-06-15T16:45:00")


class _Args:
    """Plain namespace matching what pipeline.cli.cmd_process expects."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


class ForeignFilesError(Exception):
    """Raised when gpx_dir contains .gpx files this script didn't
    generate — refuse to touch the directory rather than risk deleting
    real routes."""


def clear_own_previous_output(gpx_dir):
    """Demo data should be regeneratable idempotently: clear only THIS
    script's own previous output (by exact filename), so `process`'s
    overwrite-refusal doesn't block a re-run. Refuses (raises
    ForeignFilesError, touching nothing) if gpx_dir contains anything
    this script didn't generate — once real routes exist, blindly
    clearing *.gpx would delete them."""
    existing = find_gpx_files(gpx_dir)
    unknown = [p for p in existing if p.name not in DEMO_ROUTE_FILENAMES]
    if unknown:
        raise ForeignFilesError(
            "gpx/ contains files this script did not generate — refusing "
            "to touch it (would risk deleting real routes): "
            + ", ".join(p.name for p in unknown)
        )
    for p in existing:
        p.unlink()


def main():
    gpx_dir = REPO_ROOT / "gpx"
    index_path = REPO_ROOT / "routes.json"

    try:
        clear_own_previous_output(gpx_dir)
    except ForeignFilesError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    with tempfile.TemporaryDirectory(prefix="ebike-demo-") as tmp:
        tmp = Path(tmp)
        raw_dir = tmp / "raw"
        done_dir = tmp / "done"

        build_demo_raw_files(raw_dir)

        args = _Args(
            raw_dir=str(raw_dir),
            out_dir=str(gpx_dir),
            done_dir=str(done_dir),
            index=str(index_path),
            simplify_tolerance=8.0,
            radius_m=300,
            radius_max_m=600,
            no_move=True,
        )

        rc = cmd_process(args)
        if rc != 0:
            sys.exit(rc)

    print(f"\nDemo data written to {gpx_dir} and {index_path}")


if __name__ == "__main__":
    main()
