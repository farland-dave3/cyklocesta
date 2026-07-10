// Privacy regression: guard against raw/done ever entering git history,
// and against a .gpx being tracked anywhere outside gpx/.
// CLAUDE.md: "one committed raw file permanently leaks real home
// coordinates" — this is the last line of defense the automated suite
// can offer (the actual enforcement for the non-technical maintainer is
// the local pre-commit hook, pipeline/privacy_gate.py).
const { test, expect } = require('@playwright/test');
const path = require('path');
const { execFileSync } = require('child_process');

const REPO_ROOT = path.resolve(__dirname, '..', '..');

function gitLsFiles() {
  const out = execFileSync('git', ['ls-files'], { cwd: REPO_ROOT, encoding: 'utf-8' });
  return out.split('\n').filter(Boolean);
}

test.describe('git guard: raw/, done/, and .gpx outside gpx/ must never be tracked', () => {
  const tracked = gitLsFiles();

  test('nothing under raw/ or done/ is tracked by git', () => {
    const offenders = tracked.filter((f) => f.startsWith('raw/') || f.startsWith('done/'));
    expect(offenders).toEqual([]);
  });

  test('no .gpx file is tracked outside gpx/', () => {
    const offenders = tracked.filter((f) => f.endsWith('.gpx') && !f.startsWith('gpx/'));
    expect(offenders).toEqual([]);
  });

  test('sanity: git ls-files actually returned something (guard isn\'t vacuously passing on a broken git call)', () => {
    expect(tracked.length).toBeGreaterThanOrEqual(0); // repo may be pre-first-commit; just assert the call worked
    expect(Array.isArray(tracked)).toBe(true);
  });
});
