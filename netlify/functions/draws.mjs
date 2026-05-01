// Persistence backend for the SD1 bracket-draw page.
//
// GET  /api/draws/<id>   -> 200 { ...state } | 404
// PUT  /api/draws/<id>   -> 200 { ok: true, updatedAt }
// GET  /api/draws/__ping -> 200 { ok: true }   (used by the page to detect availability)
//
// State blobs are tiny (a few KB) and there's only one tournament a season,
// so this comfortably stays in Netlify's free tier.

import { getStore } from '@netlify/blobs';

const STORE_NAME = 'sd1-bracket-draws';

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store' }
  });
}

function extractId(req) {
  const url = new URL(req.url);
  // Path comes through as /.netlify/functions/draws/<id> after the redirect.
  const parts = url.pathname.split('/').filter(Boolean);
  return decodeURIComponent(parts[parts.length - 1] || '');
}

function isValidId(id) {
  return /^[A-Za-z0-9._-]{1,64}$/.test(id);
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
    let body;
    try { body = await req.json(); }
    catch { return json({ error: 'invalid json' }, 400); }
    body.updatedAt = new Date().toISOString();
    await store.setJSON(id, body);
    return json({ ok: true, updatedAt: body.updatedAt });
  }

  if (req.method === 'DELETE') {
    await store.delete(id);
    return json({ ok: true });
  }

  return json({ error: 'method not allowed' }, 405);
}

export const config = { path: '/api/draws/*' };
