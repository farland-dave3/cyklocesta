import json
import unittest

from pipeline.privacy_gate import (
    check_routes_json_pin_consistency,
    check_structure,
    classify_staged_paths,
    run_gate,
)

WHITELIST_GPX = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<gpx version="1.1" creator="ebike-route-map" '
    'xmlns="http://www.topografix.com/GPX/1/1">'
    "<trk><trkseg>"
    '<trkpt lat="51.000000" lon="15.000000"><ele>400.0</ele></trkpt>'
    '<trkpt lat="51.001000" lon="15.001000"><ele>401.0</ele></trkpt>'
    "</trkseg></trk></gpx>"
).encode("utf-8")

GPX_WITH_TIME = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">'
    "<trk><trkseg>"
    '<trkpt lat="51.0" lon="15.0"><ele>400.0</ele>'
    "<time>2025-01-01T00:00:00Z</time></trkpt>"
    "</trkseg></trk></gpx>"
).encode("utf-8")


def _routes_json(file, pin):
    return json.dumps({"routes": [{"file": file, "pin": pin}]}).encode("utf-8")


def _loader(files):
    def loader(path):
        return files[path]

    return loader


def _working_tree_reader(files):
    def reader(path):
        if path not in files:
            raise FileNotFoundError(path)
        return files[path]

    return reader


def _no_working_tree():
    def reader(path):
        raise FileNotFoundError(path)

    return reader


class ClassifyStagedPathsTests(unittest.TestCase):
    def test_raw_and_done_flagged(self):
        buckets = classify_staged_paths(["raw/eBike ride.gpx", "done/old.gpx", "gpx/2026-01-01 X.gpx"])
        self.assertEqual(buckets["raw_or_done"], ["raw/eBike ride.gpx", "done/old.gpx"])

    def test_gpx_outside_gpx_dir_flagged(self):
        buckets = classify_staged_paths(["2026-01-01 Oops.gpx", "some/dir/x.gpx"])
        self.assertEqual(
            buckets["gpx_outside"], ["2026-01-01 Oops.gpx", "some/dir/x.gpx"]
        )

    def test_gpx_inside_gpx_dir_ok_bucket(self):
        buckets = classify_staged_paths(["gpx/2026-01-01 X.gpx"])
        self.assertEqual(buckets["gpx_in_dir"], ["gpx/2026-01-01 X.gpx"])
        self.assertEqual(buckets["gpx_outside"], [])

    def test_routes_json_detected(self):
        buckets = classify_staged_paths(["routes.json", "index.html"])
        self.assertEqual(buckets["routes_json"], "routes.json")

    def test_privacy_zones_json_denied(self):
        # Obsolete (zone model is gone) but kept in the deny-list
        # defensively in case a stale copy exists somewhere.
        buckets = classify_staged_paths(["privacy-zones.json"])
        self.assertEqual(buckets["denied"], ["privacy-zones.json"])

    def test_config_local_js_denied(self):
        buckets = classify_staged_paths(["config.local.js"])
        self.assertEqual(buckets["denied"], ["config.local.js"])

    def test_log_file_denied(self):
        buckets = classify_staged_paths(["route-manager.log", "some/dir/debug.log"])
        self.assertEqual(
            buckets["denied"], ["route-manager.log", "some/dir/debug.log"]
        )

    def test_denied_files_excluded_from_other_buckets(self):
        buckets = classify_staged_paths(["privacy-zones.json", "config.local.js", "x.log"])
        self.assertEqual(buckets["raw_or_done"], [])
        self.assertEqual(buckets["gpx_outside"], [])
        self.assertIsNone(buckets["routes_json"])


class CheckStructureTests(unittest.TestCase):
    def test_whitelist_shaped_gpx_passes(self):
        self.assertEqual(check_structure(WHITELIST_GPX), [])

    def test_time_element_blocked(self):
        violations = check_structure(GPX_WITH_TIME)
        self.assertTrue(any("time" in v for v in violations))

    def test_invalid_xml_blocked(self):
        violations = check_structure(b"<gpx><trk>")
        self.assertTrue(violations)


class CheckRoutesJsonPinConsistencyTests(unittest.TestCase):
    def test_matching_pin_passes(self):
        payload = _routes_json("x.gpx", [51.0, 15.0])
        resolver = lambda filename: WHITELIST_GPX
        self.assertEqual(check_routes_json_pin_consistency(payload, resolver), [])

    def test_mismatched_pin_blocks(self):
        payload = _routes_json("x.gpx", [1.0, 2.0])
        resolver = lambda filename: WHITELIST_GPX
        violations = check_routes_json_pin_consistency(payload, resolver)
        self.assertTrue(violations)
        self.assertIn("pin", violations[0])

    def test_missing_referenced_gpx_blocks(self):
        payload = _routes_json("missing.gpx", [51.0, 15.0])
        resolver = lambda filename: None
        violations = check_routes_json_pin_consistency(payload, resolver)
        self.assertTrue(violations)
        self.assertIn("not found", violations[0])

    def test_invalid_xml_in_referenced_gpx_blocks(self):
        payload = _routes_json("bad.gpx", [51.0, 15.0])
        resolver = lambda filename: b"<gpx><trk>"
        violations = check_routes_json_pin_consistency(payload, resolver)
        self.assertTrue(violations)

    def test_no_trkpt_in_referenced_gpx_blocks(self):
        empty_gpx = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">'
            "<trk><trkseg></trkseg></trk></gpx>"
        ).encode("utf-8")
        payload = _routes_json("empty.gpx", [51.0, 15.0])
        resolver = lambda filename: empty_gpx
        violations = check_routes_json_pin_consistency(payload, resolver)
        self.assertTrue(violations)

    def test_missing_file_or_pin_fields_blocks(self):
        payload = json.dumps({"routes": [{"file": "x.gpx"}]}).encode("utf-8")
        violations = check_routes_json_pin_consistency(payload, lambda f: WHITELIST_GPX)
        self.assertTrue(violations)

    def test_empty_routes_list_passes(self):
        payload = json.dumps({"routes": []}).encode("utf-8")
        self.assertEqual(check_routes_json_pin_consistency(payload, lambda f: None), [])

    def test_invalid_json_blocks(self):
        violations = check_routes_json_pin_consistency(b"not json", lambda f: None)
        self.assertTrue(violations)


