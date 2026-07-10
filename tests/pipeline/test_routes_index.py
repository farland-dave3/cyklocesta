import json
import tempfile
import unittest
from pathlib import Path

from pipeline.gpx_write import write_gpx
from pipeline.routes_index import build_index, write_index


def _loop_points(n=20, lat0=50.0, lon0=15.0, ele0=400.0):
    import math

    pts = []
    for i in range(n):
        theta = 2 * math.pi * i / (n - 1)
        pts.append(
            {
                "lat": lat0 + 0.01 * math.sin(theta),
                "lon": lon0 + 0.01 * math.cos(theta),
                "ele": ele0 + 20 * math.sin(theta * 2),
            }
        )
    return pts


class BuildIndexTests(unittest.TestCase):
    def test_empty_dir_gives_empty_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            index, errors = build_index(tmp)
        self.assertEqual(index["routes"], [])
        self.assertEqual(errors, [])
        self.assertEqual(set(index.keys()), {"routes"})  # no "generated" churn field

    def test_shape_matches_frozen_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            gpx_dir = Path(tmp)
            write_gpx(gpx_dir / "2026-06-01 Demo Loop.gpx", _loop_points())
            index, errors = build_index(gpx_dir)

        self.assertEqual(errors, [])
        self.assertEqual(len(index["routes"]), 1)
        r = index["routes"][0]
        for key in ("slug", "file", "name", "date", "distance_km", "elevation_m", "pin", "bbox"):
            self.assertIn(key, r)
        self.assertEqual(r["slug"], "2026-06-01-demo-loop")
        self.assertEqual(r["file"], "2026-06-01 Demo Loop.gpx")
        self.assertEqual(r["name"], "Demo Loop")
        self.assertEqual(r["date"], "2026-06-01")
        self.assertEqual(len(r["pin"]), 2)
        self.assertEqual(len(r["bbox"]), 2)

    def test_sorted_by_date_desc_then_name_asc(self):
        with tempfile.TemporaryDirectory() as tmp:
            gpx_dir = Path(tmp)
            write_gpx(gpx_dir / "2026-06-01 B Ride.gpx", _loop_points())
            write_gpx(gpx_dir / "2026-06-01 A Ride.gpx", _loop_points())
            write_gpx(gpx_dir / "2026-06-15 Newest.gpx", _loop_points())
            index, errors = build_index(gpx_dir)

        self.assertEqual(errors, [])
        names = [r["name"] for r in index["routes"]]
        self.assertEqual(names, ["Newest", "A Ride", "B Ride"])

    def test_malformed_filename_is_skipped_with_error_not_raised(self):
        with tempfile.TemporaryDirectory() as tmp:
            gpx_dir = Path(tmp)
            write_gpx(gpx_dir / "not-a-valid-name.gpx", _loop_points())
            write_gpx(gpx_dir / "2026-06-01 Good Ride.gpx", _loop_points())
            index, errors = build_index(gpx_dir)

        # the bad file is skipped + reported...
        self.assertEqual(len(errors), 1)
        self.assertIn("not-a-valid-name.gpx", errors[0])
        # ...but the good file still makes it into the index.
        self.assertEqual(len(index["routes"]), 1)
        self.assertEqual(index["routes"][0]["file"], "2026-06-01 Good Ride.gpx")

    def test_unreal_calendar_date_in_filename_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            gpx_dir = Path(tmp)
            write_gpx(gpx_dir / "2026-13-45 Bad Date.gpx", _loop_points())
            index, errors = build_index(gpx_dir)

        self.assertEqual(index["routes"], [])
        self.assertEqual(len(errors), 1)

    def test_slug_collision_keeps_first_by_filename_order_skips_rest(self):
        with tempfile.TemporaryDirectory() as tmp:
            gpx_dir = Path(tmp)
            # Different filenames, same slug once diacritics are folded.
            # "2026-06-01 Prehrady.gpx" sorts before "...Přehrady.gpx".
            write_gpx(gpx_dir / "2026-06-01 Prehrady.gpx", _loop_points())
            write_gpx(gpx_dir / "2026-06-01 Přehrady.gpx", _loop_points())
            index, errors = build_index(gpx_dir)

        self.assertEqual(len(index["routes"]), 1)
        self.assertEqual(index["routes"][0]["file"], "2026-06-01 Prehrady.gpx")
        self.assertEqual(len(errors), 1)
        self.assertIn("collision", errors[0].lower())
        self.assertIn("Přehrady.gpx", errors[0])

    def test_case_insensitive_gpx_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            gpx_dir = Path(tmp)
            write_gpx(gpx_dir / "2026-06-01 Upper.GPX", _loop_points())
            index, errors = build_index(gpx_dir)

        self.assertEqual(errors, [])
        self.assertEqual(len(index["routes"]), 1)


class WriteIndexTests(unittest.TestCase):
    def test_writes_valid_json_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            gpx_dir = Path(tmp) / "gpx"
            gpx_dir.mkdir()
            write_gpx(gpx_dir / "2026-06-01 Demo Loop.gpx", _loop_points())
            index_path = Path(tmp) / "routes.json"
            index, errors = write_index(gpx_dir, index_path)

            data = json.loads(index_path.read_text(encoding="utf-8"))
        self.assertEqual(errors, [])
        self.assertEqual(len(data["routes"]), 1)
        self.assertEqual(set(data.keys()), {"routes"})


if __name__ == "__main__":
    unittest.main()
