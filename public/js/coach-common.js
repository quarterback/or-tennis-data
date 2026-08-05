import { BRAND } from './brand.js';
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
  { key: 'played', label: 'Played', hint: 'Normal match, enter the set scores.' },
  { key: 'retired', label: 'Retired', hint: 'A player quit mid-match. The other side wins whatever the score was.' },
  { key: 'default', label: 'Default', hint: 'One team had nobody at this position. The other side wins the point.' },
  { key: 'skipped', label: 'Not played', hint: 'Neither team contested this position. It counts for nobody.' },
];

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

    let lastContested = 0;
    for (const { f, i } of indexes) {
      if (CONTESTED.has(lines[i].outcome)) lastContested = f.flight;
    }
    for (const { f, i } of indexes) {
      if (f.flight >= lastContested) continue;
      if (!CONTESTED.has(lines[i].outcome)) {
        const played = FLIGHTS.find((x) => x.matchType === matchType && x.flight === lastContested);
        problems.push(
          `${f.label} was not played but ${played.label} was. Forfeits come from ` +
          `the bottom of the card up, so ${played.label} cannot be played while ` +
          `${f.label} is empty.`);
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
  // The hero has a .container of its own and comes first in the document, so
  // querySelector('.container') puts the banner inside the dark header. Take
  // the first one that is not part of the chrome.
  const host = [...document.querySelectorAll('.container')]
    .find((el) => !el.closest('.hero') && !el.closest('.navbar'));
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

/** Render the shared navbar and hero into the page. */
export function renderChrome({ title, subtitle }) {
  const nav = document.querySelector('.navbar-inner');
  if (nav) {
    // Sibling-relative, matching lineups.html and methodology.html — the
    // publish root is whatever those already resolve against.
    nav.innerHTML =
      '<a class="back" href="cheesybook.html">&larr; Cheesybook</a>' +
      '<a class="back" href="coach.html">Report</a>' +
      '<a class="back" href="scoreboard.html">Scoreboard</a>' +
      '<a class="back" href="lineups.html">Lineups</a>' +
      '<a class="back" href="index.html">Rankings</a>' +
      `<span class="brand">${BRAND.name}</span>`;
  }
  const hero = document.querySelector('.hero .container');
  if (hero) {
    // The <p> is always rendered, empty or not: pages fill it in with the team
    // name once the session loads, and a conditional element means they have to
    // null-check something that is only sometimes there.
    hero.innerHTML = `<h1>${escapeHtml(title)}</h1><p>${escapeHtml(subtitle || '')}</p>`;
  }
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
            <button id="signin-go">Send the link</button>
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
