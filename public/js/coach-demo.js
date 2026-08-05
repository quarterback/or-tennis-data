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

// Real Oregon schools, so a demo does not show invented ones to coaches who
// would notice. Two teams, so the team picker has something to pick.
const TEAMS = [
  { id: 9001, year: 2027, school_id: 124895, school_name: 'Catlin Gabel', gender_id: 2,
    is_jv: false, league: 'Special District 1', classification: '4A/3A/2A/1A', entry_enabled: true },
  { id: 9002, year: 2027, school_id: 124895, school_name: 'Catlin Gabel', gender_id: 1,
    is_jv: false, league: 'Special District 1', classification: '4A/3A/2A/1A', entry_enabled: true },
];

const NAMES = [
  ['Ada', 'Whitfield', '12'], ['Nora', 'Ellingsen', '12'], ['Priya', 'Raghunathan', '11'],
  ['Signe', 'Halvorsen', '11'], ['Marisol', 'Vega', '10'], ['Juno', 'Kastellanos', '10'],
  ['Beatrix', 'Ahlgren', '9'], ['Wren', 'Okonkwo', '9'], ['Talia', 'Bergström', '11'],
  ['Cleo', 'Mbeki', '12'],
];

function seed() {
  const players = [];
  let pid = 950000;
  for (const team of TEAMS) {
    for (const [first, last, grade] of NAMES) {
      players.push({
        id: pid++, team_season_id: team.id, first_name: first, last_name: last,
        grade, tr_player_id: null, active: true,
      });
    }
  }
  return { players, duals: [], nextDualId: 8001, nextLineId: 700001 };
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
  return TEAMS.find((t) => Number(t.id) === Number(id)) || TEAMS[0];
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
  const ours = TEAMS.find((t) => Number(t.gender_id) === gender
    && (Number(t.school_id) === Number(body.homeSchoolId)
      || Number(t.school_id) === Number(body.awaySchoolId))) || TEAMS[0];

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
    if (rest[0] === 'me') return { coach: COACH, teams: TEAMS };
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
