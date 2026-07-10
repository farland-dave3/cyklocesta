"""CLI: `python3 -m pipeline <report|process|rebuild-index>`.

Phase 1 workflow (open-questions #22): the maintainer manually renames
files dropped in raw/ to 'YYYY-MM-DD Name.gpx' (report helps pick the
date), then `process` batch-validates + trims + simplifies + emits them
into gpx/, moves originals to done/, and regenerates routes.json.
"""

import argparse
import shutil
import sys
import unicodedata
from pathlib import Path

from .geo import DEFAULT_SIMPLIFY_TOLERANCE_M, douglas_peucker, total_distance_km
from .gpx_parse import GpxParseError, parse_points
from .gpx_write import write_gpx
from .naming import find_gpx_files, is_valid_filename, parse_filename
from .privacy import RADIUS_M, RADIUS_MAX_M, trim_endpoints
from .ridedate import extract_ride_date
from .routes_index import write_index

DEFAULT_RAW_DIR = "raw"
DEFAULT_OUT_DIR = "gpx"
DEFAULT_DONE_DIR = "done"
DEFAULT_INDEX = "routes.json"


def cmd_report(args):
    raw_dir = Path(args.raw_dir)
    files = find_gpx_files(raw_dir)
    if not files:
        print(f"No .gpx files found in {raw_dir}")
        return 0

    print(f"{'file':<40} {'ride_date (Prague)':<20} {'points':>8} {'distance_km':>12}")
    exit_code = 0
    for f in files:
        try:
            points = parse_points(f)
        except GpxParseError as exc:
            print(f"{f.name}: ERROR: {exc}", file=sys.stderr)
            exit_code = 1
            continue
        date = extract_ride_date(points)
        date_str = date.isoformat() if date else "UNKNOWN (no <time> found)"
        dist = total_distance_km(points)
        print(f"{f.name:<40} {date_str:<20} {len(points):>8} {dist:>12.1f}")
    return exit_code


def cmd_process(args):
    raw_dir = Path(args.raw_dir)
    out_dir = Path(args.out_dir)
    done_dir = Path(args.done_dir)

    files = find_gpx_files(raw_dir)

    offenders = [f.name for f in files if not is_valid_filename(f.name)]
    if offenders:
        print(
            "Refusing to process: these filenames don't match "
            "'YYYY-MM-DD Name.gpx' — rename them first:",
            file=sys.stderr,
        )
        for o in offenders:
            print(f"  - {o}", file=sys.stderr)
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    if not args.no_move:
        done_dir.mkdir(parents=True, exist_ok=True)

    processed = 0
    skipped = 0
    errors = 0

    for f in files:
        output_filename = unicodedata.normalize("NFC", f.name)
        out_path = out_dir / output_filename
        if out_path.exists():
            print(
                f"error: {out_path} already exists — refusing to overwrite; "
                f"skipping {f.name}",
                file=sys.stderr,
            )
            errors += 1
            continue

        try:
            raw_bytes = f.read_bytes()
        except OSError as exc:
            print(f"error: {f.name}: {exc}", file=sys.stderr)
            errors += 1
            continue

        try:
            points = parse_points(f)
        except GpxParseError as exc:
            print(f"error: {f.name}: {exc}", file=sys.stderr)
            errors += 1
            continue

        # Extract the ride date BEFORE <time> is stripped (soft sanity
        # check against the manually-chosen filename date only; the
        # filename remains the authoritative date per the ID contract).
        extracted_date = extract_ride_date(points)
        parsed_name = parse_filename(f.name)
        if extracted_date and parsed_name:
            filename_date_str, _ = parsed_name
            if extracted_date.isoformat() != filename_date_str:
                print(
                    f"warning: {f.name}: filename date {filename_date_str} != "
                    f"ride date {extracted_date.isoformat()} (Europe/Prague, "
                    "from first trackpoint)",
                    file=sys.stderr,
                )

        kept = trim_endpoints(
            points, raw_bytes, radius_m=args.radius_m, radius_max_m=args.radius_max_m
        )
        if not kept:
            print(
                f"warning: {f.name}: entire track falls within the endpoint "
                "trim radii — skipped, NOT published (raw file left in place "
                "for manual review)",
                file=sys.stderr,
            )
            skipped += 1
            continue

        simplified = douglas_peucker(kept, tolerance=args.simplify_tolerance)
        write_gpx(out_path, simplified)
        print(
            f"{f.name} -> {out_dir.name}/{output_filename} "
            f"({len(points)} raw -> {len(kept)} after trim -> "
            f"{len(simplified)} after simplify)"
        )

        if not args.no_move:
            shutil.move(str(f), str(done_dir / f.name))

        processed += 1

    index, index_errors = write_index(out_dir, args.index)
    print(f"routes.json regenerated: {len(index['routes'])} routes -> {args.index}")
    if index_errors:
        print("routes.json: some gpx/ files were skipped:", file=sys.stderr)
        for e in index_errors:
            print(f"  - {e}", file=sys.stderr)

    print(f"done: {processed} processed, {skipped} skipped (fully within trim radii), {errors} errors")
    return 1 if (errors or index_errors) else 0


def cmd_rebuild_index(args):
    out_dir = Path(args.out_dir)
    index, index_errors = write_index(out_dir, args.index)
    print(f"routes.json regenerated: {len(index['routes'])} routes -> {args.index}")
    if index_errors:
        print("routes.json: some gpx/ files were skipped:", file=sys.stderr)
        for e in index_errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="pipeline", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_report = sub.add_parser("report", help="Report raw/ ride dates/stats (read-only)")
    p_report.add_argument("--raw-dir", default=DEFAULT_RAW_DIR)
    p_report.set_defaults(func=cmd_report)

    p_process = sub.add_parser("process", help="Batch-process raw/ into gpx/ + routes.json")
    p_process.add_argument("--raw-dir", default=DEFAULT_RAW_DIR)
    p_process.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    p_process.add_argument("--done-dir", default=DEFAULT_DONE_DIR)
    p_process.add_argument("--index", default=DEFAULT_INDEX)
    p_process.add_argument(
        "--simplify-tolerance", type=float, default=DEFAULT_SIMPLIFY_TOLERANCE_M
    )
    p_process.add_argument(
        "--radius-m", type=float, default=RADIUS_M,
        help="Endpoint trim radius floor, in meters (default: 300)",
    )
    p_process.add_argument(
        "--radius-max-m", type=float, default=RADIUS_MAX_M,
        help="Endpoint trim radius ceiling, in meters (default: 600)",
    )
    p_process.add_argument(
        "--no-move", action="store_true", help="Leave raw inputs in place"
    )
    p_process.set_defaults(func=cmd_process)

    p_rebuild = sub.add_parser("rebuild-index", help="Regenerate routes.json from gpx/")
    p_rebuild.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    p_rebuild.add_argument("--index", default=DEFAULT_INDEX)
    p_rebuild.set_defaults(func=cmd_rebuild_index)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
