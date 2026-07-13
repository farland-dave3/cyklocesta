"""Ride-date extraction: GPX <time> is UTC; the filename date must be the
Europe/Prague *local* date of the ride, or a late-evening ride gets
dated the following day. Extract BEFORE <time> is stripped on emit.
"""

from datetime import datetime, timedelta, tzinfo


def _last_sunday_utc(year, month, hour):
    """Naive-UTC datetime of the last Sunday of the given month at `hour`."""
    d = datetime(year, month, 31, hour)
    return d - timedelta(days=(d.weekday() + 1) % 7)


class _EuropePragueFallback(tzinfo):
    """Europe/Prague without a tz database. Windows ships no zoneinfo data,
    so ZoneInfo("Europe/Prague") fails there unless the third-party `tzdata`
    package is installed — which would break the zero-setup rule. Prague has
    followed the EU rule unchanged since 1996: UTC+1, switching to UTC+2
    between the last Sundays of March and October at 01:00 UTC.
    """

    def _offset_from_utc(self, u):
        """Offset for a naive-UTC datetime `u`."""
        if _last_sunday_utc(u.year, 3, 1) <= u < _last_sunday_utc(u.year, 10, 1):
            return timedelta(hours=2)
        return timedelta(hours=1)

    def fromutc(self, dt):
        u = dt.replace(tzinfo=None)
        return (u + self._offset_from_utc(u)).replace(tzinfo=self)

    def utcoffset(self, dt):
        if dt is None:
            return timedelta(hours=1)
        # dt is local; recover the offset via the UTC-side rule. Around the
        # transitions this is ambiguous by an hour — irrelevant for dates.
        return self._offset_from_utc(dt.replace(tzinfo=None) - timedelta(hours=1))

    def dst(self, dt):
        return self.utcoffset(dt) - timedelta(hours=1)

    def tzname(self, dt):
        return "CEST" if self.dst(dt) else "CET"


try:
    from zoneinfo import ZoneInfo

    PRAGUE = ZoneInfo("Europe/Prague")
except Exception:
    PRAGUE = _EuropePragueFallback()


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
