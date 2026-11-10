// The OSAA Ladder and Line-up Format, pinned against the draft's own examples.
//
//   node --test tests/functions/
//
// If the committee changes a rule, change public/js/lineup-rules.js and the
// examples here together. Both worked examples in the draft must stay valid.

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

const R = await import('../../public/js/lineup-rules.js');

// Ladder ids are just the ladder number as a string, so "5" is ladder #5.
const ladder = (n) => Array.from({ length: n }, (_, i) => String(i + 1));
const L15 = ladder(15);
const failed = (res) => res.checks.filter((c) => !c.ok).map((c) => c.id);

const example1 = {
  S1: '1', S2: '2', S3: '3', S4: '4',
  D1: ['5', '6'], D2: ['7', '8'], D3: ['9', '11'], D4: ['10', '12'],
};
const example2 = {
  S1: '3', S2: '4', S3: '5', S4: '6',
  D1: ['1', '2'], D2: ['7', '9'], D3: ['8', '12'], D4: ['11', '10'],
};

describe('the draft examples', () => {
  it('Example #1 is valid', () => {
    const res = R.validateLineup(L15, example1);
    assert.equal(res.valid, true, JSON.stringify(failed(res)));
  });
  it('Example #2 is valid', () => {
    const res = R.validateLineup(L15, example2);
    assert.equal(res.valid, true, JSON.stringify(failed(res)));
  });
  it('the default lineup is valid at every size from 8 to 12', () => {
    for (let n = 8; n <= 15; n++) {
      const res = R.validateLineup(ladder(n), R.defaultLineup(ladder(n)));
      assert.equal(res.valid, true, `${n} players: ${failed(res)}`);
    }
  });
});

describe('each rule', () => {
  it('2: ladder #1 must play S1 or D1', () => {
    const l = { ...example1, S1: '2', S2: '3', S3: '1' };
    assert.ok(failed(R.validateLineup(L15, l)).includes('top'));
  });
  it('3: D1 comes from the top six', () => {
    const l = { ...example1, D1: ['5', '7'], D2: ['6', '8'] };
    assert.ok(failed(R.validateLineup(L15, l)).includes('d1pool'));
  });
  it('3: S1 and S2 are the top two not on D1, in order', () => {
    const swapped = { ...example2, S1: '4', S2: '3' };
    const f = failed(R.validateLineup(L15, swapped));
    assert.ok(f.includes('s1') && f.includes('s2'));
    // #1 on D1 and #3 skipped for S1 is a violation even if S2 is right.
    const skip = { ...example2, S1: '5', S3: '3' };
    assert.ok(failed(R.validateLineup(L15, skip)).includes('s1'));
  });
  it('6: S3 must rank above S4', () => {
    const l = { ...example1, S3: '4', S4: '3' };
    assert.deepEqual(failed(R.validateLineup(L15, l)), ['s3s4']);
  });
  it('6: D4 combined number must be >= D3, equal allowed', () => {
    const flipped = { ...example1, D3: ['10', '12'], D4: ['9', '11'] };
    assert.deepEqual(failed(R.validateLineup(L15, flipped)), ['d3d4']);
    const equal = { ...example1, D3: ['9', '12'], D4: ['10', '11'] };
    assert.equal(R.validateLineup(L15, equal).valid, true);
  });
  it('ladder 1: a player not on the ladder is ineligible, and nobody plays twice', () => {
    assert.ok(failed(R.validateLineup(L15, { ...example1, D4: ['10', 'x'] })).includes('eligible'));
    assert.ok(failed(R.validateLineup(L15, { ...example1, D4: ['10', '9'] })).includes('eligible'));
  });
});

describe('8: absences shift the ladder up', () => {
  it('with #1 absent, ladder #2 becomes #1 and must play S1 or D1', () => {
    const absent = ['1'];
    const ok = R.defaultLineup(L15, absent);
    assert.equal(ok.S1, '2');
    assert.equal(R.validateLineup(L15, ok, absent).valid, true);
    const res = R.validateLineup(L15, example1, absent);
    assert.ok(failed(res).includes('eligible'));
  });
  it('combined numbers are taken on the shifted ladder', () => {
    // #3 absent: original 9/11 become 8/10 (18), original 10/12 become 9/11 (20).
    const l = { S1: '1', S2: '2', S3: '4', S4: '5', D1: ['6', '7'], D2: ['8', '9'],
                D3: ['10', '12'], D4: ['11', '13'] };
    assert.equal(R.combined(L15, l.D3, ['3']), 20);
    assert.equal(R.validateLineup(L15, l, ['3']).valid, true);
  });
});

describe('9: short lineups', () => {
  it('maps players available to defaulted flights', () => {
    assert.deepEqual(R.defaultedFlights(12), []);
    assert.deepEqual(R.defaultedFlights(11), ['S4']);
    assert.deepEqual(R.defaultedFlights(10), ['D4']);
    assert.deepEqual(R.defaultedFlights(9), ['S4', 'D4']);
    assert.deepEqual(R.defaultedFlights(8), ['S3', 'S4', 'D4']);
    assert.equal(R.defaultedFlights(7), null);
  });
  it('11 players: filling S4 instead of defaulting it is a violation', () => {
    const l = { S1: '1', S2: '2', S3: '3', S4: '4', D1: ['5', '6'], D2: ['7', '8'],
                D3: ['9', '10'], D4: ['11', null] };
    assert.ok(failed(R.validateLineup(ladder(11), l)).includes('defaults'));
  });
  it('fewer than 8 available cannot field a lineup', () => {
    assert.equal(R.validateLineup(ladder(7), R.defaultLineup(ladder(7))).valid, false);
  });
});
