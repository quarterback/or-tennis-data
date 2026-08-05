// Shared plumbing for the coach-reporting functions: database handle, session
// cookies, permission checks and small response helpers.
//
// Not a route itself — no `config.path` export, so Netlify never serves it.
//
// Concurrency note: the pattern this file exists to avoid is the read-modify-
// write deep merge in scores.mjs, where two coaches saving at once can lose an
// edit. Everything here writes through `tx()`, which sends a batch of statements
// to Postgres as one transaction. Because the HTTP driver cannot read a result
// mid-transaction, ids are reserved up front with `nextIds()` and the whole
// batch is built before anything is sent. Sequences are non-transactional, so
// burning a few ids on a rolled-back write is harmless.

import { neon } from '@neondatabase/serverless';

const SESSION_COOKIE = 'ort_session';
const SESSION_TTL_DAYS = 30;

let _sql = null;

/**
 * The connection string, whichever way the database was provisioned.
 *
 * Netlify's own Postgres integration injects NETLIFY_DATABASE_URL; a database
 * created directly at Neon gives you a string you paste in as DATABASE_URL.
 * Accepting both means the integration works with nothing else to configure.
 */
export function databaseUrl() {
  return process.env.DATABASE_URL || process.env.NETLIFY_DATABASE_URL || null;
}

/** Lazily-built Neon HTTP client. Throws a clear error if unconfigured. */
export function db() {
  if (_sql) return _sql;
  const url = databaseUrl();
  if (!url) throw new Error('no database configured (set DATABASE_URL)');
  _sql = neon(url);
  return _sql;
}

/** Run an array of tagged-template queries as a single transaction. */
export async function tx(queries) {
  return db().transaction(queries.filter(Boolean));
}

/**
 * Reserve `n` ids from a sequence in one round trip.
 *
 * Callers need the ids before they can build the statement batch (see the note
 * at the top of this file). Returns an array of Numbers — the reserved ranges
 * top out around 9e8, well inside a safe integer.
 */
export async function nextIds(sequence, n) {
  if (n <= 0) return [];
  const sql = db();
  // The sequence name is not user input; it comes from a fixed set of literals
  // in this codebase. Guard anyway so it can never become one.
  if (!/^[a-z_]+$/.test(sequence)) throw new Error(`bad sequence ${sequence}`);
  const rows = await sql(
    `SELECT nextval('${sequence}') AS id FROM generate_series(1, $1)`,
    [n]
  );
  return rows.map((r) => Number(r.id));
}

// ---------------------------------------------------------------------------
// Responses
// ---------------------------------------------------------------------------

export function json(body, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'content-type': 'application/json',
      'cache-control': 'no-store',
      ...extraHeaders,
    },
  });
}

export function csv(text, filename) {
  return new Response(text, {
    status: 200,
    headers: {
      'content-type': 'text/csv; charset=utf-8',
      'content-disposition': `attachment; filename="${filename}"`,
      'cache-control': 'no-store',
    },
  });
}

/** Thrown by the require* helpers; handled by `route()`. */
export class HttpError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

/**
 * Wrap a handler so thrown HttpErrors become responses and anything else
 * becomes a 500 without leaking a stack trace to the client.
 */
export async function route(fn) {
  try {
    return await fn();
  } catch (err) {
    if (err instanceof HttpError) return json({ error: err.message }, err.status);
    console.error(err);
    return json({ error: 'internal error' }, 500);
  }
}

export async function readJson(req) {
  try {
    return await req.json();
  } catch {
    throw new HttpError(400, 'invalid json');
  }
}

/** Path segments after /api/<name>/ — e.g. ['42', 'confirm']. */
export function segments(req, after) {
  const parts = new URL(req.url).pathname.split('/').filter(Boolean);
  const i = parts.indexOf(after);
  return i === -1 ? [] : parts.slice(i + 1).map(decodeURIComponent);
}

// ---------------------------------------------------------------------------
// Session tokens
//
// A compact signed token — base64url(JSON).base64url(HMAC-SHA256) — set as an
// HttpOnly cookie. Web Crypto only, so there is no dependency to keep current.
// ---------------------------------------------------------------------------

function b64url(bytes) {
  let bin = '';
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function b64urlDecode(str) {
  const pad = str.replace(/-/g, '+').replace(/_/g, '/');
  const bin = atob(pad + '='.repeat((4 - (pad.length % 4)) % 4));
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}

async function hmacKey() {
  const secret = process.env.SESSION_SECRET;
  if (!secret) throw new Error('SESSION_SECRET is not set');
  return crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign', 'verify']
  );
}

