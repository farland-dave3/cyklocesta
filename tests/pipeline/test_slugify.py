import unittest

from pipeline.slugify import slugify


class SlugifyTests(unittest.TestCase):
    def test_diacritics_example_from_spec(self):
        self.assertEqual(
            slugify("2026-07-06 Okolo Přehrady"), "2026-07-06-okolo-prehrady"
        )

    def test_lowercases_and_collapses_spaces(self):
        self.assertEqual(slugify("2026-06-01 Demo Loop"), "2026-06-01-demo-loop")

    def test_trims_leading_trailing_dashes(self):
        self.assertEqual(slugify("  --Weird Name--  "), "weird-name")

    def test_collapses_non_alnum_runs(self):
        self.assertEqual(slugify("A!!!B???C"), "a-b-c")

    def test_nfd_input_normalizes_same_as_nfc(self):
        import unicodedata

        nfc = unicodedata.normalize("NFC", "Přehrady")
        nfd = unicodedata.normalize("NFD", "Přehrady")
        self.assertNotEqual(nfc.encode("utf-8"), nfd.encode("utf-8"))
        self.assertEqual(slugify(nfc), slugify(nfd))


if __name__ == "__main__":
    unittest.main()
