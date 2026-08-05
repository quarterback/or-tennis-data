import { applyBrand } from './brand.js';
import { demoApi, probeBackend, resetDemo } from './coach-demo.js';

// Session handling and fetch wrappers shared by the coach-* pages.
//
// The four reporting pages each need identical sign-in handling, identical error
// reporting and the same backend health chip the SD1 tools use. Duplicating that
// four times is how they drift, so it lives here. Everything else on each page
// stays self-contained, the way the rest of public/ works.

export const FLIGHTS = [
  { matchType: 'Singles', flight: 1, label: '1S' },
  { matchType: 'Singles', flight: 2, label: '2S' },
  { matchType: 'Singles', flight: 3, label: '3S' },
  { matchType: 'Singles', flight: 4, label: '4S' },
  { matchType: 'Doubles', flight: 1, label: '1D' },
  { matchType: 'Doubles', flight: 2, label: '2D' },
  { matchType: 'Doubles', flight: 3, label: '3D' },
  { matchType: 'Doubles', flight: 4, label: '4D' },
];

/**
 * How a flight ended.
 *
 * `skipped` is not stored — the flight is simply left out of the dual, so it
 * counts for neither team and drops out of the flight denominator. That is what
 * makes a short card score correctly, and coaches agreeing to play a subset of
 * the eight is ordinary practice, not an exception.
 */
export const OUTCOMES = [
  { key: 'played', label: 'Completed' },
  { key: 'skipped', label: 'Not played' },
  { key: 'forfeit', label: 'Forfeit' },
  { key: 'retired', label: 'Retired' },
  { key: 'default', label: 'Default' },
];

/** Outcomes that need no score: one side simply took the point. */
export const AWARDED = new Set(['forfeit', 'default']);

const CONTESTED = new Set(['played', 'retired']);

/**
 * Check the bottom-up forfeit rule.
 *
 * A team short of players gives up the BOTTOM of the card, so the flights that
 * were actually played have to run from the top without a hole: playing fourth
 * singles while third singles went unplayed or defaulted is a data-entry error,
 * not a lineup. Returns an array of human-readable problems, empty when valid.
 *
 * `lines` is index-aligned with FLIGHTS.
 */
export function cardProblems(lines) {
  const problems = [];
  for (const matchType of ['Singles', 'Doubles']) {
    const indexes = FLIGHTS
      .map((f, i) => ({ f, i }))
      .filter(({ f }) => f.matchType === matchType);

    // A flight left on Completed with nothing in it has not been entered yet —
    // it is not evidence that the position was contested. Every flight starts
    // on Completed, so treating an empty one as played fired this warning
    // against rows the coach had not reached.
    const contested = (i) => CONTESTED.has(lines[i].outcome)
      && ((lines[i].sets || []).length
        || (lines[i].homePlayers || []).length
        || (lines[i].awayPlayers || []).length);

    let lastContested = 0;
    for (const { f, i } of indexes) {
      if (contested(i)) lastContested = f.flight;
    }
    for (const { f, i } of indexes) {
      if (f.flight >= lastContested) continue;
      if (!contested(i)) {
        const played = FLIGHTS.find((x) => x.matchType === matchType && x.flight === lastContested);
        const name = (x) => `${x.flight} ${x.matchType}`;
        problems.push(
          `${name(f)} was not played but ${name(played)} was. Forfeits come from ` +
          `the bottom of the card up, so ${name(played)} cannot be played while ` +
          `${name(f)} is empty.`);
      }
    }
  }
  return problems;
}

export function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

export function fmtDate(iso) {
  if (!iso) return '';
  try {
    // Date-only strings parse as UTC, which shows as the previous day west of
    // Greenwich. Split the parts rather than let the Date constructor decide.
    const [y, m, d] = String(iso).slice(0, 10).split('-').map(Number);
    return new Date(y, m - 1, d).toLocaleDateString(undefined,
      { weekday: 'short', month: 'short', day: 'numeric' });
  } catch { return iso; }
}

// Resolved once per page load by requireSession(); null until then.
let DEMO = null;

