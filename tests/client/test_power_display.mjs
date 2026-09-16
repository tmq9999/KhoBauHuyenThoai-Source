import assert from 'node:assert/strict';
import {existsSync} from 'node:fs';
import {createRequire} from 'node:module';
import {test} from 'node:test';
import {fileURLToPath} from 'node:url';

const require = createRequire(import.meta.url);
const patch = new URL('../../client-recovered/patches/power-display.js', import.meta.url);

test('power display formats fractional sums without changing numeric input', () => {
  assert.ok(existsSync(patch), 'M0.2 power display module is missing');
  const {formatPower, formatRankValue} = require(fileURLToPath(patch));
  assert.equal(formatPower(3873.0999999999999), '3873');
  assert.equal(formatPower(980.2 + 980.2 + 978.2), '2938');
  assert.equal(formatPower(0), '0');
  assert.equal(formatPower(12345678.9), '12345678');
  for (const invalid of [NaN, Infinity, -Infinity, -1, '123', null, undefined]) {
    assert.throws(() => formatPower(invalid), /invalid power/);
  }
  assert.equal(formatRankValue(3873.0999999999999, 'totalPower'), '3873');
  assert.equal(formatRankValue(3873.0999999999999, 'playerTop5power'), '3873');
  assert.equal(formatRankValue(3, 'level'), 3);
  assert.equal(formatRankValue('?', 'totalPower'), '?');
});
