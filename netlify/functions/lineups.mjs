// Persistence backend for the Lineups section (public/lineups.html).
//
// Stores ONE thing: a coach-submitted final ladder ("letter order") for a
// team-season, plus a lock flag and an optional note. The position matrix and
// the data-derived ladder are static (built by build_lineup_data.py); nothing
// coach-entered is needed for those. Challenge-match results are deliberately
// NOT stored here — coaches keep those on paper.
//
//   GET    /api/lineups/<id>   -> 200 { ladder, note, locked, updatedAt } | 404
//   PUT    /api/lineups/<id>   -> 200 { ok, updatedAt }   (team code required)
//   DELETE /api/lineups/<id>   -> 200 { ok }              (admin token required)
//   GET    /api/lineups/__ping -> 200 { ok: true }
//
// id is "<year>_<genderKey>", e.g. "2026_2124656" (girls, school 124656).
//
// Auth model — per-team access code (claim-on-first-submit):
//   * The FIRST PUT for a team claims it: the x-team-code header value is hashed
//     and stored. That coach now "owns" the team.
//   * Later PUTs must send the same x-team-code (matched against the stored hash).
//   * A wrong/missing code -> 403.
//   * If env LINEUPS_ADMIN_TOKEN is set, sending it as x-admin-token overrides any
//     team code (lets an administrator edit or, via DELETE, reset a team's claim).
// Blobs never expose the code — only its SHA-256 hash is persisted.

import { getStore } from '@netlify/blobs';

const STORE_NAME = 'hs-lineup-ladders';
const ADMIN_TOKEN_ENV = 'LINEUPS_ADMIN_TOKEN';

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
  });
}

function extractId(req) {
  const url = new URL(req.url);
  const parts = url.pathname.split('/').filter(Boolean);
  return decodeURIComponent(parts[parts.length - 1] || '');
}

function isValidId(id) {
  return /^[0-9]{4}_[0-9]{1,20}$/.test(id);
}

async function sha256(text) {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

function adminOk(req) {
  const expected = process.env[ADMIN_TOKEN_ENV];
  if (!expected) return false;
  return req.headers.get('x-admin-token') === expected;
}

// What we send back to the page — never the code hash.
function publicView(stored) {
  if (!stored) return null;
  return {
    ladder: stored.ladder || [],
    note: stored.note || '',
    locked: !!stored.locked,
    updatedAt: stored.updatedAt || null,
    claimed: !!stored.codeHash,
  };
}

export default async function handler(req) {
  const id = extractId(req);
  if (id === '__ping') return json({ ok: true });
  if (!isValidId(id)) return json({ error: 'invalid id' }, 400);

  const store = getStore(STORE_NAME);

  if (req.method === 'GET') {
    const data = await store.get(id, { type: 'json' });
    if (!data) return json({ error: 'not found' }, 404);
    return json(publicView(data));
  }

  if (req.method === 'PUT') {
    let body;
    try {
      body = await req.json();
    } catch {
      return json({ error: 'bad json' }, 400);
    }

    const existing = (await store.get(id, { type: 'json' })) || {};
    const isAdmin = adminOk(req);
    const suppliedCode = (req.headers.get('x-team-code') || '').trim();

    if (!isAdmin) {
      if (existing.codeHash) {
        // Team already claimed — the supplied code must match.
        if (!suppliedCode || (await sha256(suppliedCode)) !== existing.codeHash) {
          return json({ error: 'wrong team code' }, 403);
        }
      } else {
        // First claim — a code is required to establish ownership.
        if (suppliedCode.length < 4) {
          return json({ error: 'set a team code (min 4 chars) to claim this team' }, 403);
        }
      }
    }

    // Establish/keep the code hash.
    let codeHash = existing.codeHash || null;
    if (!codeHash && suppliedCode) codeHash = await sha256(suppliedCode);

    const ladder = Array.isArray(body.ladder) ? body.ladder.map(String) : existing.ladder || [];
    const updatedAt = new Date().toISOString();
    const next = {
      ladder,
      note: typeof body.note === 'string' ? body.note.slice(0, 2000) : existing.note || '',
      locked: typeof body.locked === 'boolean' ? body.locked : !!existing.locked,
      codeHash,
      updatedAt,
    };
    await store.setJSON(id, next);
    return json({ ok: true, updatedAt, locked: next.locked });
  }

  if (req.method === 'DELETE') {
    // Only an administrator can wipe a team's claim/submission.
    if (!adminOk(req)) return json({ error: 'admin token required' }, 403);
    await store.delete(id);
    return json({ ok: true });
  }

  return json({ error: 'method not allowed' }, 405);
}

export const config = { path: '/api/lineups/*' };
