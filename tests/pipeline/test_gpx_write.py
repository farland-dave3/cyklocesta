import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from pipeline.gpx_parse import parse_points
from pipeline.gpx_write import render_gpx, write_gpx
from pipeline.xmlutil import localname

GPX_NS = "{http://www.topografix.com/GPX/1/1}"


class RenderGpxTests(unittest.TestCase):
    def test_only_whitelisted_tags_present(self):
        points = [
            {"lat": 50.123456, "lon": 15.654321, "ele": 400.123, "time": "2025-01-01T00:00:00Z"},
            {"lat": 50.123556, "lon": 15.654421, "ele": 401.5, "time": "2025-01-01T00:00:01Z"},
        ]
        text = render_gpx(points)
        root = ET.fromstring(text)
        tags = {localname(e.tag) for e in root.iter()}
        self.assertEqual(tags, {"gpx", "trk", "trkseg", "trkpt", "ele"})

    def test_time_metadata_wpt_extensions_never_survive(self):
        # Simulate a raw-parsed point set that (in a buggy writer) might
        # tempt someone to pass through extra fields; render_gpx must
        # only ever look at lat/lon/ele.
        points = [{"lat": 1.0, "lon": 2.0, "ele": 3.0, "time": "2025-01-01T00:00:00Z"}]
        text = render_gpx(points)
        self.assertNotIn("<time", text)
        self.assertNotIn("<metadata", text)
        self.assertNotIn("<wpt", text)
        self.assertNotIn("<extensions", text)

    def test_lat_lon_six_decimals_ele_one_decimal(self):
        points = [{"lat": 50.1, "lon": 15.2, "ele": 400.0}]
        text = render_gpx(points)
        self.assertIn('lat="50.100000"', text)
        self.assertIn('lon="15.200000"', text)
        self.assertIn("<ele>400.0</ele>", text)

    def test_no_track_name(self):
        points = [{"lat": 1.0, "lon": 2.0, "ele": 3.0}]
        text = render_gpx(points)
        self.assertNotIn("<name", text)

    def test_write_gpx_then_reparse_roundtrips_points(self):
        points = [
            {"lat": 50.111111, "lon": 15.222222, "ele": 300.4},
            {"lat": 50.111211, "lon": 15.222322, "ele": 301.1},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026-01-01 Test.gpx"
            write_gpx(path, points)
            reparsed = parse_points(path)
        self.assertEqual(len(reparsed), 2)
        self.assertAlmostEqual(reparsed[0]["lat"], 50.111111, places=6)
        self.assertAlmostEqual(reparsed[0]["ele"], 300.4, places=1)
        self.assertIsNone(reparsed[0]["time"])  # time was stripped on emit


class FullPipelineWhitelistTests(unittest.TestCase):
    """Feed a GPX shaped like a real Bosch Flow export (metadata, time,
    would-be wpt/extensions if firmware added them) through parse ->
    render and confirm none of it survives."""

    def test_metadata_and_time_stripped_end_to_end(self):
        raw_gpx = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<gpx version="1.1" creator="https://www.bosch-ebike.com/" '
            'xmlns="http://www.topografix.com/GPX/1/1">'
            "<metadata><name>eBike ride</name></metadata>"
            "<trk><trkseg>"
            '<trkpt lat="50.0" lon="15.0"><ele>400.0</ele>'
            "<time>2025-04-20T08:48:23.915Z</time></trkpt>"
            '<trkpt lat="50.001" lon="15.001"><ele>401.0</ele>'
            "<time>2025-04-20T08:48:24.915Z</time></trkpt>"
            "</trkseg></trk></gpx>"
        )
        with tempfile.TemporaryDirectory() as tmp:
            raw_path = Path(tmp) / "raw.gpx"
            raw_path.write_text(raw_gpx, encoding="utf-8")
            points = parse_points(raw_path)
            out_text = render_gpx(points)

        for forbidden in ("<time", "<metadata", "<wpt", "<extensions", "eBike ride"):
            self.assertNotIn(forbidden, out_text)
        root = ET.fromstring(out_text)
        tags = {localname(e.tag) for e in root.iter()}
        self.assertEqual(tags, {"gpx", "trk", "trkseg", "trkpt", "ele"})


if __name__ == "__main__":
    unittest.main()
