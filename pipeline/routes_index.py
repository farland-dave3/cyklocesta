"""routes.json generation — the FROZEN contract (CLAUDE.md).

Always rebuilt by scanning the committed `gpx/` directory (open-
questions #11): idempotent, reproducible from public data alone, and a
rename/delete in gpx/ self-heals on the next run. Stats come from the
simplified line (accepted underestimate of distance/elevation).

Per-file problems (a malformed filename, a slug collision, a corrupt
GPX) are collected and skipped rather than aborting the whole rebuild —
at ~1400 routes, one bad file must not block everyone else's index.
"""

import json
from pathlib import Path

from .geo import bbox, elevation_gain_m, total_distance_km
from .gpx_parse import GpxParseError, parse_points
from .naming import find_gpx_files, parse_filename
from .slugify import slugify


class RoutesIndexError(Exception):
    """Raised for a single route entry that can't be built; callers of
    `build_index`/`write_index` never see this — it's caught internally
    and turned into a skipped-file entry in the returned errors list."""


def _build_route_entry(gpx_path):
    filename = gpx_path.name
    parsed = parse_filename(filename)
    if parsed is None:
        raise RoutesIndexError(
            f"{gpx_path}: filename doesn't match 'YYYY-MM-DD Name.gpx' (with "
            "a real calendar date) — gpx/ must only ever contain pipeline "
            "output. Skipping."
        )
    date_str, name = parsed

    try:
        points = parse_points(gpx_path)
    except GpxParseError as exc:
        raise RoutesIndexError(f"{gpx_path}: {exc}. Skipping.") from exc
    if not points:
        raise RoutesIndexError(f"{gpx_path}: no points. Skipping.")

    stem = filename[: -len(".gpx")]
    slug = slugify(stem)

    distance_km = total_distance_km(points)
    elevation_m = elevation_gain_m([p["ele"] for p in points])
    pin = [round(points[0]["lat"], 6), round(points[0]["lon"], 6)]
    route_bbox = bbox(points)

    return {
        "slug": slug,
        "file": filename,
        "name": name,
        "date": date_str,
        "distance_km": distance_km,
        "elevation_m": elevation_m,
        "pin": pin,
        "bbox": route_bbox,
    }


def build_index(gpx_dir):
    """Scan `gpx_dir` for *.gpx (case-insensitive) and build the
    routes.json dict. Never raises for a single bad file: a malformed
    filename, unparsable GPX, or slug collision is skipped and recorded
    in the returned `errors` list (index still built from the rest).

    Slug collisions are resolved deterministically: files are processed
    in filename-sorted order, the first to claim a slug wins, later
    collisions are skipped as errors.

    Returns (index_dict, errors_list).
    """
    gpx_files = find_gpx_files(gpx_dir)

    errors = []
    routes = []
    seen_slugs = {}

    for p in gpx_files:
        try:
            entry = _build_route_entry(p)
        except RoutesIndexError as exc:
            errors.append(str(exc))
            continue

        if entry["slug"] in seen_slugs:
            errors.append(
                f"Slug collision: '{entry['slug']}' from both "
                f"'{seen_slugs[entry['slug']]}' and '{entry['file']}' — "
                f"keeping '{seen_slugs[entry['slug']]}' (first by filename "
                f"order), skipping '{entry['file']}'."
            )
            continue

        seen_slugs[entry["slug"]] = entry["file"]
        routes.append(entry)

    # Stable sort: ascending name first, then descending date — the
    # earlier name ordering survives as the tiebreak within a date.
    routes.sort(key=lambda r: r["name"])
    routes.sort(key=lambda r: r["date"], reverse=True)

    return {"routes": routes}, errors


def write_index(gpx_dir, index_path):
    """Build the index from gpx_dir and write it to index_path.
    Returns (index_dict, errors_list) — see build_index."""
    index, errors = build_index(gpx_dir)
    index_path = Path(index_path)
    index_path.write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return index, errors
