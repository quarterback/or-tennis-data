// Sync match scores from Tennis Reporting into our Netlify Blob.
// Run with: node scripts/sync_tennisreporting.mjs
//
// Pulls:
//   POST https://api.tennisreporting.com/event/861/host/3810/bracket/get
//     -> 64 bracketItems with round/position/score/teams[].isWinner
//
// Maps TR (round, position) directly to our internal match number, so
// substitutions (e.g. Ofstun replacing Frias) don't break the sync —
// structural position is the key, not who's filling it.

const TR_BASE = 'https://api.tennisreporting.com';
const EVENT_ID = 861;
const HOST_ID = 3810;
const DIVISION_ID = 1379;
const OUR_API = process.env.OUR_API || 'https://oregontennis.org/api/scores/2026';
const ADMIN_TOKEN = process.env.SD1_ADMIN_TOKEN || '';

// TR (round, position) -> { internal: our match number, topIsA: TR pos1 = our slot A? }
// Derived from comparing the current bracket data with our internal layout.
// If TR ever rearranges, regenerate this table.
//
// Pigtails (R1 in TR, M1-M7 in our numbering):
//   R1 P2  -> M1 (32 v 33): TR pos1 = our A (seed 32)
//   R1 P10 -> M2 (29 v 36): pos1 = A (seed 29)
//   R1 P14 -> M3 (28 v 37): pos1 = A (seed 28)
//   R1 P18 -> M4 (31 v 34): pos1 = A (seed 31)
//   R1 P22 -> M5 (26 v 39): pos1 = A (seed 26)
//   R1 P26 -> M6 (27 v 38): pos1 = A (seed 27)
//   R1 P30 -> M7 (30 v 35): pos1 = A (seed 30)
//
// R32 (R2 in TR, M8-M23 in our numbering): TR positions 1-16 map in
// standard top-to-bottom order. We'll fill these in once a few R32
// scores land and confirm orientation.
const TR_POSITION_MAP = {
  // Pigtails (TR R1 — only the 7 non-bye R1 positions)
  '1:2':  { internal: 1,  topIsA: true },
  '1:10': { internal: 2,  topIsA: true },
  '1:14': { internal: 3,  topIsA: true },
  '1:18': { internal: 4,  topIsA: true },
  '1:22': { internal: 5,  topIsA: true },
  '1:26': { internal: 6,  topIsA: true },
  '1:30': { internal: 7,  topIsA: true },
  // R32 (TR R2)
  '2:1':  { internal: 8,  topIsA: true },
  '2:2':  { internal: 9,  topIsA: true },
  '2:3':  { internal: 10, topIsA: true },
  '2:4':  { internal: 11, topIsA: true },
  '2:5':  { internal: 12, topIsA: true },
  '2:6':  { internal: 13, topIsA: true },
  '2:7':  { internal: 14, topIsA: true },
  '2:8':  { internal: 15, topIsA: true },
  '2:9':  { internal: 16, topIsA: true },
  '2:10': { internal: 17, topIsA: true },
  '2:11': { internal: 18, topIsA: true },
  '2:12': { internal: 19, topIsA: true },
  '2:13': { internal: 20, topIsA: true },
  '2:14': { internal: 21, topIsA: true },
  '2:15': { internal: 22, topIsA: true },
  '2:16': { internal: 23, topIsA: true },
  // R16 (TR R3)
  '3:1':  { internal: 24, topIsA: true },
  '3:2':  { internal: 25, topIsA: true },
  '3:3':  { internal: 26, topIsA: true },
  '3:4':  { internal: 27, topIsA: true },
  '3:5':  { internal: 28, topIsA: true },
  '3:6':  { internal: 29, topIsA: true },
  '3:7':  { internal: 30, topIsA: true },
  '3:8':  { internal: 31, topIsA: true },
  // QF (TR R4)
  '4:1':  { internal: 32, topIsA: true },
  '4:2':  { internal: 33, topIsA: true },
  '4:3':  { internal: 34, topIsA: true },
  '4:4':  { internal: 35, topIsA: true },
  // SF (TR R5)
  '5:1':  { internal: 36, topIsA: true },
  '5:2':  { internal: 37, topIsA: true },
  // Final (TR R6)
  '6:1':  { internal: 38, topIsA: true },
  // 3rd place (TR R1 P1 with show3:true) — keyed specially below
};

async function postJSON(url, body) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body)
  });
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

async function main() {
  const bracket = await postJSON(`${TR_BASE}/event/${EVENT_ID}/host/${HOST_ID}/bracket/get`, {
    divisionId: DIVISION_ID, matchType: 'Singles', isConsolation: false
  });

  const matchUpdates = {};
  for (const item of bracket.configuration.bracketItems) {
    if (!item.score) continue;
    // 3rd place: TR marks it with show3:true (parallel R1 P1 entry)
    const key = item.show3 ? '3p' : `${item.round}:${item.position}`;
    const mapping = key === '3p'
      ? { internal: 39, topIsA: true }
      : TR_POSITION_MAP[key];
    if (!mapping) {
      console.warn(`Skipping TR R${item.round}P${item.position}: no internal mapping yet (score=${JSON.stringify(item.score)})`);
      continue;
    }
    const trWinnerPos = item.teams[0].isWinner ? 1 : (item.teams[1].isWinner ? 2 : null);
    if (!trWinnerPos) continue;

    // TR score array is "winner_games - loser_games" per set.
    // Per-set winner is assumed to equal match winner (true for straight-set
    // wins; for split sets the losing-set scores will be wrong — fix manually).
    const aIsMatchWinner =
      (mapping.topIsA  && trWinnerPos === 1) ||
      (!mapping.topIsA && trWinnerPos === 2);
    const winnerGames = item.score.map(s => s.split('-')[0].trim());
    const loserGames  = item.score.map(s => s.split('-')[1].trim());
    matchUpdates[mapping.internal] = {
      scoreA: (aIsMatchWinner ? winnerGames : loserGames).join(', '),
      scoreB: (aIsMatchWinner ? loserGames  : winnerGames).join(', '),
      winner: aIsMatchWinner ? 'A' : 'B',
      forfeit: null
    };
  }

  console.log(`Found ${Object.keys(matchUpdates).length} scored singles matches:`);
  for (const [n, m] of Object.entries(matchUpdates)) {
    console.log(`  M${n}: A=${m.scoreA} B=${m.scoreB} winner=${m.winner}`);
  }

  if (!Object.keys(matchUpdates).length) {
    console.log('No updates to push.');
    return;
  }

  // 4. PUT to our API (merge with existing state)
  const headers = { 'content-type': 'application/json' };
  if (ADMIN_TOKEN) headers['x-admin-token'] = ADMIN_TOKEN;

  const body = { tournamentId: '2026', singles: { matches: matchUpdates } };
  const r = await fetch(OUR_API, { method: 'PUT', headers, body: JSON.stringify(body) });
  const txt = await r.text();
  console.log(`PUT ${OUR_API} -> ${r.status} ${txt}`);
}

main().catch(e => { console.error(e); process.exit(1); });
