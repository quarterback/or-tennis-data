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

describe('the options the committee is choosing between', () => {
  it('both worked examples are valid under every preset', () => {
    // The 50% rule needs season data; with none, it has nothing to object to.
    for (const p of R.PRESETS) {
      for (const [name, ex] of [['Example #1', example1], ['Example #2', example2]]) {
        const res = R.validateLineup(L15, ex, [], p.opts, {});
        assert.equal(res.valid, true, `${p.id} / ${name}: ${failed(res)}`);
      }
    }
  });
  it('the ladder-built lineup is valid under every preset', () => {
    for (const p of R.PRESETS) for (let n = 8; n <= 13; n++) {
      const res = R.validateLineup(ladder(n), R.defaultLineup(ladder(n), [], p.opts), [], p.opts);
      assert.equal(res.valid, true, `${p.id} at ${n}: ${failed(res)}`);
    }
  });
  it('rule 3 as written leaves No. 1 singles open when #1 plays doubles', () => {
    // #1/#2 on D1, #5 at S1, #3 at S2: the text allows it, the examples do not.
    const l = { ...example2, S1: '5', S3: '4', S4: '6', S2: '3' };
    assert.equal(R.validateLineup(L15, l, [], { rule3: 'literal' }).valid, true);
    assert.ok(failed(R.validateLineup(L15, l)).includes('s1'));
  });
  it('the D1 pool size moves with the option, and 0 lifts it', () => {
    const l = { ...example1, D1: ['5', '7'], D2: ['6', '8'] };
    assert.ok(failed(R.validateLineup(L15, l, [], { d1Pool: 6 })).includes('d1pool'));
    assert.equal(R.validateLineup(L15, l, [], { d1Pool: 8 }).valid, true);
    assert.equal(R.validateLineup(L15, l, [], { d1Pool: 0 }).valid, true);
  });
  it('"all doubles in order" catches a stronger pair below a weaker one', () => {
    // D2 = 9+11 (20) and D3 = 7+8 (15): legal under the draft, not when ordered.
    const l = { ...example1, D2: ['9', '11'], D3: ['7', '8'] };
    assert.equal(R.validateLineup(L15, l).valid, true);
    assert.deepEqual(failed(R.validateLineup(L15, l, [], { doublesOrder: 'all' })), ['d2d3']);
  });
  it('the 50% rule reads the ladder against season positions', () => {
    const seasonSlots = { 3: { S1: 6, S2: 2 }, 1: { S2: 5, D1: 3 } };
    const res = R.validateLineup(L15, example1, [], { fiftyRule: true }, { seasonSlots });
    assert.deepEqual(failed(res), ['fifty']); // #3 was No. 1 singles all season
    const ok = R.validateLineup(['3', ...L15.filter((x) => x !== '3')],
      R.defaultLineup(['3', ...L15.filter((x) => x !== '3')]), [], { fiftyRule: true }, { seasonSlots });
    assert.equal(ok.valid, true, JSON.stringify(failed(ok)));
  });
  it('8 players: the alternative defaults No. 3 and No. 4 doubles', () => {
    assert.deepEqual(R.defaultedFlights(8, { shortDefaults: 'eight-doubles' }), ['D3', 'D4']);
    const l = R.defaultLineup(ladder(8), [], { shortDefaults: 'eight-doubles' });
    assert.equal(R.validateLineup(ladder(8), l, [], { shortDefaults: 'eight-doubles' }).valid, true);
    assert.ok(failed(R.validateLineup(ladder(8), l)).includes('defaults'));
  });
});

describe('every broken rule says how to fix it', () => {
  const names = Object.fromEntries(L15.map((id) => [id, `Player ${id}`]));
  const fixes = (l, opts, absent = [], ctx = {}) =>
    R.validateLineup(L15, l, absent, opts, { names, ...ctx }).checks.filter((c) => !c.ok);

  it('no failing check is without a fix, and passing checks carry none', () => {
    const broken = [
      { ...example1, S3: '4', S4: '3' },
      { ...example1, S1: '2', S2: '3', S3: '1' },
      { ...example1, D1: ['5', '9'], D3: ['7', '11'] },
      { ...example2, S1: '4', S2: '3' },
      { ...example1, D4: ['10', '9'] },
      { ...example1, D4: null },
    ];
    for (const l of broken) for (const p of R.PRESETS) {
      const res = R.validateLineup(L15, l, ['14'], p.opts, { names, seasonSlots: { 3: { S1: 9 } } });
      for (const c of res.checks) {
        if (c.ok) assert.equal(c.fix, '', `${p.id} ${c.id} passed but has a fix`);
        else assert.ok(c.fix.length > 10, `${p.id} ${c.id} failed with no fix`);
      }
    }
  });
  it('S3/S4 reversed: swap them, by name', () => {
    const [c] = fixes({ ...example1, S3: '4', S4: '3' });
    assert.equal(c.fix, 'Swap No. 3 and No. 4 singles: #3 Player 3 to No. 3 singles, #4 Player 4 to No. 4 singles.');
  });
  it('S1/S2 reversed: one swap, not two moves', () => {
    const f = fixes({ ...example2, S1: '4', S2: '3' });
    assert.ok(f.every((c) => c.fix.startsWith('Swap No. 1 and No. 2 singles: #3 Player 3 to No. 1 singles')));
  });
  it('D1 outside the pool names who can replace them', () => {
    const c = fixes({ ...example1, D1: ['5', '9'], D3: ['6', '11'] }).find((x) => x.id === 'd1pool');
    assert.match(c.fix, /^Replace #9 Player 9 on No\. 1 doubles with a player ranked #1-#6: /);
  });
  it('doubles out of order: swap the pairs', () => {
    const c = fixes({ ...example1, D3: ['10', '12'], D4: ['9', '11'] }).find((x) => x.id === 'd3d4');
    assert.match(c.fix, /^Swap the two pairs: #10 Player 10 \/ #12 Player 12 to No\. 4 doubles|^Swap the two pairs: #9 Player 9 \/ #11 Player 11 to No\. 3 doubles/);
  });
  it('an empty flight lists who is free to fill it', () => {
    const c = fixes({ ...example1, D4: null }).find((x) => x.id === 'complete');
    assert.match(c.fix, /^Fill No\. 4 doubles\. Available and not yet in the lineup: #10 Player 10, #12 Player 12/);
  });
  it('the 50% rule says when no ladder can satisfy it', () => {
    const seasonSlots = { 3: { S1: 6 }, 4: { S1: 5 } };
    const c = fixes(example1, { fiftyRule: true }, [], { seasonSlots }).find((x) => x.id === 'fifty');
    assert.match(c.fix, /no ladder satisfies the rule as written/);
  });
});

describe('one instruction per fix', () => {
  it('swapped No. 1 and No. 2 singles gives rules 2 and 3 the same fix', () => {
    const names = Object.fromEntries(L15.map((id) => [id, `Player ${id}`]));
    const res = R.validateLineup(L15, { ...example1, S1: '2', S2: '1' }, [], {}, { names });
    const fixes = new Set(res.checks.filter((c) => !c.ok).map((c) => c.fix));
    assert.equal(fixes.size, 1, [...fixes].join(' | '));
    assert.match([...fixes][0], /^Swap No\. 1 and No\. 2 singles/);
  });
});
