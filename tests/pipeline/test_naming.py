import tempfile
import unittest
from pathlib import Path

from pipeline.naming import find_gpx_files, is_valid_filename, parse_filename


class NamingTests(unittest.TestCase):
    def test_valid_filename(self):
        self.assertTrue(is_valid_filename("2026-06-01 Demo Loop.gpx"))
        self.assertEqual(
            parse_filename("2026-06-01 Demo Loop.gpx"), ("2026-06-01", "Demo Loop")
        )

    def test_valid_filename_with_diacritics(self):
        self.assertTrue(is_valid_filename("2026-07-06 Okolo Přehrady.gpx"))

    def test_missing_date_is_invalid(self):
        self.assertFalse(is_valid_filename("Demo Loop.gpx"))

    def test_wrong_date_format_is_invalid(self):
        self.assertFalse(is_valid_filename("26-06-01 Demo Loop.gpx"))

    def test_missing_name_is_invalid(self):
        self.assertFalse(is_valid_filename("2026-06-01.gpx"))

    def test_not_gpx_is_invalid(self):
        self.assertFalse(is_valid_filename("2026-06-01 Demo Loop.txt"))

    def test_parse_returns_none_for_invalid(self):
        self.assertIsNone(parse_filename("bad name.gpx"))

    def test_unreal_month_is_invalid(self):
        self.assertFalse(is_valid_filename("2026-13-01 Bad Month.gpx"))
        self.assertIsNone(parse_filename("2026-13-01 Bad Month.gpx"))

    def test_unreal_day_is_invalid(self):
        self.assertFalse(is_valid_filename("2026-02-45 Bad Day.gpx"))

    def test_february_30_is_invalid(self):
        self.assertFalse(is_valid_filename("2026-02-30 Bad Day.gpx"))

    def test_february_29_valid_only_in_leap_year(self):
        self.assertTrue(is_valid_filename("2024-02-29 Leap Day.gpx"))  # 2024 is a leap year
        self.assertFalse(is_valid_filename("2026-02-29 Not Leap.gpx"))  # 2026 is not

    def test_day_zero_is_invalid(self):
        self.assertFalse(is_valid_filename("2026-06-00 Zero Day.gpx"))


class FindGpxFilesTests(unittest.TestCase):
    def test_missing_directory_returns_empty(self):
        self.assertEqual(find_gpx_files("/nonexistent/dir/for/sure"), [])

    def test_finds_lowercase_and_uppercase_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "2026-06-01 Lower.gpx").write_text("x", encoding="utf-8")
            (d / "2026-06-02 Upper.GPX").write_text("x", encoding="utf-8")
            (d / "2026-06-03 Mixed.GpX").write_text("x", encoding="utf-8")
            (d / "notes.txt").write_text("x", encoding="utf-8")

            found = [p.name for p in find_gpx_files(d)]
        self.assertEqual(
            found,
            ["2026-06-01 Lower.gpx", "2026-06-02 Upper.GPX", "2026-06-03 Mixed.GpX"],
        )

    def test_ignores_subdirectories(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "sub").mkdir()
            (d / "sub" / "2026-06-01 Nested.gpx").write_text("x", encoding="utf-8")
            found = find_gpx_files(d)
        self.assertEqual(found, [])

    def test_sorted_by_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "2026-06-02 B.gpx").write_text("x", encoding="utf-8")
            (d / "2026-06-01 A.gpx").write_text("x", encoding="utf-8")
            found = [p.name for p in find_gpx_files(d)]
        self.assertEqual(found, ["2026-06-01 A.gpx", "2026-06-02 B.gpx"])


if __name__ == "__main__":
    unittest.main()