export async function sha256Hex(text) {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

export async function signSession(payload) {
  const body = b64url(new TextEncoder().encode(JSON.stringify(payload)));
  const sig = await crypto.subtle.sign('HMAC', await hmacKey(), new TextEncoder().encode(body));
  return `${body}.${b64url(new Uint8Array(sig))}`;
}

export async function verifySession(token) {
  if (typeof token !== 'string' || !token.includes('.')) return null;
  const [body, sig] = token.split('.');
  let ok = false;
  try {
    ok = await crypto.subtle.verify(
      'HMAC',
      await hmacKey(),
      b64urlDecode(sig),
      new TextEncoder().encode(body)
    );
  } catch {
    return null;
  }
  if (!ok) return null;
  let payload;
  try {
    payload = JSON.parse(new TextDecoder().decode(b64urlDecode(body)));
  } catch {
    return null;
  }
  if (!payload.exp || payload.exp * 1000 < Date.now()) return null;
  return payload;
}

export function sessionCookie(token) {
  const maxAge = SESSION_TTL_DAYS * 24 * 60 * 60;
  return `${SESSION_COOKIE}=${token}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${maxAge}`;
}

export function clearCookie() {
  return `${SESSION_COOKIE}=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0`;
}

export const SESSION_TTL_SECONDS = SESSION_TTL_DAYS * 24 * 60 * 60;

function cookieValue(req, name) {
  const header = req.headers.get('cookie') || '';
  for (const part of header.split(';')) {
    const [k, ...rest] = part.trim().split('=');
    if (k === name) return rest.join('=');
  }
  return null;
}

// ---------------------------------------------------------------------------
// Permissions
// ---------------------------------------------------------------------------

/** The signed-in coach, or null. Never throws for an absent session. */
export async function currentCoach(req) {
  const payload = await verifySession(cookieValue(req, SESSION_COOKIE));
  if (!payload) return null;
  const rows = await db()`
    SELECT id, email, name, is_admin FROM coach WHERE id = ${payload.sub}
  `;
  return rows[0] || null;
}

export async function requireCoach(req) {
  const coach = await currentCoach(req);
  if (!coach) throw new HttpError(401, 'sign in required');
  return coach;
}

export async function requireAdmin(req) {
  const coach = await requireCoach(req);
  if (!coach.is_admin) throw new HttpError(403, 'administrator only');
  return coach;
}

/**
 * Assert the coach may write for a team-season, and return that team.
 *
 * Admins pass for any team. A team whose `entry_enabled` is false is readable
 * but not writable — that flag is the per-league beta gate.
 */
export async function requireClaim(coach, teamSeasonId) {
  const rows = await db()`
    SELECT ts.*, (tc.coach_id IS NOT NULL) AS claimed
      FROM team_season ts
      LEFT JOIN team_claim tc
        ON tc.team_season_id = ts.id AND tc.coach_id = ${coach.id}
     WHERE ts.id = ${teamSeasonId}
  `;
  const team = rows[0];
  if (!team) throw new HttpError(404, 'team not found');
  if (!coach.is_admin && !team.claimed) throw new HttpError(403, 'not your team');
  if (!coach.is_admin && !team.entry_enabled) {
    throw new HttpError(403, 'entry is not open for this team yet');
  }
  return team;
}

/** Team-seasons this coach may write for. */
export async function claimedTeams(coach) {
  if (coach.is_admin) {
    return db()`
      SELECT ts.*, 'admin' AS role FROM team_season ts
       WHERE ts.entry_enabled
       ORDER BY ts.year DESC, ts.school_name, ts.gender_id
    `;
  }
  return db()`
    SELECT ts.*, tc.role FROM team_claim tc
      JOIN team_season ts ON ts.id = tc.team_season_id
     WHERE tc.coach_id = ${coach.id}
     ORDER BY ts.year DESC, ts.school_name, ts.gender_id
  `;
}

/**
 * An audit statement, ready to drop into a `tx()` batch.
 *
 * Returned rather than executed so the record commits or rolls back with the
 * change it describes.
 */
export function auditStmt(coachId, entity, entityId, action, before, after) {
  const sql = db();
  return sql`
    INSERT INTO audit_log (actor_coach_id, entity, entity_id, action, before, after)
    VALUES (${coachId}, ${entity}, ${entityId}, ${action},
            ${before ? JSON.stringify(before) : null}::jsonb,
            ${after ? JSON.stringify(after) : null}::jsonb)
  `;
}
