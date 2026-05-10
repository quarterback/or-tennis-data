// Persistence backend for the SD1 live tournament bracket.
//
// GET  /api/scores/<id>   -> 200 { ...state } | 404
// PUT  /api/scores/<id>   -> 200 { ok: true, updatedAt }   (admin token required if env var is set)
// DELETE /api/scores/<id> -> 200 { ok: true }              (admin token required if env var is set)
// GET  /api/scores/__ping -> 200 { ok: true }
//
// State is one JSON blob per tournament (e.g. id="2026"), holding both the
// singles and doubles trees. See sd1-live-bracket.html for the full schema.

import { getStore } from '@netlify/blobs';

const STORE_NAME = 'sd1-tournament-results';
const ADMIN_TOKEN_ENV = 'SD1_ADMIN_TOKEN';

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store' }
  });
}

function extractId(req) {
  const url = new URL(req.url);
  const parts = url.pathname.split('/').filter(Boolean);
  return decodeURIComponent(parts[parts.length - 1] || '');
}

function isValidId(id) {
  return /^[A-Za-z0-9._-]{1,64}$/.test(id);
}

function isAuthorized(req) {
  const expected = process.env[ADMIN_TOKEN_ENV];
  if (!expected) return true; // no token configured = open writes (dev mode)
  const supplied = req.headers.get('x-admin-token');
  return supplied === expected;
}

export default async function handler(req) {
  const id = extractId(req);
  if (id === '__ping') return json({ ok: true });
  if (!isValidId(id)) return json({ error: 'invalid id' }, 400);

  const store = getStore(STORE_NAME);

  if (req.method === 'GET') {
    const data = await store.get(id, { type: 'json' });
    if (data == null) return json({ error: 'not found' }, 404);
    return json(data);
  }

  if (req.method === 'PUT' || req.method === 'POST') {
    if (!isAuthorized(req)) return json({ error: 'unauthorized' }, 401);
    let body;
    try { body = await req.json(); }
    catch { return json({ error: 'invalid json' }, 400); }
    body.updatedAt = new Date().toISOString();
    await store.setJSON(id, body);
    return json({ ok: true, updatedAt: body.updatedAt });
  }

  if (req.method === 'DELETE') {
    if (!isAuthorized(req)) return json({ error: 'unauthorized' }, 401);
    await store.delete(id);
    return json({ ok: true });
  }

  return json({ error: 'method not allowed' }, 405);
}

export const config = { path: '/api/scores/*' };
