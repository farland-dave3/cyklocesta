// Privacy regression: endpoint-relative trim (open-questions #28,
// replaces the old zone-based model — there is no privacy-zones.json,
// no coordinates, no secrets anymore). Every published point must sit
// >= radius_m (the FLOOR — never the jittered radius, see
// pipeline/privacy.py) from BOTH the ride's own raw first point and its
// own raw last point; processing identical raw bytes must be fully
// deterministic (idempotent).
//
// This can only be verified against REGENERABLE SYNTHETIC data: we
// regenerate scripts/make_demo_data.py's own synthetic raw rides into a
// throwaway temp dir and run them through the real pipeline into a
// SEPARATE throwaway temp output dir (never gpx/, never routes.json —
// make_demo_data.py refuses to touch gpx/ once real routes exist there
// anyway, but this test doesn't rely on that guard at all). The two
// real committed rides in gpx/ were trimmed from raw rides whose
// anchors are gitignored and unknown here, so their trim floor can't be
// (and must never be) checked directly — see pin-first-point.spec.js
// and gpx-whitelist.spec.js for the checks that DO apply to them.
const { test, expect } = require('@playwright/test');
const path = require('path');
const { execFileSync } = require('child_process');

const REPO_ROOT = path.resolve(__dirname, '..', '..');
const GENERATOR = path.join(__dirname, 'fixtures', 'generate_endpoint_trim_report.py');

const EARTH_RADIUS_M = 6371000.0;

function haversineM(lat1, lon1, lat2, lon2) {
  const toRad = (d) => (d * Math.PI) / 180;
  const phi1 = toRad(lat1);
  const phi2 = toRad(lat2);
  const dphi = toRad(lat2 - lat1);
  const dlambda = toRad(lon2 - lon1);
  const a = Math.sin(dphi / 2) ** 2 + Math.cos(phi1) * Math.cos(phi2) * Math.sin(dlambda / 2) ** 2;
  const c = 2 * Math.asin(Math.min(1.0, Math.sqrt(a)));
  return EARTH_RADIUS_M * c;
}

function generateReport() {
  const out = execFileSync('python3', [GENERATOR], { cwd: REPO_ROOT, encoding: 'utf-8' });
  return JSON.parse(out.trim());
}

test.describe('endpoint-relative trim (radius_m floor + determinism regression)', () => {
  const report = generateReport();

  test('sanity: the synthetic demo generator actually produced rides to check', () => {
    expect(report.radius_m).toBe(300);
    expect(report.rides.length).toBeGreaterThan(0);
  });

  test('processing identical raw bytes twice is fully deterministic (byte-identical output)', () => {
    expect(report.determinism_ok).toBe(true);
  });

  for (const ride of report.rides) {
    test(`${ride.file}: every published point is >= radius_m floor from BOTH the raw start and raw end`, () => {
      expect(ride.published_points.length).toBeGreaterThan(0);

      const violations = [];
      for (const p of ride.published_points) {
        const dStart = haversineM(p.lat, p.lon, ride.raw_first.lat, ride.raw_first.lon);
        const dEnd = haversineM(p.lat, p.lon, ride.raw_last.lat, ride.raw_last.lon);
        if (dStart < report.radius_m || dEnd < report.radius_m) {
          violations.push({ point: p, distance_to_raw_start_m: dStart, distance_to_raw_end_m: dEnd });
        }
      }
      expect(violations, JSON.stringify(violations)).toEqual([]);
    });
  }
});
