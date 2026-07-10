import unittest
from datetime import date

from pipeline.ridedate import extract_ride_date, parse_gpx_time


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


if __name__ == "__main__":
    unittest.main()
