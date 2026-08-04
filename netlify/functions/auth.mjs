// Passwordless sign-in for coaches.
//
//   POST /api/auth/request  {email}   -> 204 (always)
//   GET  /api/auth/callback?token=    -> 302 to /coach.html, session cookie set
//   GET  /api/auth/me                 -> {coach, teams}
//   POST /api/auth/logout             -> 204
//   GET  /api/auth/__ping             -> {ok: true}
//
// Why magic links rather than passwords or the per-team access code in
// lineups.mjs: every scraped school file already carries the team's coach email
// (`coaches[].email`), so mailing a link to the address TennisReporting has on
// file for that team IS the claim check — no manual verification, and stronger
// than a shared code that anyone can pass along. Coaches touch this six weeks a
// year, so password resets in April are a support cost nobody will absorb.
//
// Tokens are stored only as a SHA-256 hash and consumed atomically, so a link
// cannot be replayed and a database read yields nothing usable.

import {
  HttpError, claimedTeams, clearCookie, currentCoach, db, json,
  readJson, route, segments, sessionCookie, sha256Hex, signSession,
  SESSION_TTL_SECONDS,
} from './_db.mjs';

const TOKEN_TTL_MINUTES = 15;
const MAX_LINKS_PER_WINDOW = 5;   // per email, per TTL window

function randomToken() {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return [...bytes].map((b) => b.toString(16).padStart(2, '0')).join('');
}

function siteOrigin(req) {
  return process.env.URL || process.env.DEPLOY_PRIME_URL || new URL(req.url).origin;
}

async function sendMagicLink(email, link) {
  const key = process.env.RESEND_API_KEY;
  if (!key) {
    // Local development and preview deploys without mail configured. The link
    // goes to the function log and never to the client, so an unconfigured
    // production deploy cannot hand out sessions.
    console.log(`[auth] magic link for ${email}: ${link}`);
    return;
  }
  const from = process.env.AUTH_FROM_EMAIL || 'Oregon HS Tennis <no-reply@oregontennis.org>';
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { authorization: `Bearer ${key}`, 'content-type': 'application/json' },
    body: JSON.stringify({
      from,
      to: [email],
      subject: 'Your oregontennis.org sign-in link',
      text: [
        'Use the link below to sign in and report match results.',
        '',
        link,
        '',
        `The link works once and expires in ${TOKEN_TTL_MINUTES} minutes.`,
        'If you did not ask to sign in, you can ignore this message.',
      ].join('\n'),
    }),
  });
  if (!res.ok) {
    console.error(`[auth] Resend ${res.status}: ${await res.text()}`);
    throw new HttpError(502, 'could not send the sign-in email');
  }
}

async function handleRequest(req) {
  const body = await readJson(req);
  const email = String(body.email || '').trim().toLowerCase();

  // Always 204, whatever happens below. Any variation in status, body or timing
  // would let someone enumerate which coaches have accounts.
  const ok = new Response(null, { status: 204 });
  if (!email || !email.includes('@')) return ok;

  const sql = db();
  const rows = await sql`SELECT id, email FROM coach WHERE lower(email) = ${email}`;
  const coach = rows[0];
  if (!coach) return ok;

  const [{ recent }] = await sql`
    SELECT count(*)::int AS recent FROM auth_token
     WHERE coach_id = ${coach.id}
       AND created_at > now() - ${`${TOKEN_TTL_MINUTES} minutes`}::interval
  `;
  if (recent >= MAX_LINKS_PER_WINDOW) return ok;

  const token = randomToken();
  await sql`
    INSERT INTO auth_token (token_hash, coach_id, expires_at, request_ip)
    VALUES (${await sha256Hex(token)}, ${coach.id},
            now() + ${`${TOKEN_TTL_MINUTES} minutes`}::interval,
            ${req.headers.get('x-nf-client-connection-ip')})
  `;

  await sendMagicLink(coach.email, `${siteOrigin(req)}/api/auth/callback?token=${token}`);
  return ok;
}

async function handleCallback(req) {
  const token = new URL(req.url).searchParams.get('token') || '';
  const fail = (reason) =>
    Response.redirect(`${siteOrigin(req)}/coach.html?error=${reason}`, 302);
  if (!token) return fail('missing');

  const sql = db();
  // Consume and validate in one statement: a replayed link finds used_at already
  // set and returns nothing, with no window between the check and the write.
  const rows = await sql`
    UPDATE auth_token SET used_at = now()
     WHERE token_hash = ${await sha256Hex(token)}
       AND used_at IS NULL
       AND expires_at > now()
    RETURNING coach_id
  `;
  if (!rows.length) return fail('expired');

  const coachId = rows[0].coach_id;

  // Admin membership is held in an environment variable so the first
  // administrator can exist before anyone can grant anything.
  const admins = (process.env.ADMIN_EMAILS || '')
    .split(',').map((s) => s.trim().toLowerCase()).filter(Boolean);
  const [coach] = await sql`
    UPDATE coach SET last_login_at = now(),
                     is_admin = is_admin OR lower(email) = ANY(${admins})
     WHERE id = ${coachId}
    RETURNING id, email, is_admin
  `;

  const exp = Math.floor(Date.now() / 1000) + SESSION_TTL_SECONDS;
  const session = await signSession({ sub: coach.id, exp });
  await sql`
    INSERT INTO audit_log (actor_coach_id, entity, entity_id, action)
    VALUES (${coach.id}, 'coach', ${coach.id}, 'login')
  `;

  return new Response(null, {
    status: 302,
    headers: { location: `${siteOrigin(req)}/coach.html`, 'set-cookie': sessionCookie(session) },
  });
}

async function handleMe(req) {
  const coach = await currentCoach(req);
  if (!coach) return json({ coach: null, teams: [] });
  return json({
    coach: { id: coach.id, email: coach.email, name: coach.name, isAdmin: coach.is_admin },
    teams: await claimedTeams(coach),
  });
}

async function handleLogout(req) {
  const coach = await currentCoach(req);
  if (coach) {
    await db()`
      INSERT INTO audit_log (actor_coach_id, entity, entity_id, action)
      VALUES (${coach.id}, 'coach', ${coach.id}, 'logout')
    `;
  }
  return new Response(null, { status: 204, headers: { 'set-cookie': clearCookie() } });
}

export default async function handler(req) {
  return route(async () => {
    const [action] = segments(req, 'auth');
    if (action === '__ping') return json({ ok: true });

    if (req.method === 'POST' && action === 'request') return handleRequest(req);
    if (req.method === 'GET' && action === 'callback') return handleCallback(req);
    if (req.method === 'GET' && action === 'me') return handleMe(req);
    if (req.method === 'POST' && action === 'logout') return handleLogout(req);

    throw new HttpError(404, 'unknown auth action');
  });
}

export const config = { path: '/api/auth/*' };
