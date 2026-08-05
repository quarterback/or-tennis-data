# Standing up Cheesybook

Everything on oregontennis.org so far has been static files plus a couple of
small Netlify functions storing blobs. The reporting system is the first part
that needs a real database and a few secrets. This is the whole list, in order.

Nothing here breaks the existing site. Until it is done, the reporting pages
say they cannot reach the backend and every other page carries on exactly as
now.

**Check your progress at any point by opening `/api/setup` on the deployed
site.** It reports what is configured and what is missing, and never prints a
secret. Do the four steps below and it turns green.

---

## 1. A database (~5 minutes, free)

The reporting system needs Postgres. Two ways, both fine:

**Easiest — Netlify's own:** In the Netlify dashboard for the site, go to
**Extensions → Netlify DB** (it provisions Neon behind the scenes) and enable
it. It sets `NETLIFY_DATABASE_URL` for you and there is nothing to copy. The
code accepts that variable name as well as `DATABASE_URL`, so it just works.

**Or directly:** sign up at [neon.tech](https://neon.tech), create a project,
and copy the **pooled** connection string it shows you. It looks like:

```
postgresql://user:password@ep-something-pooler.us-west-2.aws.neon.tech/neondb?sslmode=require
```

Then in Netlify → **Site configuration → Environment variables**, add:

| Name | Value |
|---|---|
| `DATABASE_URL` | the connection string you copied |

The free tier is far more than this needs — a whole season of Oregon tennis is
a few megabytes.

## 2. Create the tables (~1 minute)

The schema lives in `db/schema.sql`. Apply it once:

```
psql "postgresql://…the same connection string…" -f db/schema.sql
```

If you do not have `psql`, Neon's dashboard has an **SQL Editor** — paste the
contents of `db/schema.sql` into it and run. The file is safe to run twice;
every statement is `CREATE … IF NOT EXISTS`.

## 3. Two secrets (~2 minutes)

Still in Netlify → **Site configuration → Environment variables**:

| Name | Value | What it does |
|---|---|---|
| `SESSION_SECRET` | any long random string | Signs the sign-in cookie. Generate one with `openssl rand -hex 32`, or mash the keyboard for 40 characters. Changing it later just signs everyone out. |
| `ADMIN_EMAILS` | your email address | Whoever signs in with a listed address becomes an administrator. Comma-separated for more than one. |

That is the required set. Redeploy (or trigger any deploy) so the functions
pick them up.

## 4. Load the teams and rosters (~2 minutes)

This fills in the 266 team-seasons, the coach email addresses already in the
scraped data, and last season's rosters carried forward:

```
export DATABASE_URL="postgresql://…"
pip install "psycopg[binary]"
python scripts/seed_reporting_db.py --year 2027
```

Add `--dry-run` first if you want to see the counts without writing anything.

---

## Optional: emailing the sign-in links

Without this, sign-in links are written to the Netlify function log instead of
being emailed. That is enough for you to test with — open the function log,
copy the link, paste it in the browser — but no good for real coaches.

Sign up at [resend.com](https://resend.com) (free tier is 3,000 emails a
month, and this needs a few hundred a season), verify the sending domain, and
set:

| Name | Value |
|---|---|
| `RESEND_API_KEY` | the key from Resend |
| `AUTH_FROM_EMAIL` | e.g. `Oregon HS Tennis <no-reply@oregontennis.org>` |

## Optional: letting the nightly build read entered results

The GitHub Action needs its own read-only view of the database to fold coach
entries into the site. In the repository → **Settings → Secrets and variables
→ Actions**, add `DATABASE_URL_RO` with the same connection string (or a
read-only role if you make one).

Skip this and the site simply builds from the scrape, exactly as it does now —
that step is deliberately allowed to fail without taking the build down.

---

## Opening it to a league

Nothing is enterable until a team is switched on. Sign in at `/coach.html`
with an address in `ADMIN_EMAILS`, then flip `entry_enabled` for the teams in
the beta league. That flag is what the beta is: everyone else sees the site
unchanged.

## If something looks wrong

- **`/api/setup`** — the fastest answer; it names the specific thing missing.
- **A page says the backend is unavailable** — a variable is missing, or the
  deploy predates adding it. Redeploy.
- **"the tables do not exist yet"** — step 2 has not run against the database
  the site is actually pointed at.
- **Sign-in link never arrives** — expected until `RESEND_API_KEY` is set; the
  link is in the function log.
