# Cheesybook — coach-entered results, and the pages that read them

**What this is:** the reporting and reading side of oregontennis.org, built as
its own product. Coaches enter their dual matches; scoreboard, team pages,
player cards and the selection board are all built from what they enter, folded
in over the TennisReporting scrape. [Open it →](cheesybook.html)

---

## Why it exists

Two problems, one answer.

**The scrape cannot see the whole card.** Oregon plays four singles and four
doubles, but the TennisReporting API does not reliably carry the fourth flight.
`test_api_endpoints.py` in this repository is the owner's own probe of that
question — it hits the API nine ways looking for `"flight":"4"` and ends with
"if none of these show Flight 4 data, the API may not provide it." Cheesybook is
the answer that does not depend on the API ever exposing it: a coach enters all
eight flights, and coach-entered results are authoritative over the scrape for
the same dual.

**Nobody publishes league champions.** Oregon does not document them anywhere.
The selection board therefore derives them, and says that it did.

## What got built

| Piece | What it does |
|---|---|
| `coach*.html` | Sign in, manage a roster, report a dual, confirm what an opponent reported |
| `netlify/functions/` | Passwordless auth, roster, duals, admin, setup check |
| `scoreboard.html` | Every dual by day, grouped, with box scores |
| `team.html` | A team's season: schedule, by-position, ladder, position matrix |
| `player.html` | A player's card: season line, positions, full match log |
| `teams.html` | Every team by league, searchable |
| `committee.html` | The state selection board |
| `seeding/` | Print-ready league seeding packets |

## Decisions worth remembering

**A dual publishes when it is filed, not when it is confirmed.** The away coach
confirms or disputes; a disputed dual is still published and flagged. Waiting on
a coach who never signs in would silently drop the other team's season, and
freezing disputes out of the maths would reward disputing every loss.

**4-4 is a tie for the team that lost the tiebreaker.** Head-to-head is a
separate, stricter question than the record: a dual level at 4-4 stands as a tie
in the standings, but the team that lost on sets-then-games lost the head to
head. The two are stored separately because a selection committee asks both.

**Nothing assumes eight flights.** `box_score` skips absent flights instead of
padding them, `flight_score` counts only lines present, and the tie path
triggers on `home == away` whatever that number is. A scraped six-flight dual
scores out of six; a Cheesybook dual out of eight. This is what lets the
fourth-flight gap be real without breaking anything downstream.

**League champions are derived through the tiebreakers the site already had.**
Best league win percentage, then Power Index, then bubble-swapping adjacent
teams within 0.1 win percentage when the lower won the head to head — the same
steps as `loadTeamsForSelection` in the playoff simulator. If the two disagreed,
the board and the simulator would name different champions.

**Demo mode is a fallback, never a preference.** With no database the coach
pages probe `/api/setup`, find nothing, and fall back to an in-browser backend
with the same routes and shapes. It probes `/api/setup` and not
`/api/auth/__ping` — that route answers `{ok:true}` without touching the
database, so it reports healthy on a deployment that cannot store a single
result.

**Two exports join at read time.** The committee export has names and season
records; the lineups export has player ids, per-position records and where each
player appeared. The lineups file name is computable — gender digit then school
id — so team pages, player cards and box-score names all link up without either
exporter changing.

## Bugs this turned up

**The Netlify deploy was broken and the checks looked green.** `_db.mjs` and
`_db.test.mjs` sat at the top level of `netlify/functions/`, where every file is
bundled as a function. The helper exports no handler and the test is not an
endpoint. Moving them to `lib/` and `tests/functions/` fixed the deploy — and
stopped shipping test code to production.

**The tests never ran on a pull request.** The workflow only fired on a schedule,
so the data commit was gated but review was not. That is how a failing deploy
reached a PR that looked fine. Fixing it immediately surfaced a third problem:
`test_api_endpoints.py` is a probe script whose `test_endpoint(url, params, …)`
signature makes pytest try to inject fixtures. `pytest.ini` now pins
`testpaths`.

**Search broke navigation on every device.** The search boxes on Teams and
Scoreboard were bound to `input` and `change`. Clicking a result blurred the box,
`change` fired, the list re-rendered, and the anchor under the cursor was
destroyed before the click landed. I saw this once and wrote it off as a slow
page because the URL worked directly — it was not slow, it was broken.

**Links that were invisible were effectively absent.** Team names were wrapped in
anchors with `color: inherit`, giving a target a few glyphs wide that looked
exactly like the text beside it. The whole row is the link now.

**The demo saved into a team nobody was looking at.** The save payload carries
`year` + `genderId` + school ids and no `team_season_id`; the demo read a field
that does not exist. The save reported success and the hub stayed empty. Found
by driving the flow in a browser rather than assuming it worked.

## Design direction

The pages went from reading like a dashboard to reading like a sports page, in
several passes and mostly by removing things:

- **Games first.** The scoreboard led with a full screen of filters; they now
  collapse behind one button and the first card sits ~220px down. Date
  navigation is the primary control.
- **No counts.** Checked against ESPN's own scoreboard payload: a completed card
  carries Final, each team's record, a winner flag, and links — never a count of
  periods. Per-quarter data exists but lives inside the box score.
- **Conference is a filter, not a card detail.** ESPN offers Top 25 / FBS / ACC /
  Big Ten; this offers league, grouped under classification.
- **The season is a timeline.** One card per match read as a dashboard. It is now
  a divided list at 48px a row — nine games below the fold on a phone, against
  two or three before — expanding in place with an animated height.
- **No microcopy.** Headings do not restate what the layout already says.

Two pieces of prose stayed on purpose: the derived-champions banner, because
without it a committee reads an inferred bid as a reported one; and the coach
pages' instructions, because a form filled in once a season by a volunteer is
the one place guidance earns its place.

## Mobile

Every page measures zero horizontal overflow, zero controls that trigger iOS
zoom on focus, and zero sub-24px controls at 390px. The sizing lives once in
`brand.css` — restated in `coach.css`, which loads later and beat a media-query
rule of equal specificity.

## Brand

Name and look are two files: `js/brand.js` and `css/brand.css`. Three palettes
ship, switchable with `?palette=cool|warm|cheese` and swatches on the front page.
Funkora carries the wordmark, Heilo Champion the headings; tables stay on the
system font, because this is a product people read four-digit Power Indexes off,
down a column, on a phone at a court.

Raw `#ffd800` is about 1.3:1 on white and `#ffa600` about 2:1, so neither can
carry text. They are backgrounds and rules; where those hues need reading, the
tokens use darkened forms.

## What is not done

- **No database yet.** Three steps, about ten minutes — see
  `docs/SETUP-reporting.md`. Until then the coach pages run in demo mode and
  every other page works from the scrape.
- **Email is optional.** Without a Resend key, sign-in links go to the function
  log. Fine for testing, not for coaches.
- **The wordmark font is a placeholder** pending a custom face.
- **The selection board is unlisted** — reachable by URL, not linked, until
  closer to the state tournament.
- **`league_champions.csv` is empty.** Champions derive from the standings; a
  league settled by tournament or vote can be entered there to override.
