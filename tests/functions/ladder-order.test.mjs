// Reordering a ladder: every move inserts, and a typed order reads names.
//
//   node --test tests/functions/*.test.mjs

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

const { moveTo, parseOrder } = await import('../../public/js/ladder-order.js');

const order = ['a', 'b', 'c', 'd', 'e'];

describe('moveTo inserts, never swaps', () => {
  it('moving No. 1 down to No. 3 slides No. 2 and No. 3 up', () => {
    assert.deepEqual(moveTo(order, 'a', 2), ['b', 'c', 'a', 'd', 'e']);
  });
  it('moving No. 5 up to No. 2 slides everyone between down', () => {
    assert.deepEqual(moveTo(order, 'e', 1), ['a', 'e', 'b', 'c', 'd']);
  });
  it('clamps past either end and leaves the input alone', () => {
    assert.deepEqual(moveTo(order, 'c', 99), ['a', 'b', 'd', 'e', 'c']);
    assert.deepEqual(moveTo(order, 'c', -4), ['c', 'a', 'b', 'd', 'e']);
    assert.deepEqual(order, ['a', 'b', 'c', 'd', 'e']);
  });
});

describe('parseOrder reads a typed ladder', () => {
  const players = [
    { pid: '1', name: 'Edward Kong' }, { pid: '2', name: 'Matthew Stezar' },
    { pid: '3', name: 'Owen Scesa' }, { pid: '4', name: 'Owen Ramku' },
    { pid: '5', name: 'José Álvarez' },
  ];
  it('takes full names, last names, numbering and accents', () => {
    const r = parseOrder('1. Stezar\n#2 kong\n3) jose alvarez\nScesa - strong serve', players);
    assert.deepEqual(r.order, ['2', '1', '5', '3', '4']);
    assert.deepEqual(r.leftOver, ['4']);
    assert.deepEqual([r.unmatched, r.ambiguous, r.repeated], [[], [], []]);
  });
  it('flags a line that could be two players, and one that names nobody', () => {
    const r = parseOrder('Owen\nSmith', players);
    assert.deepEqual(r.ambiguous, [{ line: 'Owen', could: ['Owen Scesa', 'Owen Ramku'] }]);
    assert.deepEqual(r.unmatched, ['Smith']);
  });
  it('a shared first name resolves once the other player is placed', () => {
    const r = parseOrder('Owen Ramku\nOwen', players);
    assert.deepEqual(r.order.slice(0, 2), ['4', '3']);
  });
  it('a player named twice keeps their first spot', () => {
    const r = parseOrder('Kong\nStezar\nEdward Kong', players);
    assert.deepEqual(r.repeated, ['Edward Kong']);
    assert.deepEqual(r.order.slice(0, 2), ['1', '2']);
  });
});
