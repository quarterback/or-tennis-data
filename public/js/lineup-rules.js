// OSAA Team Tennis State Championships — Ladder and Line-up Format.
//
// THE RULE IS NOT SETTLED. The committee is choosing between several versions,
// so every point still under discussion is an OPTION here, and PRESETS name the
// versions on the table. lineups.html lets the committee switch between them
// and compare one lineup under all of them at once.
// tests/functions/lineup-rules.test.mjs pins every preset against the draft's
// two worked examples.
//
// Pure: no DOM, no fetch.
//
// Format: 8 flights, 4 singles + 4 doubles (Dual Match Format 1).
//
// What every version shares (the draft, numbered as in the draft):
//   2) The #1 player on the ladder plays No. 1 singles or No. 1 doubles.
//   6) No. 3 singles ranks higher on the ladder than No. 4 singles.
//   8) An absent player is removed and everyone below moves up one; the rules
//      then apply to the shifted ladder.
//   Final Ladder Submission 1) only players on the ladder are eligible.
//
// What the options vary:
//   rule3        'examples' — S1 and S2 are the two highest-ranked players not
//                  on No. 1 doubles, in order (how both worked examples read).
//                'literal'  — the text of rule 3: the highest-ranked player not
//                  on No. 1 doubles (other than ladder #1 at S1) plays No. 2
//                  singles; if #1 plays doubles, No. 1 singles is open.
//   d1Pool       6 (draft), 4, 8, or 0 = any player on the ladder.
//   doublesOrder 'd3d4' — the draft: D4's combined ladder number is equal to or
//                  higher than D3's.
//                'all'  — every doubles flight: D1 <= D2 <= D3 <= D4.
//   fiftyRule    false, or true — a player may not be laddered lower than the
//                  singles position they played in 50%+ of their season matches
//                  (survey proposal). Needs each player's season positions.
//   shortDefaults 'draft' — rule 9 as written.
//                 'eight-doubles' — with 8 players, default No. 3 and No. 4
//                  doubles instead (survey proposal); 9-11 as the draft.

export const SINGLES = ['S1', 'S2', 'S3', 'S4'];
export const DOUBLES = ['D1', 'D2', 'D3', 'D4'];
export const FLIGHTS = [...SINGLES, ...DOUBLES];
export const FLIGHT_NAME = {
  S1: 'No. 1 singles', S2: 'No. 2 singles', S3: 'No. 3 singles', S4: 'No. 4 singles',
  D1: 'No. 1 doubles', D2: 'No. 2 doubles', D3: 'No. 3 doubles', D4: 'No. 4 doubles',
};
export const FULL_LINEUP = 12;

export const DRAFT = Object.freeze({
  rule3: 'examples', d1Pool: 6, doublesOrder: 'd3d4', fiftyRule: false, shortDefaults: 'draft',
});

// The choices for each option, in the order the page lists them.
export const OPTIONS = [
  { key: 'rule3', label: 'Rule 3 (who plays No. 1 / No. 2 singles)', choices: [
    ['examples', 'As the worked examples show: the top two players not on No. 1 doubles play No. 1 and No. 2 singles'],
    ['literal', 'As the text reads: the next-highest player not on No. 1 doubles plays No. 2 singles; No. 1 singles is open if #1 plays doubles'],
  ] },
  { key: 'd1Pool', label: 'No. 1 doubles pool', choices: [
    [6, 'Top 6 on the ladder (draft)'],
    [4, 'Top 4 on the ladder'],
    [8, 'Top 8 on the ladder'],
    [0, 'Anyone on the ladder'],
  ] },
  { key: 'doublesOrder', label: 'Doubles order', choices: [
    ['d3d4', 'No. 3 doubles equal to or stronger than No. 4 only (draft)'],
    ['all', 'All four doubles in order: No. 1 ≥ No. 2 ≥ No. 3 ≥ No. 4'],
  ] },
  { key: 'fiftyRule', label: '50% rule (ladder)', choices: [
    [false, 'Off (draft)'],
    [true, 'On: no one laddered below the singles position they played 50%+ of the season'],
  ] },
  { key: 'shortDefaults', label: 'Short lineups (rule 9)', choices: [
    ['draft', 'Draft table: 8 players default No. 3 and No. 4 singles and No. 4 doubles'],
    ['eight-doubles', 'With 8 players, default No. 3 and No. 4 doubles instead'],
  ] },
];

