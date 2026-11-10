// OSAA Team Tennis State Championships — Ladder and Line-up Format (draft).
//
// The ONE place the lineup rules live. lineups.html uses it to check a lineup
// as a coach builds it; tests/functions/lineup-rules.test.mjs pins it against
// the two worked examples in the draft. Pure: no DOM, no fetch.
//
// Format: 8 flights, 4 singles + 4 doubles (Dual Match Format 1).
//
// The rules as encoded, numbered as in the draft:
//   2) The #1 player on the ladder plays No. 1 singles or No. 1 doubles.
//   3) No. 1 doubles is any two of ladder #1-#6. Singles are then filled in
//      ladder order: the highest-ranked player NOT on No. 1 doubles plays
//      No. 1 singles and the next one No. 2 singles. (The text of rule 3 says
//      "#2 singles"; both worked examples resolve it this way — Example 1 puts
//      #1 at S1 and #2 at S2, Example 2 puts #1/#2 on D1 and #3/#4 at S1/S2.)
//   4) No. 2 doubles is the coach's choice from the remaining players.
//   5) No. 3/4 singles and No. 3/4 doubles come from the remaining players.
//   6) No. 3 singles ranks higher on the ladder than No. 4 singles, and the
//      combined ladder number of No. 4 doubles is equal to or higher
//      (numerically) than No. 3 doubles — i.e. No. 3 doubles is the stronger
//      or equal pair (Example 1: D3 = 20, D4 = 22).
//   8) An absent player is removed and everyone below moves up one; the rules
//      above then apply to the shifted ladder.
//   9) Fewer than 12 available: 11 defaults No. 4 singles, 10 defaults No. 4
//      doubles, 9 defaults No. 4 singles and No. 4 doubles, 8 defaults No. 3
//      and No. 4 singles and No. 4 doubles.
// Final Ladder Submission 1): only players listed on the ladder are eligible.

export const SINGLES = ['S1', 'S2', 'S3', 'S4'];
export const DOUBLES = ['D1', 'D2', 'D3', 'D4'];
export const FLIGHTS = [...SINGLES, ...DOUBLES];
export const FLIGHT_NAME = {
  S1: 'No. 1 singles', S2: 'No. 2 singles', S3: 'No. 3 singles', S4: 'No. 4 singles',
  D1: 'No. 1 doubles', D2: 'No. 2 doubles', D3: 'No. 3 doubles', D4: 'No. 4 doubles',
};
export const D1_POOL = 6;
export const FULL_LINEUP = 12;
export const MIN_LINEUP = 8;

// Rule 9: which flights are defaulted for a given number of available players.
export function defaultedFlights(available) {
  if (available >= 12) return [];
  if (available === 11) return ['S4'];
  if (available === 10) return ['D4'];
  if (available === 9) return ['S4', 'D4'];
  if (available === 8) return ['S3', 'S4', 'D4'];
  return null; // below 8: the draft does not define a lineup
}

// Rule 8: the ladder the rules apply to on the day. Returns pid -> rank (1-based).
export function effectiveRanks(ladder, absent = []) {
  const out = new Map();
  const gone = new Set(absent);
  let r = 0;
  for (const pid of ladder) if (!gone.has(pid)) out.set(pid, ++r);
  return out;
}

// A lineup that satisfies every rule, built straight from the ladder: singles
// in ladder order, then doubles pairs in ladder order. The coach edits from here.
export function defaultLineup(ladder, absent = []) {
  const ranks = effectiveRanks(ladder, absent);
  const order = [...ranks.keys()];
  const off = new Set(defaultedFlights(order.length) || []);
  const lineup = {};
  let i = 0;
  for (const f of SINGLES) lineup[f] = off.has(f) ? null : (order[i++] ?? null);
  for (const f of DOUBLES) {
    if (off.has(f)) { lineup[f] = null; continue; }
    const a = order[i++] ?? null, b = order[i++] ?? null;
    lineup[f] = [a, b];
  }
  return lineup;
}

function pidsAt(lineup, f) {
  const v = lineup[f];
  if (!v) return [];
  return (Array.isArray(v) ? v : [v]).filter(Boolean);
}

