# Coach Reporting: making the site its own data source

**What this is:** a coach-facing reporting system on oregontennis.org. Coaches
sign in, manage a roster, and enter dual match results directly; those results
become authoritative over the TennisReporting scrape and flow through the
existing rankings pipeline untouched. It also adds the print-ready league seeding
packet that district committees need in May.

**Date:** 2026-08-04 (built, not yet enrolled)
**Branch:** `claude/oregon-tennis-reporting-mr6yvz`
**Author:** Engineering, scoped with the site owner.
**Status:** built and tested; no league is enrolled and no database is
provisioned. Target is a 2027 beta with several leagues.

## Why this exists

The site has been a one-way pipe. `fetch_data.py` scrapes TennisReporting,
`generate_site.py` turns that into rankings, a GitHub Action commits the result.
Everything the site does well — the TOSS Power Index, the weekly snapshots, the
Lineups ladder, all-state — is a read over somebody else's data, which caps the
site's quality at the quality of that scrape.

Two costs were already visible in the 2026 season:

- Oregon's dual card is four singles and four doubles, but **fourth singles and
  fourth doubles do not come through the TennisReporting API.** The 2026 season
  holds 64 fourth-singles and 70 fourth-doubles lines statewide against 2,879
  duals that arrived as six flights. This is a known limitation of the feed, not
  a statement about how Oregon plays, and it is not ours to fix upstream — two of
  every team's eight positions are simply absent from the record.
- `build_lineup_data.py` capped doubles at 3D, so even the handful of
  fourth-doubles lines that did arrive never reached the ladder or the matrix.

The second is a bug we fixed. The first is the argument for the whole project:
the only way those two positions get counted is if the coaches who played them
report them here.

2027 raises the stakes, because the proposed format adds a dual team
championship. Dual results stop being a curiosity and become a seeding input.

## The architectural bet

**Entered duals are compiled back into TennisReporting meet shape and written
into `data/<year>/school_<id>_gender_<g>.json`.**

`build_rankings()` globs exactly those files, and every other consumer reads
through it. Emitting TR shape means the 4,700-line ranking pipeline, the TOSS
formula, the head-to-head swap passes and the lineups derivation all keep working
unchanged. The alternative — refactoring `generate_site.py` to read a normalized
store — is a rewrite of the most load-bearing and least-tested code in the
repository, in exchange for nothing a coach would notice.

Two pieces of existing machinery made this cheap. `dedupe_meets()` already keyed
duplicate duals on `(date, unordered school pair)`, because both coaches posting
the same match to TennisReporting was already a problem; making entered data win
was adding a source rank to its existing tiebreak. And `sync-tr.mjs` had already
established the precedence pattern by refusing to clobber a line an operator had
corrected.

## What we built

**A Postgres store** (`db/schema.sql`) holding coaches, team-seasons, claims,
rosters, duals, flights, sets and an append-only audit log. Three sequences start
in reserved ranges — players at 900,000,000, duals at 800,000,000, lines at
700,000,000 — so a compiled meet's ids can never collide with a real
TennisReporting id, which is what lets the merge recognise and replace its own
output.

**Passwordless sign-in** (`netlify/functions/auth.mjs`). Every scraped school
file already carries the team's coach email, so mailing a sign-in link to the
address TennisReporting has on file for that team *is* the claim check — no
manual verification for the 262 addresses already on record, and stronger than a
shared access code anyone can pass along. Coaches touch this six weeks a year;
password resets in April are a support cost nobody would absorb.

**The reporting API** (`duals.mjs`, `roster.mjs`, `admin.mjs`). The home coach is
the reporter of record and the away coach confirms or disputes.

**The compile step**, split in two on purpose. `export_entered_meets.py` is the
only script that talks to the database; `merge_entered_data.py` is a pure
function of (scrape, bundle). A database outage in CI therefore degrades to
"the site builds from the scrape alone" rather than failing the build.

**Four coach pages** in `public/`, following the `lineups.html` conventions:
self-contained vanilla JS, site chrome, phone-first, installable.

