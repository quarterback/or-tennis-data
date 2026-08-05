// The score field on the reporting form is one text input, so everything a
// coach might type has to land somewhere sensible.
//
//   node --test tests/functions/
//
// This replaced six number inputs per flight. The parser is now the only thing
// standing between "7-6(5), 6-4" written off a scoresheet and a stored result,
// which makes it worth pinning.

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

const { parseScore, formatScore } = await import('../../public/js/coach-common.js');

describe('parseScore', () => {
  it('reads the ordinary two-set win', () => {
    const { sets, error } = parseScore('6-4, 6-2');
    assert.equal(error, null);
    assert.deepEqual(sets, [
      { number: 1, homeGames: 6, awayGames: 4, tiePoints: null },
      { number: 2, homeGames: 6, awayGames: 2, tiePoints: null },
    ]);
  });

  it('reads a third-set tiebreak played to ten', () => {
    const { sets } = parseScore('4-6, 6-3, 10-7');
    assert.equal(sets.length, 3);
    assert.deepEqual(sets[2], { number: 3, homeGames: 10, awayGames: 7, tiePoints: null });
  });

  it('keeps the tiebreak points from a 7-6 set', () => {
    const { sets } = parseScore('7-6(5), 6-4');
    assert.equal(sets[0].tiePoints, 5);
  });

  it('accepts spaces instead of commas', () => {
    assert.equal(formatScore(parseScore('6-0 6-0').sets), '6-0, 6-0');
  });

  it('accepts an en dash, which is what a paste and a phone keyboard produce', () => {
    assert.equal(formatScore(parseScore('6–4, 6–2').sets), '6-4, 6-2');
  });

  it('treats an empty field as nothing entered, not an error', () => {
    assert.deepEqual(parseScore('  '), { sets: [], error: null });
  });

  it('rejects a set with no winner', () => {
    assert.match(parseScore('6-6').error, /no winner/);
  });

  it('rejects something that is not a set score', () => {
    assert.ok(parseScore('9').error);
    assert.ok(parseScore('6-4, later').error);
  });

  it('rejects more sets than a match can have', () => {
    assert.ok(parseScore('6-4, 6-4, 6-4, 6-4, 6-4, 6-4').error);
  });

  it('round-trips through formatScore', () => {
    for (const text of ['6-4, 6-2', '4-6, 6-3, 10-7', '7-6(5), 6-4']) {
      assert.equal(formatScore(parseScore(text).sets), text);
    }
  });
});
