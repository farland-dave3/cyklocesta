import json
import tempfile
import unittest
from pathlib import Path

from pipeline.cli import build_parser


def _write_raw_gpx(path, points, start_iso="2026-06-01T12:00:00.000Z"):
    """points: list of (lat, lon, ele) tuples. Mimics a real Flow export
    (metadata, per-point time) as input to `process`."""
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="https://www.bosch-ebike.com/" '
        'xmlns="http://www.topografix.com/GPX/1/1">',
        "<metadata><name>eBike ride</name></metadata><trk><trkseg>",
    ]
    for lat, lon, ele in points:
        parts.append(f'<trkpt lat="{lat:.6f}" lon="{lon:.6f}"><ele>{ele:.1f}</ele>'
                      f"<time>{start_iso}</time></trkpt>")
    parts.append("</trkseg></trk></gpx>")
    path.write_text("".join(parts), encoding="utf-8")


def _straight_line(n=300, lat0=51.0, lon0=15.0):
    # Long enough (~7.9 km end to end) that it survives endpoint
    # trimming regardless of the specific per-file jittered radii
    # (max possible combined trim is <1.2 km: 600m + 600m) — avoids
    # flaky tests that would otherwise depend on which raw-byte hash a
    # given test's content happens to produce.
    return [(lat0 + i * 0.0002, lon0 + i * 0.0002, 300.0 + i * 0.5) for i in range(n)]


def _run(argv):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


class ProcessCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.raw_dir = self.root / "raw"
        self.out_dir = self.root / "gpx"
        self.done_dir = self.root / "done"
        self.index_path = self.root / "routes.json"
        self.raw_dir.mkdir()

    def _argv(self, extra=None):
        argv = [
            "process",
            "--raw-dir", str(self.raw_dir),
            "--out-dir", str(self.out_dir),
            "--done-dir", str(self.done_dir),
            "--index", str(self.index_path),
        ]
        return argv + (extra or [])

    def test_process_runs_with_zero_setup_no_config_files(self):
        # No privacy-zones.json, no salt, no zone list — nothing but the
        # raw GPX itself. This is the core of the 2026-07-06 design
        # change: the pipeline must run end-to-end with zero setup.
        self.assertFalse((self.root / "privacy-zones.json").exists())
        _write_raw_gpx(self.raw_dir / "2026-06-01 Straight Line.gpx", _straight_line())
        rc = _run(self._argv())
        self.assertEqual(rc, 0)
        self.assertTrue((self.out_dir / "2026-06-01 Straight Line.gpx").exists())

    def test_rejects_bad_filenames_without_processing_anything(self):
        _write_raw_gpx(self.raw_dir / "bad name no date.gpx", _straight_line())
        rc = _run(self._argv())
        self.assertNotEqual(rc, 0)
        self.assertFalse(self.out_dir.exists() and any(self.out_dir.iterdir()))

    def test_processes_valid_file_and_moves_to_done(self):
        _write_raw_gpx(self.raw_dir / "2026-06-01 Straight Line.gpx", _straight_line())
        rc = _run(self._argv())
        self.assertEqual(rc, 0)
        out_file = self.out_dir / "2026-06-01 Straight Line.gpx"
        self.assertTrue(out_file.exists())
        self.assertFalse((self.raw_dir / "2026-06-01 Straight Line.gpx").exists())
        self.assertTrue((self.done_dir / "2026-06-01 Straight Line.gpx").exists())
        self.assertTrue(self.index_path.exists())
        data = json.loads(self.index_path.read_text(encoding="utf-8"))
        self.assertEqual(len(data["routes"]), 1)

    def test_no_move_leaves_raw_in_place_and_never_writes_gpx_from_real_ride_dir(self):
        raw_file = self.raw_dir / "2026-06-01 Straight Line.gpx"
        _write_raw_gpx(raw_file, _straight_line())
        rc = _run(self._argv(["--no-move"]))
        self.assertEqual(rc, 0)
        self.assertTrue(raw_file.exists())  # never moved
        self.assertFalse(self.done_dir.exists() and any(self.done_dir.iterdir()))

    def test_refuses_to_overwrite_existing_output(self):
        # A realistic "pre-existing" gpx/ file: previously-published,
        # valid whitelist output (so the routes.json rebuild at the end
        # of `process` still succeeds against the rest of gpx/).
        from pipeline.gpx_write import write_gpx

        out_file_name = "2026-06-01 Straight Line.gpx"
        self.out_dir.mkdir(parents=True)
        existing_points = [{"lat": 1.0, "lon": 2.0, "ele": 3.0}]
        write_gpx(self.out_dir / out_file_name, existing_points)
        existing_content = (self.out_dir / out_file_name).read_text(encoding="utf-8")

        _write_raw_gpx(self.raw_dir / out_file_name, _straight_line())

        rc = _run(self._argv(["--no-move"]))
        self.assertNotEqual(rc, 0)
        # the pre-existing file must be untouched, byte for byte
        self.assertEqual(
            (self.out_dir / out_file_name).read_text(encoding="utf-8"), existing_content
        )

    def test_entirely_within_trim_radii_is_skipped_not_published(self):
        # All points sit within a few cm of each other — well under
        # even the 300m minimum radius from either endpoint.
        home_points = [(51.0 + i * 0.0000001, 15.0, 300.0) for i in range(10)]
        _write_raw_gpx(self.raw_dir / "2026-06-01 Entirely Home.gpx", home_points)
        rc = _run(self._argv(["--no-move"]))
        self.assertEqual(rc, 0)
        self.assertFalse((self.out_dir / "2026-06-01 Entirely Home.gpx").exists())
        # raw file left in place for manual review, not silently lost.
        self.assertTrue((self.raw_dir / "2026-06-01 Entirely Home.gpx").exists())

    def test_custom_radius_overrides_are_passed_through(self):
        # With a tiny custom radius range, a short track that would
        # normally be entirely trimmed away instead survives.
        home_points = [(51.0 + i * 0.00001, 15.0, 300.0) for i in range(30)]
        _write_raw_gpx(self.raw_dir / "2026-06-01 Small Loop.gpx", home_points)
        rc = _run(self._argv(["--no-move", "--radius-m", "1", "--radius-max-m", "2"]))
        self.assertEqual(rc, 0)
        self.assertTrue((self.out_dir / "2026-06-01 Small Loop.gpx").exists())

    def test_unreal_calendar_date_filename_rejected_without_processing_anything(self):
        _write_raw_gpx(self.raw_dir / "2026-13-45 Bad Date.gpx", _straight_line())
        rc = _run(self._argv(["--no-move"]))
        self.assertNotEqual(rc, 0)
        self.assertFalse(self.out_dir.exists() and any(self.out_dir.iterdir()))

    def test_uppercase_gpx_extension_is_processed(self):
        _write_raw_gpx(self.raw_dir / "2026-06-01 Upper Ext.GPX", _straight_line())
        rc = _run(self._argv(["--no-move"]))
        self.assertEqual(rc, 0)
        self.assertTrue((self.out_dir / "2026-06-01 Upper Ext.GPX").exists())

    def test_routes_json_has_no_generated_field(self):
        _write_raw_gpx(self.raw_dir / "2026-06-01 Straight Line.gpx", _straight_line())
        rc = _run(self._argv())
        self.assertEqual(rc, 0)
        data = json.loads(self.index_path.read_text(encoding="utf-8"))
        self.assertEqual(set(data.keys()), {"routes"})

    def test_malformed_file_in_out_dir_does_not_abort_whole_index_rebuild(self):
        # A stray non-conforming file already sitting in gpx/ (e.g. from
        # manual tampering) must not block the index for everyone else.
        from pipeline.gpx_write import write_gpx

        self.out_dir.mkdir(parents=True)
        write_gpx(self.out_dir / "not-a-valid-name.gpx", [{"lat": 1.0, "lon": 2.0, "ele": 3.0}])
        _write_raw_gpx(self.raw_dir / "2026-06-01 Straight Line.gpx", _straight_line())

        rc = _run(self._argv(["--no-move"]))
        self.assertNotEqual(rc, 0)  # nonzero: index_errors reported
        data = json.loads(self.index_path.read_text(encoding="utf-8"))
        self.assertEqual(len(data["routes"]), 1)
        self.assertEqual(data["routes"][0]["file"], "2026-06-01 Straight Line.gpx")


