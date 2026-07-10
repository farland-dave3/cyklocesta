import unittest

from pipeline.geo import haversine_m
from pipeline.privacy import RADIUS_M, RADIUS_MAX_M, compute_endpoint_radii, trim_endpoints


def _point(lat, lon, ele=100.0, time=None):
    return {"lat": lat, "lon": lon, "ele": ele, "time": time}


def _line(n, lat0=50.0, lon0=15.0, step_deg=0.0002):
    """A simple straight line of n points, ~step_deg apart (~22m/step at
    this latitude), so index arithmetic maps predictably to
    distance-from-either-end."""
    return [_point(lat0 + i * step_deg, lon0) for i in range(n)]


RAW_BYTES_A = b"synthetic raw gpx bytes for route A - not real data"
RAW_BYTES_B = b"a totally different synthetic raw gpx byte sequence"


class ComputeEndpointRadiiTests(unittest.TestCase):
    def test_deterministic_same_bytes_same_radii(self):
        r1 = compute_endpoint_radii(RAW_BYTES_A)
        r2 = compute_endpoint_radii(RAW_BYTES_A)
        self.assertEqual(r1, r2)

    def test_different_bytes_give_different_radii(self):
        r1 = compute_endpoint_radii(RAW_BYTES_A)
        r2 = compute_endpoint_radii(RAW_BYTES_B)
        self.assertNotEqual(r1, r2)

    def test_both_radii_within_configured_range(self):
        for raw in (RAW_BYTES_A, RAW_BYTES_B, b"", b"x", b"\x00\x01\x02" * 50):
            radius_start, radius_end = compute_endpoint_radii(raw)
            self.assertGreaterEqual(radius_start, RADIUS_M)
            self.assertLess(radius_start, RADIUS_MAX_M)
            self.assertGreaterEqual(radius_end, RADIUS_M)
            self.assertLess(radius_end, RADIUS_MAX_M)

    def test_start_and_end_radii_are_generally_independent(self):
        # Over several distinct byte strings, start != end for at least
        # most of them (derived from different digest slices).
        samples = [f"sample raw bytes number {i}".encode() for i in range(10)]
        distinct = sum(
            1 for raw in samples for (s, e) in [compute_endpoint_radii(raw)] if s != e
        )
        self.assertGreaterEqual(distinct, 8)

    def test_custom_radius_range_respected(self):
        radius_start, radius_end = compute_endpoint_radii(
            RAW_BYTES_A, radius_m=100, radius_max_m=150
        )
        self.assertGreaterEqual(radius_start, 100)
        self.assertLess(radius_start, 150)
        self.assertGreaterEqual(radius_end, 100)
        self.assertLess(radius_end, 150)


class TrimEndpointsTests(unittest.TestCase):
    def test_points_near_start_anchor_are_removed(self):
        # A straight line of 200 points, ~22m apart, starting at index 0.
        # Even at the minimum radius (300m), the first ~14 points sit
        # within 300m of the start anchor (index 0) and must be gone.
        points = _line(200)
        kept = trim_endpoints(points, RAW_BYTES_A)
        kept_ids = {id(p) for p in kept}
        self.assertNotIn(id(points[0]), kept_ids)  # the anchor itself always goes
        self.assertNotIn(id(points[1]), kept_ids)  # its immediate neighbor too

    def test_points_near_end_anchor_are_removed(self):
        points = _line(200)
        kept = trim_endpoints(points, RAW_BYTES_A)
        kept_ids = {id(p) for p in kept}
        self.assertNotIn(id(points[-1]), kept_ids)
        self.assertNotIn(id(points[-2]), kept_ids)

    def test_mid_route_loop_back_near_start_is_also_removed(self):
        # A path that leaves the start, goes far away, then swings back
        # within a few meters of the start anchor mid-route, then moves
        # away again, then ends far away too.
        points = [
            _point(50.0, 15.0),       # the start anchor itself
            _point(50.05, 15.0),      # far from start
            _point(50.0001, 15.0),    # mid-route: back within meters of start
            _point(50.06, 15.0),      # far again
            _point(51.0, 15.0),       # the end anchor
        ]
        kept = trim_endpoints(points, RAW_BYTES_A)
        kept_lats = [p["lat"] for p in kept]
        self.assertNotIn(50.0, kept_lats)      # start anchor gone
        self.assertNotIn(50.0001, kept_lats)   # mid-route pass-by near start gone too
        self.assertNotIn(51.0, kept_lats)      # end anchor gone
        self.assertIn(50.05, kept_lats)        # genuinely far points survive
        self.assertIn(50.06, kept_lats)

    def test_survivors_are_at_least_both_radii_from_their_anchors(self):
        points = _line(300)
        radius_start, radius_end = compute_endpoint_radii(RAW_BYTES_A)
        kept = trim_endpoints(points, RAW_BYTES_A)
        start, end = points[0], points[-1]
        self.assertGreater(len(kept), 0)
        for p in kept:
            d_start = haversine_m(p["lat"], p["lon"], start["lat"], start["lon"])
            d_end = haversine_m(p["lat"], p["lon"], end["lat"], end["lon"])
            self.assertGreaterEqual(d_start, radius_start)
            self.assertGreaterEqual(d_end, radius_end)

    def test_entirely_within_radius_returns_empty(self):
        # A short track (~40m end to end) is well within even the
        # minimum 300m radius of both its own endpoints.
        points = [_point(50.0 + i * 0.00003, 15.0) for i in range(10)]
        kept = trim_endpoints(points, RAW_BYTES_A)
        self.assertEqual(kept, [])

    def test_empty_input_returns_empty(self):
        self.assertEqual(trim_endpoints([], RAW_BYTES_A), [])

    def test_pin_is_first_surviving_point_not_raw_start(self):
        points = _line(200)
        kept = trim_endpoints(points, RAW_BYTES_A)
        self.assertGreater(len(kept), 0)
        pin = kept[0]
        self.assertNotEqual((pin["lat"], pin["lon"]), (points[0]["lat"], points[0]["lon"]))

    def test_different_raw_bytes_still_both_trim_sensibly(self):
        # Same geometry, different raw bytes -> different (independent)
        # radii, but both must still produce a well-formed trim.
        points = _line(300)
        kept_a = trim_endpoints(points, RAW_BYTES_A)
        kept_b = trim_endpoints(points, RAW_BYTES_B)
        self.assertGreater(len(kept_a), 0)
        self.assertGreater(len(kept_b), 0)

    def test_custom_radius_overrides_respected(self):
        points = _line(300)
        kept_default = trim_endpoints(points, RAW_BYTES_A)
        kept_tiny = trim_endpoints(points, RAW_BYTES_A, radius_m=1, radius_max_m=2)
        # A much smaller radius range trims far fewer points.
        self.assertGreater(len(kept_tiny), len(kept_default))

    def test_filename_is_irrelevant_only_raw_bytes_matter(self):
        # The radius is keyed on raw file BYTES, not the filename — a
        # rename must never change the trim (renames are radius-
        # irrelevant by construction, since filename isn't an input at
        # all here).
        points = _line(200)
        kept_1 = trim_endpoints(points, RAW_BYTES_A)
        kept_2 = trim_endpoints(points, RAW_BYTES_A)  # same bytes, "different name" N/A
        self.assertEqual([p["lat"] for p in kept_1], [p["lat"] for p in kept_2])


if __name__ == "__main__":
    unittest.main()