// Check a lineup. lineup: { S1: pid|null, ..., D1: [pid|null, pid|null]|null, ... }
// Returns { valid, available, defaulted, checks: [{ id, rule, ok, na, text }] }.
// Every check is reported, passing or not, so the page can show the whole list.
export function validateLineup(ladder, lineup, absent = []) {
  const ranks = effectiveRanks(ladder, absent);
  const available = ranks.size;
  const listed = new Set(ladder);
  const gone = new Set(absent);
  const defaulted = defaultedFlights(available);
  const checks = [];
  const add = (id, rule, ok, text, na = false) => checks.push({ id, rule, ok: na ? true : ok, na, text });
  const rk = (pid) => ranks.get(pid);
  const tag = (pid) => (rk(pid) ? `#${rk(pid)}` : '?');

  if (defaulted === null) {
    add('size', '9', false,
      `Only ${available} players are available. The format defines lineups for 8 to 12 players.`);
    return { valid: false, available, defaulted: [], checks };
  }
  const off = new Set(defaulted);

  // Every flight filled (or defaulted, per rule 9).
  const missing = [];
  const shouldDefault = [];
  for (const f of FLIGHTS) {
    const need = f[0] === 'S' ? 1 : 2;
    const have = pidsAt(lineup, f).length;
    if (off.has(f)) { if (have) shouldDefault.push(f); }
    else if (have < need) missing.push(f);
  }
  add('complete', '1', missing.length === 0,
    missing.length ? `Not filled: ${missing.map((f) => FLIGHT_NAME[f]).join(', ')}.`
                   : 'Every flight is filled.');
  if (available < FULL_LINEUP) {
    add('defaults', '9', shouldDefault.length === 0,
      shouldDefault.length
        ? `With ${available} players, ${defaulted.map((f) => FLIGHT_NAME[f]).join(', ')} must be defaulted; ` +
          `${shouldDefault.map((f) => FLIGHT_NAME[f]).join(', ')} has a player in it.`
        : `With ${available} players, ${defaulted.map((f) => FLIGHT_NAME[f]).join(', ')} is defaulted.`);
  }

  // Eligibility: on the ladder, present, and in one flight only.
  const seen = new Map();
  const bad = [];
  for (const f of FLIGHTS) for (const pid of pidsAt(lineup, f)) {
    if (!listed.has(pid)) bad.push(`a player not on the ladder is in ${FLIGHT_NAME[f]}`);
    else if (gone.has(pid)) bad.push(`an absent player is in ${FLIGHT_NAME[f]}`);
    if (seen.has(pid)) bad.push(`the same player is in ${FLIGHT_NAME[seen.get(pid)]} and ${FLIGHT_NAME[f]}`);
    else seen.set(pid, f);
  }
  add('eligible', 'Ladder 1', bad.length === 0,
    bad.length ? `Ineligible: ${[...new Set(bad)].join('; ')}.` : 'Every player is on the ladder and plays once.');

  // Rule 2: ladder #1 at S1 or D1.
  const top = [...ranks.keys()][0];
  const topAt = seen.get(top);
  add('top', '2', topAt === 'S1' || topAt === 'D1',
    topAt === 'S1' || topAt === 'D1'
      ? `Ladder #1 plays ${FLIGHT_NAME[topAt]}.`
      : `Ladder #1 must play No. 1 singles or No. 1 doubles${topAt ? `, not ${FLIGHT_NAME[topAt]}` : ''}.`);

  // Rule 3a: D1 from the top six.
  const d1 = pidsAt(lineup, 'D1');
  const d1Out = d1.filter((p) => !(rk(p) <= D1_POOL));
  add('d1pool', '3', d1.length === 2 && d1Out.length === 0,
    d1.length < 2 ? 'No. 1 doubles is not filled.'
      : d1Out.length ? `No. 1 doubles must come from ladder #1-#${D1_POOL}; ${d1Out.map(tag).join(' and ')} is outside it.`
      : `No. 1 doubles is ${d1.map(tag).join(' / ')}, inside the top ${D1_POOL}.`,
    d1.length < 2);

  // Rule 3b: S1 and S2 are the two highest-ranked players not on D1, in order.
  const d1Set = new Set(d1);
  const notD1 = [...ranks.keys()].filter((p) => !d1Set.has(p));
  for (const [f, want] of [['S1', notD1[0]], ['S2', notD1[1]]]) {
    const got = pidsAt(lineup, f)[0];
    if (!got) { add(f.toLowerCase(), '3', true, `${FLIGHT_NAME[f]} is not filled.`, true); continue; }
    add(f.toLowerCase(), '3', got === want,
      got === want
        ? `${FLIGHT_NAME[f]} is ${tag(got)}, the ${f === 'S1' ? 'highest' : 'next-highest'}-ranked player not on No. 1 doubles.`
        : `${FLIGHT_NAME[f]} must be ${tag(want)}, the ${f === 'S1' ? 'highest' : 'next-highest'}-ranked player not on No. 1 doubles; ${tag(got)} is there.`);
  }

  // Rule 6a: S3 above S4.
  const s3 = pidsAt(lineup, 'S3')[0], s4 = pidsAt(lineup, 'S4')[0];
  if (s3 && s4) {
    add('s3s4', '6', rk(s3) < rk(s4),
      rk(s3) < rk(s4) ? `No. 3 singles (${tag(s3)}) ranks above No. 4 singles (${tag(s4)}).`
                      : `No. 3 singles (${tag(s3)}) must rank above No. 4 singles (${tag(s4)}).`);
  } else {
    add('s3s4', '6', true, 'No. 3 / No. 4 singles: not both played.', true);
  }

  // Rule 6b: D4's combined number >= D3's.
  const d3 = pidsAt(lineup, 'D3'), d4 = pidsAt(lineup, 'D4');
  if (d3.length === 2 && d4.length === 2 && [...d3, ...d4].every(rk)) {
    const c3 = rk(d3[0]) + rk(d3[1]), c4 = rk(d4[0]) + rk(d4[1]);
    add('d3d4', '6', c4 >= c3,
      c4 >= c3 ? `No. 3 doubles (${c3}) is equal to or stronger than No. 4 doubles (${c4}).`
               : `No. 4 doubles' combined number (${c4}) must be equal to or higher than No. 3 doubles' (${c3}).`);
  } else {
    add('d3d4', '6', true, 'No. 3 / No. 4 doubles: not both played.', true);
  }

  return { valid: checks.every((c) => c.ok), available, defaulted, checks };
}

// Combined ladder number of a doubles pair on the day, or null.
export function combined(ladder, pair, absent = []) {
  const ranks = effectiveRanks(ladder, absent);
  if (!pair || pair.length !== 2 || !pair.every((p) => ranks.has(p))) return null;
  return ranks.get(pair[0]) + ranks.get(pair[1]);
}
