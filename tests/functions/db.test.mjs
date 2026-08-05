// Unit tests for the session token and the small helpers around it.
//
//   node --test tests/functions/
//
// These need no database: everything covered here is pure. What they pin is the
// part where being wrong is worst — a session token that verifies when it should
// not is an account takeover, not a bug report.

import assert from 'node:assert/strict';
import { after, before, describe, it } from 'node:test';

process.env.SESSION_SECRET = 'test-secret-not-used-anywhere-real';

const {
  HttpError, clearCookie, route, segments, sessionCookie, sha256Hex,
  signSession, verifySession,
} = await import('../../netlify/functions/lib/db.mjs');

function req(url, headers = {}) {
  return new Request(url, { headers });
}

describe('session tokens', () => {
  it('round-trips a payload', async () => {
    const exp = Math.floor(Date.now() / 1000) + 60;
    const token = await signSession({ sub: 42, exp });
    const payload = await verifySession(token);
    assert.equal(payload.sub, 42);
  });

  it('rejects a tampered payload', async () => {
    const exp = Math.floor(Date.now() / 1000) + 60;
    const token = await signSession({ sub: 42, exp });
    const [body, sig] = token.split('.');
    // Re-encode the payload as a different coach, keeping the old signature.
    const forged = Buffer.from(JSON.stringify({ sub: 999, exp }))
      .toString('base64url');
    assert.equal(await verifySession(`${forged}.${sig}`), null);
    assert.notEqual(body, forged);
  });

  it('rejects a token signed with another secret', async () => {
    const exp = Math.floor(Date.now() / 1000) + 60;
    const token = await signSession({ sub: 1, exp });
    process.env.SESSION_SECRET = 'a-different-secret';
    const mod = await import(`../../netlify/functions/lib/db.mjs?bust=${Math.random()}`);
    assert.equal(await mod.verifySession(token), null);
    process.env.SESSION_SECRET = 'test-secret-not-used-anywhere-real';
  });

  it('rejects an expired token', async () => {
    const token = await signSession({ sub: 7, exp: Math.floor(Date.now() / 1000) - 1 });
    assert.equal(await verifySession(token), null);
  });

  it('rejects a token with no expiry', async () => {
    const token = await signSession({ sub: 7 });
    assert.equal(await verifySession(token), null);
  });

  it('rejects malformed input without throwing', async () => {
    for (const bad of ['', 'nodot', null, undefined, 'a.b.c.d', '...']) {
      assert.equal(await verifySession(bad), null);
    }
  });
});

describe('cookies', () => {
  it('is HttpOnly, Secure and SameSite=Lax', () => {
    const c = sessionCookie('abc');
    assert.match(c, /HttpOnly/);
    assert.match(c, /Secure/);
    assert.match(c, /SameSite=Lax/);
  });

  it('clears with a zero max-age', () => {
    assert.match(clearCookie(), /Max-Age=0/);
  });
});

describe('sha256Hex', () => {
  it('matches the known digest of "abc"', async () => {
    assert.equal(
      await sha256Hex('abc'),
      'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
    );
  });
});

describe('segments', () => {
  it('returns the path after the resource name', () => {
    assert.deepEqual(segments(req('https://x/api/duals/42/confirm'), 'duals'), ['42', 'confirm']);
    assert.deepEqual(segments(req('https://x/api/duals'), 'duals'), []);
    assert.deepEqual(segments(req('https://x/api/roster/player/7'), 'roster'), ['player', '7']);
  });

  it('decodes escaped segments', () => {
    assert.deepEqual(segments(req('https://x/api/admin/a%2Fb'), 'admin'), ['a/b']);
  });
});

describe('route', () => {
  it('turns an HttpError into its status', async () => {
    const res = await route(async () => { throw new HttpError(403, 'not your team'); });
    assert.equal(res.status, 403);
    assert.deepEqual(await res.json(), { error: 'not your team' });
  });

  it('does not leak an unexpected error to the client', async () => {
    const errors = [];
    const realError = console.error;
    console.error = (e) => errors.push(e);
    const res = await route(async () => { throw new Error('DATABASE_URL=postgres://secret'); });
    console.error = realError;

    assert.equal(res.status, 500);
    assert.deepEqual(await res.json(), { error: 'internal error' });
    assert.equal(errors.length, 1, 'the real error still reaches the logs');
  });
});
