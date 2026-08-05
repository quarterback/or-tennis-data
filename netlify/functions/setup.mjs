// A setup check: what is configured, what is missing, what to do next.
//
//   GET /api/setup -> {ready, checks: [...]}
//
// Standing this system up means provisioning a database, applying a schema and
// setting four environment variables, and until every one of those is done the
// reporting pages fail in ways that look like bugs. This answers "what is
// actually wrong" in one request.
//
// It reports only whether each value is PRESENT, never what it is. The database
// check runs a real query, because a connection string that is set but wrong is
// the failure that wastes the most time.

import { databaseUrl, db, json, route } from './lib/db.mjs';

async function databaseCheck() {
  if (!databaseUrl()) {
    return {
      key: 'Database',
      ok: false,
      detail: 'No connection string.',
      fix: 'Add a Postgres database, then set DATABASE_URL. Netlify\'s own '
         + 'Postgres integration sets NETLIFY_DATABASE_URL, which also works.',
    };
  }
  try {
    const [{ n }] = await db()`SELECT count(*)::int AS n FROM team_season`;
    return {
      key: 'Database',
      ok: true,
      detail: `Connected. ${n} team-season${n === 1 ? '' : 's'} on file.`,
      fix: n === 0
        ? 'Schema is applied but empty — run scripts/seed_reporting_db.py.'
        : '',
    };
  } catch (err) {
    const missingSchema = /relation .* does not exist/i.test(String(err.message));
    return {
      key: 'Database',
      ok: false,
      detail: missingSchema
        ? 'Connected, but the tables do not exist yet.'
        : `Could not query: ${err.message}`,
      fix: missingSchema
        ? 'Apply the schema: psql "$DATABASE_URL" -f db/schema.sql'
        : 'Check the connection string is the pooled URL from your provider.',
    };
  }
}

export default async function handler() {
  return route(async () => {
    const checks = [await databaseCheck()];

    checks.push({
      key: 'Session secret',
      ok: !!process.env.SESSION_SECRET,
      detail: process.env.SESSION_SECRET ? 'Set.' : 'Not set — nobody can sign in.',
      fix: process.env.SESSION_SECRET ? ''
        : 'Set SESSION_SECRET to any long random string. It signs the session '
        + 'cookie; changing it later just signs everyone out.',
    });

    const admins = (process.env.ADMIN_EMAILS || '').split(',').filter((s) => s.trim());
    checks.push({
      key: 'Administrator',
      ok: admins.length > 0,
      detail: admins.length
        ? `${admins.length} address${admins.length === 1 ? '' : 'es'} listed.`
        : 'Nobody is an administrator.',
      fix: admins.length ? ''
        : 'Set ADMIN_EMAILS to your own email. Whoever signs in with a listed '
        + 'address becomes an administrator on first login.',
    });

    // Email is genuinely optional: without a key the sign-in link is written to
    // the function log instead of sent, which is enough to test with.
    checks.push({
      key: 'Email delivery',
      ok: true,
      optional: true,
      detail: process.env.RESEND_API_KEY
        ? 'Sign-in links are emailed.'
        : 'Not configured — sign-in links go to the function log instead of '
        + 'being emailed. Fine for testing, not for coaches.',
      fix: process.env.RESEND_API_KEY ? ''
        : 'Set RESEND_API_KEY from resend.com to email real coaches.',
    });

    const required = checks.filter((c) => !c.optional);
    return json({
      ready: required.every((c) => c.ok),
      remaining: required.filter((c) => !c.ok).length,
      checks,
    });
  });
}

export const config = { path: '/api/setup' };
