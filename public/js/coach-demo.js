// A backend that lives in the browser, for showing the tool without one.
//
// The reporting pages need Postgres and a mail provider to do anything real.
// Neither is set up yet, and neither should be needed to SHOW somebody how
// entry works — the sign-in wall with "internal error" under it is a bad first
// impression of a tool whose whole pitch is that it is easy.
//
// So when the API is not answering, the pages fall back here: same routes, same
// shapes, backed by localStorage. Sign-in is skipped, a sample team is already
// claimed, and everything a coach would do works — entering a dual, saving it,
// editing it back. Nothing leaves the phone.
//
// It switches itself off the moment a real backend answers, so this cannot
// mask a live outage or quietly eat real results: `probeBackend()` decides
// once per page load, and a configured deployment never reaches this file.

const KEY = 'cb_demo_state';
const PROGRAM_KEY = 'cb_demo_program';

// The program the demo is standing in for. A coach trying the tool out has to
// be able to try it as THEIR program — one hard-coded school means everybody
// else is looking at somebody else's roster and cannot tell what their own
// entry would look like. Changing it re-seeds, so each program opens with its
// own season rather than the last one's duals under a new name.
const DEFAULT_PROGRAM = {
  school_id: 124895, school_name: 'Catlin Gabel',
  league: 'Special District 1', classification: '4A/3A/2A/1A',
};