// The versions on the table. `id` is what the page puts in its URL.
export const PRESETS = [
  { id: 'draft', name: 'Draft (current text)', opts: { ...DRAFT },
    note: 'The most recent written draft, with rule 3 read as its worked examples show.' },
  { id: 'literal', name: 'Draft, rule 3 as literally written', opts: { ...DRAFT, rule3: 'literal' },
    note: 'Rule 3 says "#2 singles" and never names who plays No. 1 singles when #1 plays doubles.' },
  { id: 'ordered', name: 'Draft + all doubles in order', opts: { ...DRAFT, doublesOrder: 'all' },
    note: 'Closes the gap reviewers flagged: nothing in the draft stops a stronger pair at No. 3 doubles than No. 2.' },
  { id: 'specialists', name: 'Doubles specialists', opts: { ...DRAFT, d1Pool: 0, doublesOrder: 'all' },
    note: 'Any ladder player may play No. 1 doubles; all four doubles flights must be in order.' },
  { id: 'fifty', name: 'Draft + 50% rule', opts: { ...DRAFT, fiftyRule: true },
    note: 'The survey proposal: the ladder must respect where each player played most of the season.' },
];

export function presetById(id) { return PRESETS.find((p) => p.id === id) || null; }
export function withDefaults(opts) { return { ...DRAFT, ...(opts || {}) }; }

// Rule 9: which flights are defaulted for a given number of available players.
export function defaultedFlights(available, opts) {
  const o = withDefaults(opts);
  if (available >= 12) return [];
  if (available === 11) return ['S4'];
  if (available === 10) return ['D4'];
  if (available === 9) return ['S4', 'D4'];
  if (available === 8) return o.shortDefaults === 'eight-doubles' ? ['D3', 'D4'] : ['S3', 'S4', 'D4'];
  return null; // below 8: no version defines a lineup
}

// Rule 8: the ladder the rules apply to on the day. Returns pid -> rank (1-based).
export function effectiveRanks(ladder, absent = []) {
  const out = new Map();
  const gone = new Set(absent);
  let r = 0;
  for (const pid of ladder) if (!gone.has(pid)) out.set(pid, ++r);
  return out;
}

// A lineup that satisfies every version: singles in ladder order, then doubles
// pairs in ladder order. The coach edits from here.
export function defaultLineup(ladder, absent = [], opts) {
  const order = [...effectiveRanks(ladder, absent).keys()];
  const off = new Set(defaultedFlights(order.length, opts) || []);
  const lineup = {};
  let i = 0;
  for (const f of SINGLES) lineup[f] = off.has(f) ? null : (order[i++] ?? null);
  for (const f of DOUBLES) {
    if (off.has(f)) { lineup[f] = null; continue; }
    lineup[f] = [order[i++] ?? null, order[i++] ?? null];
  }
  return lineup;
}

function pidsAt(lineup, f) {
  const v = lineup[f];
  if (!v) return [];
  return (Array.isArray(v) ? v : [v]).filter(Boolean);
}

// 50% rule. seasonSlots: pid -> { S1: n, ..., D4: n } (season appearances).
// Returns pid -> { k, n, total }: the singles position number (1-4) they
// played in 50%+ of their matches, and the counts behind it.
export function majoritySingles(seasonSlots = {}) {
  const out = new Map();
  for (const [pid, slots] of Object.entries(seasonSlots)) {
    const total = Object.values(slots || {}).reduce((a, b) => a + (b || 0), 0);
    if (!total) continue;
    for (const f of SINGLES) {
      if ((slots[f] || 0) * 2 >= total) { out.set(pid, { k: Number(f[1]), n: slots[f], total }); break; }
    }
  }
  return out;
}