class RunGateTests(unittest.TestCase):
    def test_no_staged_files_no_violations(self):
        self.assertEqual(run_gate([], _loader({}), _no_working_tree()), [])

    def test_raw_staged_blocks(self):
        violations = run_gate(["raw/eBike ride.gpx"], _loader({}), _no_working_tree())
        self.assertTrue(violations)

    def test_done_staged_blocks(self):
        violations = run_gate(["done/old.gpx"], _loader({}), _no_working_tree())
        self.assertTrue(violations)

    def test_gpx_outside_gpx_dir_blocks(self):
        violations = run_gate(["2026-01-01 Oops.gpx"], _loader({}), _no_working_tree())
        self.assertTrue(violations)

    def test_clean_gpx_in_gpx_dir_passes(self):
        content = {"gpx/2026-01-01 X.gpx": WHITELIST_GPX}
        violations = run_gate(list(content.keys()), _loader(content), _no_working_tree())
        self.assertEqual(violations, [])

    def test_structurally_bad_gpx_blocks(self):
        content = {"gpx/2026-01-01 X.gpx": GPX_WITH_TIME}
        violations = run_gate(list(content.keys()), _loader(content), _no_working_tree())
        self.assertTrue(violations)

    def test_privacy_zones_json_staged_blocks_unconditionally(self):
        # Obsolete file, kept on the deny-list defensively — blocks even
        # with nothing else staged.
        violations = run_gate(["privacy-zones.json"], _loader({"privacy-zones.json": b"{}"}), _no_working_tree())
        self.assertTrue(violations)

    def test_config_local_js_staged_blocks_unconditionally(self):
        violations = run_gate(["config.local.js"], _loader({}), _no_working_tree())
        self.assertTrue(violations)

    def test_log_file_staged_blocks_unconditionally(self):
        violations = run_gate(["app.log"], _loader({}), _no_working_tree())
        self.assertTrue(violations)

    def test_denied_file_blocks_even_alongside_clean_gpx(self):
        content = {
            "gpx/2026-01-01 X.gpx": WHITELIST_GPX,
            "privacy-zones.json": b"{}",
        }
        violations = run_gate(list(content.keys()), _loader(content), _no_working_tree())
        self.assertTrue(violations)

    def test_routes_json_matching_pin_against_staged_gpx_passes(self):
        content = {
            "gpx/2026-01-01 X.gpx": WHITELIST_GPX,
            "routes.json": _routes_json("2026-01-01 X.gpx", [51.0, 15.0]),
        }
        violations = run_gate(list(content.keys()), _loader(content), _no_working_tree())
        self.assertEqual(violations, [])

    def test_routes_json_mismatched_pin_against_staged_gpx_blocks(self):
        content = {
            "gpx/2026-01-01 X.gpx": WHITELIST_GPX,
            "routes.json": _routes_json("2026-01-01 X.gpx", [1.0, 2.0]),
        }
        violations = run_gate(list(content.keys()), _loader(content), _no_working_tree())
        self.assertTrue(violations)

    def test_routes_json_matches_working_tree_gpx_when_gpx_not_staged(self):
        # routes.json staged alone, referencing an already-published gpx
        # that isn't touched by this commit — must be read from the
        # working tree, not treated as missing.
        content = {"routes.json": _routes_json("2026-01-01 X.gpx", [51.0, 15.0])}
        working_tree = {"gpx/2026-01-01 X.gpx": WHITELIST_GPX}
        violations = run_gate(
            list(content.keys()), _loader(content), _working_tree_reader(working_tree)
        )
        self.assertEqual(violations, [])

    def test_routes_json_referencing_missing_gpx_blocks(self):
        content = {"routes.json": _routes_json("2026-01-01 Missing.gpx", [51.0, 15.0])}
        violations = run_gate(list(content.keys()), _loader(content), _no_working_tree())
        self.assertTrue(violations)

    def test_staged_gpx_content_preferred_over_stale_working_tree(self):
        # Both the gpx and routes.json are staged together; the staged
        # gpx content (which matches the pin) must win over a stale,
        # mismatched working-tree copy of the "same" file.
        content = {
            "gpx/2026-01-01 X.gpx": WHITELIST_GPX,
            "routes.json": _routes_json("2026-01-01 X.gpx", [51.0, 15.0]),
        }
        stale_working_tree = {
            "gpx/2026-01-01 X.gpx": _routes_json("irrelevant", [1.0, 2.0])  # garbage/mismatched
        }
        violations = run_gate(
            list(content.keys()), _loader(content), _working_tree_reader(stale_working_tree)
        )
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