export function demoProgram() {
  try {
    const raw = localStorage.getItem(PROGRAM_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* corrupt or unavailable */ }
  return DEFAULT_PROGRAM;
}

/** Point the demo at another school, and start that program's season clean. */
export function setDemoProgram(program) {
  try {
    localStorage.setItem(PROGRAM_KEY, JSON.stringify(program));
    localStorage.removeItem(KEY);
  } catch { /* private mode */ }
}

// Team-season ids are derived from the program so state keyed on them survives
// a reload: gender digit then school id, the same shape as a lineups key.
const teamId = (genderId, schoolId) => Number(`${genderId}${schoolId}`);

function teams() {
  const p = demoProgram();
  return [2, 1].map((genderId) => ({
    id: teamId(genderId, p.school_id),
    year: 2027,
    school_id: p.school_id,
    school_name: p.school_name,
    gender_id: genderId,
    is_jv: false,
    league: p.league || '',
    classification: p.classification || '',
    entry_enabled: true,
  }));
}

const NAMES = [
  ['Ada', 'Whitfield', '12'], ['Nora', 'Ellingsen', '12'], ['Priya', 'Raghunathan', '11'],
  ['Signe', 'Halvorsen', '11'], ['Marisol', 'Vega', '10'], ['Juno', 'Kastellanos', '10'],
  ['Beatrix', 'Ahlgren', '9'], ['Wren', 'Okonkwo', '9'], ['Talia', 'Bergström', '11'],
  ['Cleo', 'Mbeki', '12'],
];

// Three duals already on the books, so the tool opens with a season in it
// rather than an empty table and a "no duals reported yet" line. Somebody being
// shown this should see what it looks like in use: a confirmed win, a loss, and
// a draft half-entered. Real opponents, plausible scores.
const SAMPLE = [
  { days: 21, opponent: 124884, home: true, status: 'confirmed',
    // 5–3. Won the singles, split the doubles.
    results: [true, true, false, true, true, false, false, true] },
  { days: 14, opponent: 124656, home: false, status: 'confirmed',
    // 3–5 the other way.
    results: [false, true, false, false, true, true, false, false] },
  { days: 5, opponent: 75860, home: true, status: 'draft',
    // Half a card typed and not yet submitted, which is the state a coach
    // leaves one in when a match runs late.
    results: [true, true, false, null, null, null, null, null] },
];

const CARD = [
  ['Singles', 1], ['Singles', 2], ['Singles', 3], ['Singles', 4],
  ['Doubles', 1], ['Doubles', 2], ['Doubles', 3], ['Doubles', 4],
];

const SCORES = [
  [[6, 3], [6, 4]], [[7, 5], [6, 2]], [[6, 4], [3, 6], [10, 7]],
  [[6, 1], [6, 0]], [[6, 2], [7, 6]], [[4, 6], [6, 3], [10, 8]],
  [[6, 4], [6, 4]], [[7, 6], [6, 3]],
];

function seed() {
  const players = [];
  let pid = 950000;
  const TEAMS = teams();
  for (const team of TEAMS) {
    for (const [first, last, grade] of NAMES) {
      players.push({
        id: pid++, team_season_id: team.id, first_name: first, last_name: last,
        grade, tr_player_id: null, active: true,
      });
    }
  }

  // Dates are counted back from today so the season always looks current.
  const today = new Date();
  const iso = (daysAgo) => {
    const d = new Date(today.getTime() - daysAgo * 86400000);
    return d.toISOString().slice(0, 10);
  };

  const girls = TEAMS[0];
  // The sample opponents are fixed schools, so a demo pointed at one of them
  // would show it playing itself. Drop that fixture rather than seed nonsense.
  const samples = SAMPLE.filter((x) => Number(x.opponent) !== Number(girls.school_id));
  const ours = players.filter((p) => p.team_season_id === girls.id);
  let lineId = 700001;
  let dualId = 8001;

  const duals = samples.map((sample) => ({
    id: dualId++,
    team_season_id: girls.id,
    home_school_id: sample.home ? girls.school_id : sample.opponent,
    away_school_id: sample.home ? sample.opponent : girls.school_id,
    is_home: sample.home,
    opponent_school_id: sample.opponent,
    played_on: iso(sample.days),
    status: sample.status,
    updated_at: new Date().toISOString(),
    lines: sample.results.map((weWon, i) => {
      if (weWon === null) return null;   // flight not entered yet
      const [type, flight] = CARD[i];
      const doubles = type === 'Doubles';
      const homeWon = sample.home ? weWon : !weWon;
      // Set scores are written from the home side, so flip them when we are away.
      const sets = SCORES[i].map(([a, b], n) => ({
        number: n + 1,
        homeGames: weWon === sample.home ? a : b,
        awayGames: weWon === sample.home ? b : a,
      }));
      const pick = (n) => ours[(i * 2 + n) % ours.length];
      return {
        id: lineId++,
        match_type: type,
        flight,
        home_won: homeWon,
        finish: null,
        sets: weWon === homeWon ? sets : sets.map((x) => ({
          number: x.number, homeGames: x.awayGames, awayGames: x.homeGames })),
        homePlayers: sample.home ? [pick(0), ...(doubles ? [pick(1)] : [])] : [],
        awayPlayers: sample.home ? [] : [pick(0), ...(doubles ? [pick(1)] : [])],
      };
    }).filter(Boolean),
  }));

  return { players, duals, nextDualId: dualId, nextLineId: lineId };
}

function load() {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* corrupt or unavailable — start over */ }
  const fresh = seed();
  save(fresh);
  return fresh;
}

function save(state) {
  try { localStorage.setItem(KEY, JSON.stringify(state)); } catch { /* private mode */ }
}

/** Wipe the demo back to a clean roster and no duals. */
export function resetDemo() {
  localStorage.removeItem(KEY);
}

const COACH = { id: 1, email: 'demo@oregontennis.org', name: 'Demo', is_admin: true };

function team(id) {
  const all = teams();
  return all.find((t) => Number(t.id) === Number(id)) || all[0];
}

/**
 * Write a save payload onto a dual.
 *
 * The pages do not send a team_season_id — the real backend resolves the team
 * from year + genderId + the two school ids, so the demo has to do the same or
 * every saved dual lands under a team nobody is looking at. (It did; the hub
 * came back empty and the save looked like it had worked.)
 */