export function isDemo() { return DEMO === true; }

/** Fetch JSON from the API, turning a non-2xx into a thrown Error. */
export async function api(path, options = {}) {
  if (DEMO) return demoApi(path, options);
  const res = await fetch(path, {
    credentials: 'same-origin',
    headers: options.body ? { 'content-type': 'application/json' } : {},
    ...options,
  });
  if (res.status === 204) return null;

  let body = null;
  try { body = await res.json(); } catch { /* empty or non-JSON */ }
  if (!res.ok) {
    const err = new Error((body && body.error) || `request failed (${res.status})`);
    err.status = res.status;
    err.body = body;
    throw err;
  }
  return body;
}

/** The signed-in coach and the teams they may write for, or nulls. */
export async function session() {
  try {
    return await api('/api/auth/me');
  } catch {
    return { coach: null, teams: [] };
  }
}

export async function signOut() {
  if (DEMO) { resetDemo(); location.reload(); return; }
  await api('/api/auth/logout', { method: 'POST' });
  location.href = 'coach.html';
}

/** The backend health chip the SD1 and Lineups pages already show. */
export async function checkBackend(el) {
  if (!el) return;
  if (DEMO) {
    el.textContent = 'demo mode';
    el.className = 'backend';
    return;
  }
  try {
    await api('/api/auth/__ping');
    el.textContent = 'backend connected';
    el.className = 'backend ok';
  } catch {
    el.textContent = 'backend unavailable — changes will not save';
    el.className = 'backend fail';
  }
}

/**
 * Say plainly that this is a demo.
 *
 * Somebody being shown the tool needs to know the results they type are not
 * going anywhere — otherwise the first real season starts with a coach who
 * thinks they already reported three duals.
 */
function showDemoBanner() {
  if (document.getElementById('demo-banner')) return;
  const bar = document.createElement('div');
  bar.id = 'demo-banner';
  bar.className = 'banner warn';
  bar.style.cssText = 'display:flex;gap:10px;align-items:center;flex-wrap:wrap';
  bar.innerHTML = '<span><strong>Demo.</strong> Sign-in is off and nothing is '
    + 'saved to the server — everything you enter stays on this device.</span>'
    + '<button class="ghost tiny" id="demo-reset" style="margin-left:auto">Start over</button>';
  const host = document.querySelector('.wrap');
  if (host) host.prepend(bar);
  document.getElementById('demo-reset').onclick = () => { resetDemo(); location.reload(); };
}

export function setStatus(el, message, kind = 'ok') {
  if (!el) return;
  el.textContent = message;
  el.className = `status ${kind}`;
  if (kind === 'ok' && message) {
    setTimeout(() => { if (el.textContent === message) el.textContent = ''; }, 4000);
  }
}

export function teamLabel(team) {
  const gender = Number(team.gender_id) === 1 ? 'Boys' : 'Girls';
  const level = team.is_jv ? ' JV' : '';
  return `${team.school_name} ${gender}${level} ${team.year}`;
}

/** Remember the team the coach last worked with, across pages and visits. */
export const lastTeam = {
  get() {
    const fromUrl = new URLSearchParams(location.search).get('team');
    if (fromUrl) return Number(fromUrl);
    const stored = localStorage.getItem('ort_team');
    return stored ? Number(stored) : null;
  },
  set(id) {
    if (id) localStorage.setItem('ort_team', String(id));
  },
};

/**
 * Sets with both scores present and not level.
 *
 * A half-typed set is kept in the model — a coach types "6" before "3" — so
 * every reader has to skip them rather than treat a missing number as zero.
 */
export function completeSets(sets) {
  return (sets || []).filter((s) => {
    const h = s.homeGames;
    const a = s.awayGames;
    if (h === null || h === undefined || a === null || a === undefined) return false;
    return Number.isFinite(Number(h)) && Number.isFinite(Number(a)) && Number(h) !== Number(a);
  }).map((s) => ({ ...s, homeGames: Number(s.homeGames), awayGames: Number(s.awayGames) }));
}