class RebuildIndexCliTests(unittest.TestCase):
    def test_rebuild_index_scans_gpx_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            gpx_dir = Path(tmp) / "gpx"
            gpx_dir.mkdir()
            from pipeline.gpx_write import write_gpx

            write_gpx(
                gpx_dir / "2026-06-01 Demo.gpx",
                [{"lat": 50.0, "lon": 15.0, "ele": 400.0}, {"lat": 50.001, "lon": 15.001, "ele": 401.0}],
            )
            index_path = Path(tmp) / "routes.json"
            rc = _run(["rebuild-index", "--out-dir", str(gpx_dir), "--index", str(index_path)])
            self.assertEqual(rc, 0)
            data = json.loads(index_path.read_text(encoding="utf-8"))
            self.assertEqual(len(data["routes"]), 1)
            self.assertEqual(set(data.keys()), {"routes"})

    def test_rebuild_index_skips_bad_files_exits_nonzero_but_writes_the_rest(self):
        with tempfile.TemporaryDirectory() as tmp:
            gpx_dir = Path(tmp) / "gpx"
            gpx_dir.mkdir()
            from pipeline.gpx_write import write_gpx

            write_gpx(
                gpx_dir / "2026-06-01 Good.gpx",
                [{"lat": 50.0, "lon": 15.0, "ele": 400.0}, {"lat": 50.001, "lon": 15.001, "ele": 401.0}],
            )
            write_gpx(gpx_dir / "totally-bad-name.gpx", [{"lat": 1.0, "lon": 2.0, "ele": 3.0}])
            index_path = Path(tmp) / "routes.json"
            rc = _run(["rebuild-index", "--out-dir", str(gpx_dir), "--index", str(index_path)])
            self.assertNotEqual(rc, 0)
            data = json.loads(index_path.read_text(encoding="utf-8"))
            self.assertEqual(len(data["routes"]), 1)
            self.assertEqual(data["routes"][0]["file"], "2026-06-01 Good.gpx")


class ReportCliTests(unittest.TestCase):
    def test_report_is_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw_dir = Path(tmp)
            _write_raw_gpx(raw_dir / "2026-06-01 Straight Line.gpx", _straight_line())
            before = (raw_dir / "2026-06-01 Straight Line.gpx").read_text(encoding="utf-8")
            rc = _run(["report", "--raw-dir", str(raw_dir)])
            after = (raw_dir / "2026-06-01 Straight Line.gpx").read_text(encoding="utf-8")
            self.assertEqual(rc, 0)
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
