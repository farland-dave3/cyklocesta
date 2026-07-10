import math
import unittest

from pipeline.geo import (
    bbox,
    douglas_peucker,
    elevation_gain_m,
    haversine_m,
    total_distance_km,
)


class HaversineTests(unittest.TestCase):
    def test_zero_distance(self):
        self.assertEqual(haversine_m(50.0, 15.0, 50.0, 15.0), 0.0)

    def test_known_distance_one_degree_latitude(self):
        # ~1 degree of latitude is ~111.19 km everywhere.
        d = haversine_m(50.0, 15.0, 51.0, 15.0)
        self.assertAlmostEqual(d / 1000.0, 111.19, delta=0.5)


class TotalDistanceTests(unittest.TestCase):
    def test_single_point_is_zero(self):
        self.assertEqual(total_distance_km([{"lat": 50.0, "lon": 15.0}]), 0.0)

    def test_sums_consecutive_segments(self):
        # Three points forming an L; each leg ~111.19 km (1 deg lat) and
        # ~1 deg lon at the equator-ish scale factor at lat 0.
        points = [
            {"lat": 0.0, "lon": 0.0},
            {"lat": 1.0, "lon": 0.0},
            {"lat": 1.0, "lon": 1.0},
        ]
        dist = total_distance_km(points)
        # leg1 ~111.19 km, leg2 (1 deg lon at lat=1, ~cos(1deg)) ~111.18 km
        self.assertAlmostEqual(dist, 222.4, delta=1.0)


class DouglasPeuckerTests(unittest.TestCase):
    def test_fewer_than_three_points_returned_as_is(self):
        pts = [{"lat": 0, "lon": 0}, {"lat": 1, "lon": 1}]
        self.assertEqual(douglas_peucker(pts, tolerance=8.0), pts)

    def test_collinear_points_collapse_to_endpoints(self):
        # A perfectly straight line: every interior point is exactly on
        # the chord, so DP should keep only the two endpoints.
        pts = [{"lat": 0.0, "lon": lon / 1000.0, "ele": 100.0} for lon in range(0, 101)]
        simplified = douglas_peucker(pts, tolerance=8.0)
        self.assertEqual(len(simplified), 2)
        self.assertEqual(simplified[0], pts[0])
        self.assertEqual(simplified[-1], pts[-1])

    def test_significant_deviation_is_kept(self):
        # A path that bulges out ~50m from the chord at its midpoint
        # must survive an 8m tolerance.
        pts = [
            {"lat": 0.0, "lon": 0.0},
            {"lat": 0.0005, "lon": 0.05},  # ~55m north of the chord
            {"lat": 0.0, "lon": 0.1},
        ]
        simplified = douglas_peucker(pts, tolerance=8.0)
        self.assertEqual(len(simplified), 3)

    def test_reduces_point_count_on_noisy_nearly_straight_line(self):
        # Small (<8m) zig-zag noise on an otherwise straight line should
        # be simplified away, reducing point count substantially.
        pts = []
        for i in range(200):
            lon = i / 2000.0  # ~55m per step over the whole line
            jitter = 0.00002 * math.sin(i)  # a few meters, well under tolerance
            pts.append({"lat": jitter, "lon": lon, "ele": 100.0})
        simplified = douglas_peucker(pts, tolerance=8.0)
        self.assertLess(len(simplified), len(pts))
        self.assertGreaterEqual(len(simplified), 2)


class ElevationGainTests(unittest.TestCase):
    def test_flat_profile_is_zero(self):
        self.assertEqual(elevation_gain_m([100.0] * 20), 0)

    def test_simple_climb(self):
        self.assertEqual(elevation_gain_m([100.0, 150.0]), 50)

    def test_climb_then_descent_only_counts_the_climb(self):
        self.assertEqual(elevation_gain_m([100.0, 150.0, 100.0]), 50)

    def test_hysteresis_filters_small_noise_climbs(self):
        # Noise of +/-1m riding on a flat baseline must NOT accumulate
        # into a large "gain" the way naive positive-delta summation
        # would (that's exactly the bug #11b calls out).
        elevations = [100.0]
        for i in range(1, 200):
            elevations.append(100.0 + (1.0 if i % 2 == 0 else -1.0))
        naive_gain = sum(
            max(0.0, b - a) for a, b in zip(elevations, elevations[1:])
        )
        smoothed = elevation_gain_m(elevations, threshold=3.0)
        self.assertGreater(naive_gain, 50)  # naive summation is grossly inflated
        # Hysteresis correctly sees this as ~flat: bounded by one
        # threshold-unit (the Schmitt-trigger-style tracker can end a
        # run "mid-swing", stuck at the first sub-threshold excursion,
        # rather than exactly 0) — nowhere near the naive figure.
        self.assertLessEqual(smoothed, 3)

    def test_real_climb_survives_small_superimposed_noise(self):
        # A genuine 100m climb over 100 samples, with +/-1m noise on
        # top, should still register as ~100m gain (not exactly, since
        # the hysteresis eats a little at the very start, but close).
        elevations = []
        for i in range(101):
            base = 100.0 + i  # 1m/sample climb, 100m total
            noise = 1.0 if i % 2 == 0 else -1.0
            elevations.append(base + noise)
        gain = elevation_gain_m(elevations, threshold=3.0)
        self.assertGreater(gain, 90)
        self.assertLessEqual(gain, 102)

    def test_none_values_are_ignored(self):
        self.assertEqual(elevation_gain_m([100.0, None, 150.0]), 50)


class BboxTests(unittest.TestCase):
    def test_bbox_of_points(self):
        points = [
            {"lat": 49.9, "lon": 15.4},
            {"lat": 50.2, "lon": 15.7},
            {"lat": 50.0, "lon": 15.5},
        ]
        self.assertEqual(bbox(points), [[49.9, 15.4], [50.2, 15.7]])


if __name__ == "__main__":
    unittest.main()