/**
 * Which side won a flight, from its set scores.
 *
 * Returns 'home', 'away' or null when the line is incomplete. Deliberately
 * counts sets rather than trying to know the format — Oregon duals mix best-of-3,
 * 8-game pro sets and a 10-point tiebreak for the third, and the coach entering
 * the score already knows which one they played.
 */
export function lineWinner(sets) {
  let home = 0;
  let away = 0;
  for (const s of completeSets(sets)) {
    if (s.homeGames > s.awayGames) home += 1; else away += 1;
  }
  if (home === 0 && away === 0) return null;
  return home > away ? 'home' : (away > home ? 'away' : null);
}

/** Flights won by each side across a card. */
/**
 * The tiebreak on a level card — computed, never asked.
 *
 * A dual that finishes level goes to sets, then games. Both are already on the
 * card, so the coach is never asked to nominate a winner: totalling what they
 * typed is the whole rule. Mirrors `tiebreak_winner` in entered_shape.py, which
 * is what the pipeline applies on save.
 *
 * Returns null when the card is not level, and {basis: null} when sets AND
 * games are also level — a tie that stays a tie, which is a real result.
 */
export function cardTiebreak(lines) {
  const { home, away } = cardScore(lines);
  if (home !== away) return null;

  let hs = 0; let as = 0; let hg = 0; let ag = 0;
  for (const line of lines) {
    if (line.outcome === 'skipped') continue;
    for (const set of completeSets(line.sets)) {
      if (set.homeGames > set.awayGames) hs += 1; else as += 1;
      hg += set.homeGames;
      ag += set.awayGames;
    }
  }

  if (hs !== as) return { basis: 'sets', home: hs, away: as, homeWon: hs > as };
  if (hg !== ag) return { basis: 'games', home: hg, away: ag, homeWon: hg > ag };
  return { basis: null, home: hs, away: as, homeWon: null };
}

export function cardScore(lines) {
  let home = 0;
  let away = 0;
  for (const line of lines) {
    // A flight marked not-played counts for nobody, even though the coach may
    // have typed a score into it before changing their mind. The outcome is the
    // authority, not the leftover set boxes.
    if (line.outcome === 'skipped') continue;
    const w = line.homeWon === true ? 'home'
      : line.homeWon === false ? 'away'
        : lineWinner(line.sets);
    if (w === 'home') home += 1;
    else if (w === 'away') away += 1;
  }
  return { home, away };
}

/**
 * Render the page's chrome: the site masthead, then its heading.
 *
 * Same masthead as every other Cheesybook page, from js/brand.js — these are
 * not a separate tool a coach visits, they are part of the site.
 */
export function renderChrome({ title, subtitle }) {
  applyBrand(title, {
    current: 'Report',
    links: [
      { href: 'cheesybook.html', label: 'Home' },
      { href: 'scoreboard.html', label: 'Scoreboard' },
      { href: 'teams.html', label: 'Teams' },
      { href: 'lineups.html', label: 'Lineups' },
      { href: 'coach.html', label: 'Report' },
      { href: 'index.html', label: 'Rankings' },
    ],
  });
  const head = document.querySelector('.pagehead');
  if (head) {
    // The subtitle is always rendered, empty or not: pages fill it in with the
    // team name once the session loads, and a conditional element means they
    // have to null-check something that is only sometimes there.
    head.innerHTML = `<h1>${escapeHtml(title)}</h1><p class="sub">${escapeHtml(subtitle || '')}</p>`;
  }
}

/**
 * Set the line under the page heading — the team, once the session knows it.
 *
 * Pages used to reach for `.hero p` themselves, so moving the chrome onto the
 * shared masthead broke three of them at once. The selector lives here now.
 */
export function setSubtitle(text) {
  const el = document.querySelector('.pagehead .sub');
  if (el) el.textContent = text || '';
}

/**
 * Require a signed-in coach, rendering a sign-in prompt if there is not one.
 * Resolves to the session when signed in, or null when the prompt was shown.
 */
