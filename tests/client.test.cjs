const assert = require('node:assert/strict');
const { test } = require('node:test');
const { pathToFileURL } = require('node:url');
const path = require('node:path');

test('progress advances only while playing and corrects to observations', async () => {
  const source = pathToFileURL(path.resolve(__dirname, '../apps/client/src/progress.ts')).href;
  const { calculateProgress } = await import(source);
  const observed = '2026-01-01T00:00:00.000Z';
  const now = Date.parse(observed) + 10_000;
  assert.equal(calculateProgress(20, 100, observed, false, now), 20);
  assert.equal(calculateProgress(20, 100, observed, true, now), 30);
  assert.equal(calculateProgress(99, 100, observed, true, now), 100);
});