// Check a lineup under one version of the rules.
//   lineup: { S1: pid|null, ..., D1: [pid|null, pid|null]|null, ... }
//   opts:   see the header; missing keys take the draft's value
//   ctx:    { seasonSlots, names } — season positions for the 50% rule, and
//           pid -> name to make its messages readable
// Returns { valid, available, defaulted, checks: [{ id, rule, ok, na, text }] }.
// Every check is reported, passing or not, so the page can show the whole list.
export function validateLineup(ladder, lineup, absent = [], opts, ctx = {}) {
  const o = withDefaults(opts);
  const ranks = effectiveRanks(ladder, absent);
  const available = ranks.size;
  const listed = new Set(ladder);
  const gone = new Set(absent);
  const defaulted = defaultedFlights(available, o);
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
    const names = defaulted.map((f) => FLIGHT_NAME[f]).join(', ');
    add('defaults', '9', shouldDefault.length === 0,
      shouldDefault.length
        ? `With ${available} players, ${names} must be defaulted; ` +
          `${shouldDefault.map((f) => FLIGHT_NAME[f]).join(', ')} has a player in it.`
        : `With ${available} players, ${names} is defaulted.`);
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

  // Rule 3a: D1 pool.
  const d1 = pidsAt(lineup, 'D1');
  if (o.d1Pool) {
    const d1Out = d1.filter((p) => !(rk(p) <= o.d1Pool));
    add('d1pool', '3', d1.length === 2 && d1Out.length === 0,
      d1.length < 2 ? 'No. 1 doubles is not filled.'
        : d1Out.length ? `No. 1 doubles must come from ladder #1-#${o.d1Pool}; ${d1Out.map(tag).join(' and ')} is outside it.`
        : `No. 1 doubles is ${d1.map(tag).join(' / ')}, inside the top ${o.d1Pool}.`,
      d1.length < 2);
  } else {
    add('d1pool', '3', true, 'No. 1 doubles may be any two players on the ladder.', true);
  }

  // Rule 3b: who plays S1 and S2.
  const d1Set = new Set(d1);
  const notD1 = [...ranks.keys()].filter((p) => !d1Set.has(p));
  const s1 = pidsAt(lineup, 'S1')[0], s2 = pidsAt(lineup, 'S2')[0];
  if (o.rule3 === 'literal') {
    // Ladder #1 at S1 is rule 2. Beyond that, the text pins only No. 2 singles:
    // the highest-ranked player not on D1, setting aside whoever is at S1.
    const want = notD1.filter((p) => p !== s1)[0];
    add('s1', '3', true, d1Set.has(top)
      ? 'No. 1 singles is the coach\'s choice: rule 3 as written names no one for it when #1 plays doubles.'
      : 'No. 1 singles is ladder #1 (rule 2).', true);
    if (!s2) add('s2', '3', true, 'No. 2 singles is not filled.', true);
    else add('s2', '3', s2 === want,
      s2 === want
        ? `No. 2 singles is ${tag(s2)}, the next-highest-ranked player not on No. 1 doubles.`
        : `No. 2 singles must be ${tag(want)}, the next-highest-ranked player not on No. 1 doubles; ${tag(s2)} is there.`);
  } else {
    for (const [f, got, want] of [['S1', s1, notD1[0]], ['S2', s2, notD1[1]]]) {
      const which = f === 'S1' ? 'highest' : 'next-highest';
      if (!got) { add(f.toLowerCase(), '3', true, `${FLIGHT_NAME[f]} is not filled.`, true); continue; }
      add(f.toLowerCase(), '3', got === want,
        got === want
          ? `${FLIGHT_NAME[f]} is ${tag(got)}, the ${which}-ranked player not on No. 1 doubles.`
          : `${FLIGHT_NAME[f]} must be ${tag(want)}, the ${which}-ranked player not on No. 1 doubles; ${tag(got)} is there.`);
    }
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

  // Rule 6b: doubles order on combined ladder number (lower = stronger).
  const sum = (f) => {
    const p = pidsAt(lineup, f);
    return p.length === 2 && p.every(rk) ? rk(p[0]) + rk(p[1]) : null;
  };
  const pairs = o.doublesOrder === 'all' ? [['D1', 'D2'], ['D2', 'D3'], ['D3', 'D4']] : [['D3', 'D4']];
  for (const [a, b] of pairs) {
    const ca = sum(a), cb = sum(b);
    const id = `${a}${b}`.toLowerCase();
    if (ca === null || cb === null) {
      add(id, '6', true, `${FLIGHT_NAME[a]} / ${FLIGHT_NAME[b]}: not both played.`, true);
      continue;
    }
    add(id, '6', cb >= ca,
      cb >= ca ? `${FLIGHT_NAME[a]} (${ca}) is equal to or stronger than ${FLIGHT_NAME[b]} (${cb}).`
               : `${FLIGHT_NAME[b]} (combined ${cb}) is a stronger pair than ${FLIGHT_NAME[a]} (combined ${ca}); ` +
                 `${FLIGHT_NAME[a]} must be equal or stronger.`);
  }

  // 50% rule: a check on the LADDER (as submitted, before absences).
  if (o.fiftyRule) {
    const maj = majoritySingles(ctx.seasonSlots);
    const name = (pid) => (ctx.names && ctx.names[pid]) || pid;
    const pos = new Map(ladder.map((pid, i) => [pid, i + 1]));
    const low = [...maj].filter(([pid, m]) => pos.has(pid) && pos.get(pid) > m.k);
    add('fifty', '50%', low.length === 0,
      !ctx.seasonSlots ? 'No season positions to check against.'
        : low.length
          ? `Laddered below their season position: ${low.map(([pid, m]) => `${name(pid)} (No. ${m.k} singles in ${m.n} of ${m.total} matches, laddered #${pos.get(pid)})`).join('; ')}.`
          : 'No player is laddered below the singles position they played 50%+ of the season.',
      !ctx.seasonSlots);
  }

  return { valid: checks.every((c) => c.ok), available, defaulted, checks };
}

// Combined ladder number of a doubles pair on the day, or null.
export function combined(ladder, pair, absent = []) {
  const ranks = effectiveRanks(ladder, absent);
  if (!pair || pair.length !== 2 || !pair.every((p) => ranks.has(p))) return null;
  return ranks.get(pair[0]) + ranks.get(pair[1]);
}