export async function requireSession(mountId = 'signin') {
  if (DEMO === null) DEMO = !(await probeBackend());
  if (DEMO) {
    showDemoBanner();
    return demoApi('/api/auth/me');
  }

  const s = await session();
  if (s.coach) return s;

  const mount = document.getElementById(mountId);
  if (mount) {
    mount.style.display = '';
    mount.innerHTML = `
      <div class="card">
        <div class="card-head">Sign in to report results</div>
        <div class="card-body">
          <p class="lede">Enter the email address your team is listed under. We
          will send you a link that signs you in — there is no password to
          remember.</p>
          <div class="row">
            <input type="email" id="signin-email" placeholder="coach@school.org"
                   autocomplete="email" class="grow">
            <button class="primary" id="signin-go">Send the link</button>
          </div>
          <p class="small muted" style="margin-top:10px">
            Not sure which address? It is the one on your team's TennisReporting
            page. If the link does not arrive, ask an administrator to add you.</p>
          <div id="signin-status" class="status" style="margin-top:8px"></div>
        </div>
      </div>`;

    const status = document.getElementById('signin-status');
    const send = async () => {
      const email = document.getElementById('signin-email').value.trim();
      if (!email.includes('@')) return setStatus(status, 'Enter a valid email address.', 'err');
      document.getElementById('signin-go').disabled = true;
      try {
        await api('/api/auth/request', { method: 'POST', body: JSON.stringify({ email }) });
        // Always the same message: the API deliberately does not reveal whether
        // an address has an account.
        status.textContent = 'If that address is registered, a sign-in link is on its way.';
        status.className = 'status ok';
      } catch (e) {
        setStatus(status, e.message, 'err');
      } finally {
        document.getElementById('signin-go').disabled = false;
      }
    };
    document.getElementById('signin-go').onclick = send;
    document.getElementById('signin-email').addEventListener('keydown', (e) => {
      if (e.key === 'Enter') send();
    });
  }
  return null;
}

/**
 * Parse a tennis score as a coach writes it.
 *
 * "6-4, 6-2" · "4-6, 6-3, 10-7" · "7-6(5), 6-4" · "6-0 6-0". An en dash reads
 * as a hyphen, because a phone keyboard and a paste from a scoresheet both
 * produce them. Returns { sets, error }; sets is index-ordered and shaped the
 * way the API takes them.
 *
 * This replaced a grid of six number inputs per flight. Coaches read scores off
 * a scoresheet in exactly this notation, and typing it is one field instead of
 * six tab stops.
 */
export function parseScore(text) {
  const raw = String(text || '').trim();
  if (!raw) return { sets: [], error: null };

  const chunks = raw
    .replace(/[\u2010-\u2015\u2212]/g, '-')   // en/em dash, minus
    .split(/[,;]|\s{2,}|\s(?=\d+\s*-)/)
    .map((c) => c.trim())
    .filter(Boolean);

  const sets = [];
  for (const chunk of chunks) {
    const m = chunk.match(/^(\d{1,2})\s*-\s*(\d{1,2})(?:\s*\((\d{1,2})\))?$/);
    if (!m) return { sets: [], error: `“${chunk}” is not a set score.` };
    const home = Number(m[1]);
    const away = Number(m[2]);
    if (home > 30 || away > 30) return { sets: [], error: `“${chunk}” is not a set score.` };
    if (home === away) return { sets: [], error: `“${chunk}” has no winner.` };
    sets.push({
      number: sets.length + 1,
      homeGames: home,
      awayGames: away,
      tiePoints: m[3] === undefined ? null : Number(m[3]),
    });
  }
  if (sets.length > 5) return { sets: [], error: 'A match is at most five sets.' };
  return { sets, error: null };
}

/** The inverse: sets back to the text a coach would have typed. */
export function formatScore(sets) {
  return (sets || [])
    .slice()
    .sort((a, b) => Number(a.number) - Number(b.number))
    .filter((s) => s.homeGames != null && s.awayGames != null)
    .map((s) => `${s.homeGames}-${s.awayGames}`
      + (s.tiePoints == null ? '' : `(${s.tiePoints})`))
    .join(', ');
}
