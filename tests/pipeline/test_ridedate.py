import unittest
from datetime import date, datetime, timedelta, timezone

from pipeline.ridedate import (
    _EuropePragueFallback,
    extract_ride_date,
    parse_gpx_time,
)


class ParseGpxTimeTests(unittest.TestCase):
    def test_parses_z_suffixed_utc(self):
        dt = parse_gpx_time("2025-04-20T08:48:23.915Z")
        self.assertEqual(dt.year, 2025)
        self.assertEqual(dt.hour, 8)

    def test_none_for_empty(self):
        self.assertIsNone(parse_gpx_time(""))
        self.assertIsNone(parse_gpx_time(None))


class ExtractRideDateTests(unittest.TestCase):
    def test_uses_first_point_with_a_time(self):
        points = [
            {"lat": 0, "lon": 0, "ele": 0, "time": None},
            {"lat": 0, "lon": 0, "ele": 0, "time": "2025-06-15T10:00:00.000Z"},
            {"lat": 0, "lon": 0, "ele": 0, "time": "2025-06-16T10:00:00.000Z"},
        ]
        self.assertEqual(extract_ride_date(points), date(2025, 6, 15))

    def test_late_evening_utc_crosses_midnight_into_next_day_prague(self):
        # 2025-06-15 23:30 UTC is 2025-06-16 01:30 in Prague (CEST, UTC+2
        # in summer) — this is exactly the bug the ⛔ rule guards
        # against: naive UTC-as-local dating would call this the 15th.
        points = [{"lat": 0, "lon": 0, "ele": 0, "time": "2025-06-15T23:30:00.000Z"}]
        self.assertEqual(extract_ride_date(points), date(2025, 6, 16))

    def test_winter_no_dst_offset_stays_same_day(self):
        # 2025-01-15 08:00 UTC is 2025-01-15 09:00 in Prague (CET,
        # UTC+1 in winter) — still the same calendar day.
        points = [{"lat": 0, "lon": 0, "ele": 0, "time": "2025-01-15T08:00:00.000Z"}]
        self.assertEqual(extract_ride_date(points), date(2025, 1, 15))

    def test_no_time_anywhere_returns_none(self):
        points = [{"lat": 0, "lon": 0, "ele": 0, "time": None}]
        self.assertIsNone(extract_ride_date(points))


class EuropePragueFallbackTests(unittest.TestCase):
    """The fallback tzinfo used on Windows, where CPython ships no tz
    database and ZoneInfo("Europe/Prague") raises at import time."""

    def test_matches_zoneinfo_across_a_full_year(self):
        # On this dev box ZoneInfo works, so exhaustively check the
        # fallback against it at 6-hour steps through 2025-2026,
        # including both DST transitions each year.
        try:
            from zoneinfo import ZoneInfo

            real = ZoneInfo("Europe/Prague")
        except Exception:
            self.skipTest("no tz database on this platform")
        fallback = _EuropePragueFallback()
        dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2027, 1, 1, tzinfo=timezone.utc)
        while dt < end:
            self.assertEqual(
                dt.astimezone(real).replace(tzinfo=None),
                dt.astimezone(fallback).replace(tzinfo=None),
                f"mismatch at {dt.isoformat()}",
            )
            dt += timedelta(hours=6)

    def test_dst_transition_boundaries_2025(self):
        fallback = _EuropePragueFallback()
        # Last Sunday of March 2025 is the 30th: 00:59 UTC is still CET
        # (+1), 01:00 UTC is CEST (+2).
        before = datetime(2025, 3, 30, 0, 59, tzinfo=timezone.utc)
        after = datetime(2025, 3, 30, 1, 0, tzinfo=timezone.utc)
        self.assertEqual(before.astimezone(fallback).hour, 1)
        self.assertEqual(after.astimezone(fallback).hour, 3)
        # Last Sunday of October 2025 is the 26th: back to CET at 01:00 UTC.
        before = datetime(2025, 10, 26, 0, 59, tzinfo=timezone.utc)
        after = datetime(2025, 10, 26, 1, 0, tzinfo=timezone.utc)
        self.assertEqual(before.astimezone(fallback).hour, 2)
        self.assertEqual(after.astimezone(fallback).hour, 2)

    def test_late_evening_date_shift_through_fallback(self):
        # The core reason PRAGUE exists: late-evening UTC must date the
        # ride to the next Prague day — verify via the fallback directly.
        fallback = _EuropePragueFallback()
        dt = datetime(2025, 6, 15, 23, 30, tzinfo=timezone.utc)
        self.assertEqual(dt.astimezone(fallback).date(), date(2025, 6, 16))
        dt = datetime(2025, 12, 15, 23, 30, tzinfo=timezone.utc)
        self.assertEqual(dt.astimezone(fallback).date(), date(2025, 12, 16))


if __name__ == "__main__":
    unittest.main()