**The seeding packet** (`build_seeding_packet.py`): one printable page per
league with standings, a head-to-head grid, a page per team carrying its
eight-flight record and ladder, and every league dual as a scorecard.

## Decisions worth recording

**A dual is published as soon as it is filed.** Confirmation raises confidence;
it does not gate publication. Waiting on a coach who never signs in would
silently drop the other team's season. For the same reason a disputed dual still
counts, flagged: freezing disputes out of the maths would reward disputing every
loss.

**Entered data wins statewide, not per league.** The owner chose the simpler
rule. It means one fat-fingered entry has teeth, which is why validation rejects
what a real dual cannot do — a level set, a player in two flights, a duplicate
flight, a date outside the season — and why every write is attributable in the
audit log.

**Two independent guards against double-counting.** The merge removes the
scraped twin, matching within a day to absorb the UTC skew that puts a late match
on the following date. `dedupe_meets` then applies the same rule again on load.
Counting a dual twice is the failure that would corrupt every metric while
looking entirely normal, so it gets two chances to be caught and an assertion if
both miss.

**JV goes in `data_jv/`, not a filename suffix.** `build_rankings` globs
`school_*_gender_*.json` and reads the gender from the fourth underscore-
separated field, so `school_X_gender_2_jv.json` would parse cleanly and fold
sub-varsity results into the varsity rankings.

**Titles never carry the event name.** `is_dual_match` rejects any meet whose
title contains "District", "State Championship", or "Event" with a period —
that is how TennisReporting's individual tournaments are filtered out. A district
team playoff is still a dual and still has to count, so compiled titles are
always "Away at Home".

**Cards are replaced, never merged.** The read-modify-write deep merge in
`scores.mjs` loses an edit when two people save at once. A dual's lines are
deleted and re-inserted in one transaction, and writes carry the timestamp the
client loaded, so a concurrent edit is a 409 rather than a silent overwrite.

**Rosters are pre-populated.** 266 team-seasons, 262 coach emails and 3,547
players carry forward from the 2026 scrape, seniors dropped and grades bumped. A
coach who has to type a roster from scratch in March stops using the system, so
nothing derivable is asked for.

## What this fixed on the way

**Fourth doubles now counts.** Adding `D4` to `build_lineup_data.py` and the
position matrix restored 32 players who were absent from their team's ladder
entirely and corrected 94 more with incomplete records. The system is now
first-class eight-flight everywhere — entry card, ladder, matrix, rankings,
seeding packet — so when reporting replaces the feed it needs no further change.

**The build is deterministic.** Ranked teams were already emitted in rank order,
but unranked ones followed directory order, so `processed_rankings.json` churned
between a local checkout and the Actions runner with no value changing. Sorting
the glob fixed it, which is also what makes "the compile step is a no-op on an
empty database" a claim that can be checked.

**There are tests.** There were none. There are now 49 Python tests and 13
JavaScript tests, including a contract file that hands the adapter's output to
the real downstream functions rather than to a description of them, and an
end-to-end file that runs the chain a coach triggers.

## What is deliberately not here

**Challenge matches.** The Lineups AAR left them out because most coaches will
never use them and paper already handles the rare case. That still holds for the
beta; the ladder remains coach-submitted.

**Automated dispute resolution.** A contested dual during seeding week needs a
human. The admin queue plus a notification is the whole mechanism.

**Offline entry.** A `localStorage` draft, not a service-worker sync queue. A
background queue that silently replays a stale card into a versioned API is a
bug factory.

## What has to happen before a beta

Provision Neon and apply `db/schema.sql`; set `DATABASE_URL`, `DATABASE_URL_RO`,
`SESSION_SECRET`, `RESEND_API_KEY` and `ADMIN_EMAILS`; run
`scripts/seed_reporting_db.py --year 2027`; enrol a league by turning on
`entry_enabled`. Then run the merge in `--dry-run` for a couple of weeks and read
the diffs before letting it commit.
