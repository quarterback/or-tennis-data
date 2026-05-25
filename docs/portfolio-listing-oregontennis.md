# oregontennis.org

*The data that changed a state championship.*

---

In May 2026, the OSAA adopted a dual team tennis championship — boys and
girls, across 6A, 5A, and 4A-1A — with the first tournaments in 2027. It's
the first new team format Oregon tennis has had, and it makes Oregon the most
recent state to join the more-than-half of the country that already crowns a
team champion. (Colorado was the last before this.)

oregontennis.org is the data backbone that made the case. The argument for the
new championship — who would qualify, how brackets would seed, how many more
kids would actually get to play, what the travel looked like — wasn't asserted.
It was *computed*, published, and handed to the committee as a working model.
The state championship committee recommended adoption; the OSAA accepted it.

This is the whole arc: notice a problem, build the evidence, make the
argument, and take it all the way to the people who decide.

---

## The bigger story

Oregon tennis only ever had an individual tournament — singles and doubles.
Roughly 10–15% of varsity players ever reached state; a 12-player roster might
send two. Twenty-seven other states already ran a dual team championship.
Oregon didn't.

Changing that required more than a pitch. It required answering every
practical objection with data: *Can teams field viable rosters? How big should
the brackets be? Who gets auto-bids? What does it do to travel? How do you seed
it fairly?* oregontennis.org existed to answer exactly those questions — first
as a ranking experiment, then as the analytical engine behind a multi-year
advocacy effort, documented along the way in proposals, redistricting analysis,
and after-action reports.

The result: a recommendation, then adoption, then a real event on the 2027
calendar.

---

## Everything on the site

It started as a rankings table. It's now a small suite of public tools.

**Rankings dashboard** — Four interlocking views in one app:
— *Rankings* — every team rated by four different models, filterable by year, class, and league
— *Playoff Simulator* — what-if brackets, including a regional mode that optimizes travel against competitive integrity
— *Comparison* — head-to-head and model-vs-model, so you can see where the math disagrees with itself
— *Analysis* — the deeper cuts behind the numbers

**Methodology** — The Power Index explained in plain language, so the rankings are auditable rather than a black box.

**Weekly rankings** — In-season snapshots, week by week, so the picture is live, not just a year-end summary.

**All-State archive** — All-State teams, 2022–2025, preserved in one place.

**Bracket tools** — A permutation explorer and a fair-bracket generator that stress-test how different seedings would actually play out.

**SD1 draw suite** — A live seeding board, draw tool, and printable/live brackets built to run an actual special-district tournament in the room, on the day, with cloud-saved state.

**2027 format tools** — Built ahead of the new event: a mixed-doubles standby-list tool and the dual team finals format the advocacy effort created.

**Changelog & after-action reports** — The work shown openly: what changed, what was tested, what was learned, including an A/B test of two rating models written up honestly.

---

## The models

**APR** — Adjusted Power Rating. RPI-style strength of schedule: your wins
matter, your opponents' wins matter more, theirs matter too. *"How good are
you, given who you played?"*

**FWS / oFWS** — Flight-Weighted Score. A dual meet is eight positions, not
one. Winning 6–1 is deeper than scraping 4–3. FWS weights each flight,
normalizes for short matches, and the opponent-weighted variant folds in *who*
you beat. *"How deep is your roster?"*

**Power Index** — The blend. Half APR, half normalized FWS — winning and depth
in one number.

**TOSS** — A later model folding in game-share margin, A/B-tested against the
Power Index, with results reported rather than assumed.

**H2H engine** — When teams are close, head-to-head breaks the tie — but only
when it doesn't create a rock-paper-scissors loop (A beats B beats C beats A).
The edge cases are the whole job.

---

## Stack

**Generation** Python — every model computed and emitted as one self-contained `index.html` with the data embedded
**Geocoding** Nominatim / OpenStreetMap, geocoded once and cached so fresh clones never hit the network
**Frontend** Vanilla JS + Bootstrap + DataTables over embedded JSON; React/TypeScript/Vite in the original prototype
**Live tooling** Netlify Functions (v2) + Netlify Blobs for the cloud-saved SD1 draw
**Hosting** Netlify — static, zero-infrastructure, offline-capable
**Data** ~1,200 team-seasons, every flight, 2021–present, straight from the OSAA source API

---

## Why it matters

The boring choices are deliberate. Static HTML and embedded JSON instead of a
backend, because the audience — coaches and athletic directors — needs
something fast, free, and saveable, not a platform to log into. The interesting
choices are everywhere else: in the rating math, the tiebreaker edge cases, the
travel optimization, and the decision to publish the proposals instead of just
shipping numbers.

The point of the project isn't the rankings. It's that a clear, honest model,
made public and argued well, can move an institution. The site is the proof of
work — the championship is the outcome.

→ [oregontennis.org](https://oregontennis.org)
