// Pull live scores from Tennis Reporting and merge into our scores blob.
// GET /api/sync-tr -> { ok: true, singlesUpdates: N, doublesUpdates: N, skipped: [...] }
//
// Hit by the live bracket page on each poll. Idempotent: if no scores
// changed since last call, the blob is unchanged.

import { getStore } from '@netlify/blobs';

const TR_BASE = 'https://api.tennisreporting.com';
const EVENT_ID = 861;
const HOST_ID = 3810;
const DIVISION_ID = 1379;
const TOURNAMENT_ID = '2026';
const STORE_NAME = 'sd1-tournament-results';

// TR (round:position) -> our internal match number; topIsA: TR pos1 = our slot A.
// Both pigtails and R2+ are 1-to-1 with our internal layout, so topIsA is always
// true for this bracket.
const POSITION_MAP = {
  // Pigtails (TR R1, only the 7 non-bye positions)
  '1:2': 1, '1:10': 2, '1:14': 3, '1:18': 4, '1:22': 5, '1:26': 6, '1:30': 7,
  // R32 (TR R2)
  '2:1': 8,  '2:2': 9,  '2:3': 10, '2:4': 11, '2:5': 12, '2:6': 13, '2:7': 14, '2:8': 15,
  '2:9': 16, '2:10': 17,'2:11': 18,'2:12': 19,'2:13': 20,'2:14': 21,'2:15': 22,'2:16': 23,
  // R16 (TR R3)
  '3:1': 24, '3:2': 25, '3:3': 26, '3:4': 27, '3:5': 28, '3:6': 29, '3:7': 30, '3:8': 31,
  // QF (TR R4)
  '4:1': 32, '4:2': 33, '4:3': 34, '4:4': 35,
  // SF (TR R5)
  '5:1': 36, '5:2': 37,
  // Final (TR R6)
  '6:1': 38,
  // 3P: TR R1 P1 with show3:true (handled as special case)
};

async function fetchTRBracket(matchType) {
  const r = await fetch(`${TR_BASE}/event/${EVENT_ID}/host/${HOST_ID}/bracket/get`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ divisionId: DIVISION_ID, matchType, isConsolation: false })
  });
  if (!r.ok) throw new Error(`TR ${matchType} bracket: ${r.status}`);
  return r.json();
}

function deriveUpdates(bracket) {
  const updates = {};
  const skipped = [];
  for (const item of bracket.configuration.bracketItems) {
    if (!item.score) continue;
    const key = item.show3 ? '3p' : `${item.round}:${item.position}`;
    const internal = key === '3p' ? 39 : POSITION_MAP[key];
    if (!internal) {
      skipped.push(`R${item.round}P${item.position}`);
      continue;
    }
    const trWinnerPos = item.teams[0].isWinner ? 1 : (item.teams[1].isWinner ? 2 : null);
    if (!trWinnerPos) continue;
    // Assume topIsA = true (true for every position in this bracket layout).
    const aWins = trWinnerPos === 1;
    const winnerGames = item.score.map(s => s.split('-')[0].trim());
    const loserGames  = item.score.map(s => s.split('-')[1].trim());
    updates[internal] = {
      scoreA: (aWins ? winnerGames : loserGames).join(', '),
      scoreB: (aWins ? loserGames  : winnerGames).join(', '),
      winner: aWins ? 'A' : 'B',
      forfeit: null
    };
  }
  return { updates, skipped };
}

function shallowMatchesEqual(a, b) {
  if (!a || !b) return false;
  return a.scoreA === b.scoreA && a.scoreB === b.scoreB &&
         a.winner === b.winner && a.forfeit === b.forfeit;
}

export default async function handler(req) {
  try {
    const [singlesBr, doublesBr] = await Promise.all([
      fetchTRBracket('Singles'),
      fetchTRBracket('Doubles')
    ]);
    const s = deriveUpdates(singlesBr);
    const d = deriveUpdates(doublesBr);

    const store = getStore(STORE_NAME);
    const existing = (await store.get(TOURNAMENT_ID, { type: 'json' })) || {};
    existing.tournamentId = TOURNAMENT_ID;
    existing.singles = existing.singles || {};
    existing.singles.matches = existing.singles.matches || {};
    existing.doubles = existing.doubles || {};
    existing.doubles.matches = existing.doubles.matches || {};

    let changed = 0;
    for (const [num, m] of Object.entries(s.updates)) {
      if (!shallowMatchesEqual(existing.singles.matches[num], m)) {
        existing.singles.matches[num] = m;
        changed++;
      }
    }
    for (const [num, m] of Object.entries(d.updates)) {
      if (!shallowMatchesEqual(existing.doubles.matches[num], m)) {
        existing.doubles.matches[num] = m;
        changed++;
      }
    }

    if (changed > 0) {
      existing.updatedAt = new Date().toISOString();
      await store.setJSON(TOURNAMENT_ID, existing);
    }

    return new Response(JSON.stringify({
      ok: true,
      changed,
      singlesUpdates: Object.keys(s.updates).length,
      doublesUpdates: Object.keys(d.updates).length,
      skipped: [...s.skipped.map(x => 'S:' + x), ...d.skipped.map(x => 'D:' + x)],
      updatedAt: existing.updatedAt || null
    }), { status: 200, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' } });
  } catch (e) {
    return new Response(JSON.stringify({ ok: false, error: e.message }), {
      status: 500, headers: { 'content-type': 'application/json' }
    });
  }
}

export const config = { path: '/api/sync-tr' };
