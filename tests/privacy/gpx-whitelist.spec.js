// Privacy regression: emitted GPX must be whitelist-only output.
// CLAUDE.md: "Emit GPX by whitelist, never edit-in-place" — <trk><trkseg>
// <trkpt lat lon><ele> only. No <time> (patterns-of-life leak), no
// <metadata>, no <wpt>, no <extensions> may ever survive into gpx/.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const REPO_ROOT = path.resolve(__dirname, '..', '..');
const GPX_DIR = path.join(REPO_ROOT, 'gpx');

const ALLOWED_TAGS = new Set(['gpx', 'trk', 'trkseg', 'trkpt', 'ele']);
const FORBIDDEN_TAGS = ['time', 'metadata', 'wpt', 'extensions'];

function listGpxFiles() {
  if (!fs.existsSync(GPX_DIR)) return [];
  return fs.readdirSync(GPX_DIR).filter((f) => f.endsWith('.gpx'));
}

test.describe('GPX emit-by-whitelist (privacy regression)', () => {
  const files = listGpxFiles();

  test('sanity: gpx/ has at least one committed/working route to check', () => {
    expect(files.length).toBeGreaterThan(0);
  });

  for (const file of files) {
    test(`${file}: contains no <time>, <metadata>, <wpt>, <extensions>`, () => {
      const text = fs.readFileSync(path.join(GPX_DIR, file), 'utf-8');
      for (const forbidden of FORBIDDEN_TAGS) {
        const re = new RegExp(`<${forbidden}[\\s>/]`, 'i');
        expect(text, `${file} must not contain <${forbidden}>`).not.toMatch(re);
      }
    });

    test(`${file}: only whitelisted elements present`, () => {
      const text = fs.readFileSync(path.join(GPX_DIR, file), 'utf-8');
      const tagNames = new Set();
      const re = /<\/?([a-zA-Z][a-zA-Z0-9:_-]*)/g;
      let m;
      while ((m = re.exec(text)) !== null) {
        // Strip an XML-namespace prefix if present (e.g. "gpx:trk" -> "trk").
        const name = m[1].split(':').pop();
        if (name.toLowerCase() === 'xml') continue; // the <?xml ...?> PI
        tagNames.add(name);
      }
      const unexpected = [...tagNames].filter((t) => !ALLOWED_TAGS.has(t));
      expect(unexpected, `${file} has unexpected element(s): ${unexpected.join(', ')}`).toEqual([]);
    });
  }
});