function applyPayload(d, body, state) {
  const gender = Number(body.genderId);
  const all = teams();
  const ours = all.find((t) => Number(t.gender_id) === gender
    && (Number(t.school_id) === Number(body.homeSchoolId)
      || Number(t.school_id) === Number(body.awaySchoolId))) || all[0];

  d.team_season_id = ours.id;
  d.home_school_id = Number(body.homeSchoolId);
  d.away_school_id = Number(body.awaySchoolId);
  d.is_home = Number(body.homeSchoolId) === Number(ours.school_id);
  d.opponent_school_id = d.is_home ? Number(body.awaySchoolId) : Number(body.homeSchoolId);
  d.played_on = body.playedOn || d.played_on;
  // `draft` is the wire format, not a status string.
  d.status = body.draft ? 'draft' : 'reported';
  d.updated_at = new Date().toISOString();
  d.lines = (body.lines || []).map((l) => ({
    id: state.nextLineId++,
    match_type: l.matchType,
    flight: l.flight,
    home_won: l.homeWon ?? null,
    finish: l.finish ?? null,
    sets: l.sets || [],
    homePlayers: l.homePlayers || [],
    awayPlayers: l.awayPlayers || [],
  }));
}

// School names for the summary rows, read from the site's own scoreboard index
// so the demo shows real opponents rather than the word "Opponent".
let SCHOOLS = null;
async function loadSchools() {
  if (SCHOOLS) return SCHOOLS;
  SCHOOLS = new Map();
  try {
    const idx = await fetch('data/scoreboard/2026/index.json').then((r) => r.json());
    // `id` here is the school id, and some names carry a leading space.
    for (const t of idx.teams || []) SCHOOLS.set(Number(t.id), String(t.name).trim());
  } catch { /* not built — names fall back below */ }
  return SCHOOLS;
}

function summarise(state, d) {
  // Same summary shape /api/duals returns: enough for the season table without
  // loading every card.
  const home = d.lines.filter((l) => l.home_won === true).length;
  const away = d.lines.filter((l) => l.home_won === false).length;
  const us = team(d.team_season_id).school_name;
  const them = (SCHOOLS && SCHOOLS.get(d.opponent_school_id)) || 'Opponent';
  return {
    id: d.id,
    played_on: d.played_on,
    status: d.status,
    is_home: d.is_home !== false,
    home_name: d.is_home === false ? them : us,
    away_name: d.is_home === false ? us : them,
    home_flights: home,
    away_flights: away,
    flight_count: d.lines.length,
  };
}

/**
 * Serve one API call from localStorage.
 *
 * Mirrors the routes in netlify/functions/, including their error shapes, so
 * the pages need no demo-specific branches beyond choosing this transport.
 */
