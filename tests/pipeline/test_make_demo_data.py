"""Tests for scripts/make_demo_data.py's "never delete real routes"
safety logic (loaded by file path since scripts/ isn't a package)."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "make_demo_data.py"
_spec = importlib.util.spec_from_file_location("make_demo_data", SCRIPT_PATH)
make_demo_data = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(make_demo_data)


class ClearOwnPreviousOutputTests(unittest.TestCase):
    def test_empty_dir_is_fine(self):
        with tempfile.TemporaryDirectory() as tmp:
            gpx_dir = Path(tmp)
            make_demo_data.clear_own_previous_output(gpx_dir)  # must not raise
            self.assertEqual(list(gpx_dir.glob("*.gpx")), [])

    def test_missing_dir_is_fine(self):
        with tempfile.TemporaryDirectory() as tmp:
            gpx_dir = Path(tmp) / "does-not-exist-yet"
            make_demo_data.clear_own_previous_output(gpx_dir)  # must not raise

    def test_removes_only_its_own_previous_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            gpx_dir = Path(tmp)
            for name in make_demo_data.DEMO_ROUTE_FILENAMES:
                (gpx_dir / name).write_text("stale demo output", encoding="utf-8")

            make_demo_data.clear_own_previous_output(gpx_dir)

            self.assertEqual(list(gpx_dir.glob("*.gpx")), [])

    def test_refuses_and_touches_nothing_if_a_foreign_gpx_is_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            gpx_dir = Path(tmp)
            real_route = gpx_dir / "2026-01-01 A Real Ride.gpx"
            real_route.write_text("real published route — must survive", encoding="utf-8")
            for name in make_demo_data.DEMO_ROUTE_FILENAMES:
                (gpx_dir / name).write_text("stale demo output", encoding="utf-8")

            with self.assertRaises(make_demo_data.ForeignFilesError):
                make_demo_data.clear_own_previous_output(gpx_dir)

            # nothing was touched — not even the stale demo files.
            self.assertTrue(real_route.exists())
            for name in make_demo_data.DEMO_ROUTE_FILENAMES:
                self.assertTrue((gpx_dir / name).exists())

    def test_foreign_file_named_like_a_gpx_but_different_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            gpx_dir = Path(tmp)
            (gpx_dir / "2026-01-01 Someone Elses Ride.GPX").write_text("x", encoding="utf-8")
            with self.assertRaises(make_demo_data.ForeignFilesError):
                make_demo_data.clear_own_previous_output(gpx_dir)


if __name__ == "__main__":
    unittest.main()
