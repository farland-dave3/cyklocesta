"""Ride-date extraction: GPX <time> is UTC; the filename date must be the
Europe/Prague *local* date of the ride, or a late-evening ride gets
dated the following day. Extract BEFORE <time> is stripped on emit.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

PRAGUE = ZoneInfo("Europe/Prague")


def parse_gpx_time(text):
    """Parse a GPX <time> string (e.g. '2025-04-20T08:48:23.915Z') to an
    aware UTC datetime. Returns None if text is None/empty."""
    if not text:
        return None
    s = text.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def extract_ride_date(points):
    """Return the Europe/Prague local date (datetime.date) of the ride,
    derived from the FIRST point that has a <time>. Returns None if no
    point carries a time (e.g. already-stripped published GPX)."""
    for p in points:
        t = p.get("time")
        if t:
            dt = parse_gpx_time(t)
            if dt is None:
                continue
            return dt.astimezone(PRAGUE).date()
    return None