export async function demoApi(path, options = {}) {
  const state = load();
  const method = (options.method || 'GET').toUpperCase();
  const body = options.body ? JSON.parse(options.body) : {};
  const url = new URL(path, location.origin);
  const parts = url.pathname.replace(/^\/api\//, '').split('/').filter(Boolean);
  const [group, ...rest] = parts;

  if (rest[0] === '__ping') return { ok: true, demo: true };

  if (group === 'auth') {
    if (rest[0] === 'me') return { coach: COACH, teams: teams() };
    if (rest[0] === 'logout') { resetDemo(); return null; }
    return { ok: true };
  }

  if (group === 'roster') {
    if (rest[0] === 'player') {
      const player = state.players.find((p) => Number(p.id) === Number(rest[1]));
      if (!player) throw Object.assign(new Error('player not found'), { status: 404 });
      if (body.firstName !== undefined) player.first_name = body.firstName;
      if (body.lastName !== undefined) player.last_name = body.lastName;
      if (body.grade !== undefined) player.grade = String(body.grade);
      if (body.active !== undefined) player.active = !!body.active;
      save(state);
      return { ok: true, player };
    }

    const tid = Number(rest[0]);
    const players = () => state.players
      .filter((p) => p.team_season_id === tid)
      .sort((a, b) => Number(b.active) - Number(a.active)
        || a.last_name.localeCompare(b.last_name)
        || a.first_name.localeCompare(b.first_name));

    // An unknown team id is an opponent who has not registered. Returning an
    // empty roster is correct, not a gap: the dual page falls back to a
    // free-text "Opponent name" field for exactly this case.
    if (method === 'GET') return { team: team(tid), players: players(), canEdit: true };

    const add = (first, last, grade) => {
      const exists = state.players.some((p) => p.team_season_id === tid
        && p.first_name.toLowerCase() === first.toLowerCase()
        && p.last_name.toLowerCase() === last.toLowerCase());
      if (exists) return false;
      const id = Math.max(950000, ...state.players.map((p) => p.id)) + 1;
      state.players.push({ id, team_season_id: tid, first_name: first, last_name: last,
        grade: String(grade || ''), tr_player_id: null, active: true });
      return true;
    };

    if (rest[1] === 'import') {
      let added = 0;
      for (const line of String(body.text || '').split('\n')) {
        const s = line.trim().replace(/\s+/g, ' ');
        if (!s) continue;
        let first, last;
        if (s.includes(',')) { [last, first] = s.split(',', 2).map((x) => x.trim()); }
        else {
          const bits = s.split(' ');
          if (bits.length < 2) continue;
          first = bits.slice(0, -1).join(' '); last = bits[bits.length - 1];
        }
        if (first && last && add(first, last, '')) added += 1;
      }
      save(state);
      return { added, players: players() };
    }

    if (!body.firstName || !body.lastName) {
      throw Object.assign(new Error('both names are required'), { status: 400 });
    }
    add(body.firstName.trim(), body.lastName.trim(), body.grade);
    save(state);
    return { ok: true, players: players() };
  }

  if (group === 'duals') {
    const id = Number(rest[0]);

    if (method === 'GET' && !rest.length) {
      await loadSchools();
      const tid = Number(url.searchParams.get('team'));
      return {
        duals: state.duals.filter((d) => d.team_season_id === tid).map((d) => summarise(state, d)),
        awaitingYou: [],
      };
    }

    if (method === 'GET') {
      const d = state.duals.find((x) => Number(x.id) === id);
      if (!d) throw Object.assign(new Error('dual not found'), { status: 404 });
      return { dual: d };
    }

    if (method === 'POST' && !rest[1]) {
      const d = { id: state.nextDualId++, lines: [] };
      applyPayload(d, body, state);
      state.duals.push(d);
      save(state);
      return { dual: d };
    }

    const d = state.duals.find((x) => Number(x.id) === id);
    if (!d) throw Object.assign(new Error('dual not found'), { status: 404 });

    if (method === 'PUT') {
      applyPayload(d, body, state);
      save(state);
      return { dual: d };
    }

    if (method === 'POST' && ['confirm', 'dispute', 'resolve'].includes(rest[1])) {
      d.status = rest[1] === 'confirm' ? 'confirmed'
        : (rest[1] === 'dispute' ? 'contested' : (body.status || d.status));
      save(state);
      return { ok: true };
    }

    if (method === 'DELETE') {
      state.duals = state.duals.filter((x) => Number(x.id) !== id);
      save(state);
      return { ok: true };
    }
  }

  throw Object.assign(new Error(`no demo route for ${method} ${path}`), { status: 404 });
}

/**
 * Is there a real backend?
 *
 * One probe per page load. Demo mode is what happens when the answer is no —
 * it is a fallback, never a preference — with two overrides for the cases where
 * guessing would be wrong: `?demo=1` to show the demo on a configured site, and
 * `?demo=0` to see the real failure while debugging one.
 */
export async function probeBackend() {
  const forced = new URLSearchParams(location.search).get('demo');
  if (forced === '1') return false;
  if (forced === '0') return true;

  // NOT /api/auth/__ping — that route answers {ok:true} without ever touching
  // the database, so it reports healthy on a deployment that cannot store a
  // single result. /api/setup runs a real query and says whether it is ready.
  try {
    const res = await fetch('/api/setup', { credentials: 'same-origin' });
    if (res.ok) return !!(await res.json()).ready;
  } catch { /* fall through */ }

  // /api/setup predates nothing, but a deploy could be older than it. Fall back
  // to a route that does hit the database: it answers 200 with a null coach
  // when the backend is fine and nobody is signed in.
  try {
    const res = await fetch('/api/auth/me', { credentials: 'same-origin' });
    return res.ok;
  } catch {
    return false;
  }
}
