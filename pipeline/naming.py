"""Filename convention: `YYYY-MM-DD Name.gpx` is the route ID, display
name, and uniqueness key (CLAUDE.md ⛔). Shared by `process` (validates
raw/ input) and `rebuild-index` (validates gpx/ output, since routes.json
is always rebuilt by scanning gpx/ and depends on this parse).
"""

import re
from datetime import date
from pathlib import Path

FILENAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}) (.+)\.gpx$", re.IGNORECASE)


def parse_filename(filename):
    """Return (date_str, name) for a valid 'YYYY-MM-DD Name.gpx' whose
    date part is a real calendar date, or None if it doesn't match
    (either the shape, or the date itself — e.g. '2026-13-45' passes
    the regex but isn't a real day)."""
    m = FILENAME_RE.match(filename)
    if not m:
        return None
    date_str, name = m.group(1), m.group(2)
    year, month, day = (int(part) for part in date_str.split("-"))
    try:
        date(year, month, day)
    except ValueError:
        return None
    return date_str, name


def is_valid_filename(filename):
    return parse_filename(filename) is not None


def find_gpx_files(directory):
    """List *.gpx files in `directory`, matched case-insensitively (so
    '.GPX' isn't silently skipped on a case-sensitive filesystem, nor
    inconsistently matched depending on OS). Sorted by filename for
    deterministic processing order. Returns [] if directory is missing."""
    directory = Path(directory)
    if not directory.exists():
        return []
    return sorted(
        (p for p in directory.iterdir() if p.is_file() and p.suffix.lower() == ".gpx"),
        key=lambda p: p.name,
    )
