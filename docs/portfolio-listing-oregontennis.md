# oregontennis.org

*A statewide sports-rating engine, playoff simulator, and live tournament toolkit — built as one self-contained system.*

---

oregontennis.org is the analytics platform for Oregon high school tennis: four
years of statewide results, four original rating models, a playoff simulator,
and a suite of live tournament tools, all generated from raw match data and
served as a single static site.

It's also the data layer behind a real institutional change — the analysis
that supported Oregon's adoption of a dual team tennis championship. The format
is now on the calendar: power-ranking-seeded brackets debuting in spring 2027 —
12 teams at 6A, 8 at 5A and 4A-1A, per gender — higher seed hosting through to
a final at the state championship site. The interesting part isn't the outcome;
it's how a small, honest, fully transparent system got built to make that kind
of argument possible.

---

## The problem it models

A tennis dual meet is eight concurrent matches — *matches within matches*.
Four singles, four doubles; win five flights and you win the meet. That
structure breaks ordinary ranking: a 5–3 win at the bottom of the lineup looks
identical to a 5–3 win at the top, win-loss records ignore who you played, and
lineups can be "stacked" to game any naive metric. There was no central data
and no rating that understood any of this.

So the system had to invent the measurement, then build everything on top of
it — ingestion, rating models, simulation, and the public tools — handling
real-world mess along the way: forfeits, ties, six-flight meets, classification
changes, and dirty source data.

---

## The models

**APR** — Adjusted Power Rating. RPI-style strength of schedule, aligned with
what the OSAA already uses: your wins matter, your opponents' more, theirs too.
*"How good are you, given who you played?"*

**FWS** — Flight-Weighted Score. Scores all eight flights on a weighted curve
(1st singles/doubles = 1.00 down to 4th doubles = 0.10, max 3.95). The top of
the lineup drives the number, but depth counts — a 7–1 sweep outscores a 5–3
win with the same top flights — which makes stacking pointless. Normalized for
flights actually contested, so a six-flight meet isn't penalized.

**FWS+** — FWS made legible, indexed like baseball's ERA+. 100 is exactly
average for the classification; 115 is 15% above. It recalibrates as the season
fills in, so a team's standing reads in real time and across history without
needing to know the raw averages.

**Power Index** — The blend: `(APR × 0.50) + (FWS × 0.50)`. Opponent quality
and flight dominance in one number, fuller than either alone.

**TOSS** — A later model folding in game-share margin, A/B-tested against the
Power Index with results reported, not assumed.

**H2H engine** — When teams are close, head-to-head breaks the tie — but only
when it doesn't create a rock-paper-scissors loop (A beats B beats C beats A).
Split series defer to the metrics. The edge cases are the whole job.

---

## Everything on the site

What began as an All-State archive is now a small suite of public tools.

**Rankings dashboard** — Four interlocking views in one app:
— *Rankings* — every team rated by the models, filterable by year, class, and league
— *Playoff Simulator* — what-if brackets, with a regional mode that optimizes travel against competitive integrity
— *Comparison* — head-to-head and model-vs-model, plus rating-vs-actual results (how well dual-meet strength predicts the individual tournament — spoiler: not very)
— *Analysis* — league strength, top to bottom

**Methodology** — The Power Index explained in plain language, so the rankings are auditable rather than a black box.

**Weekly rankings** — In-season snapshots, week by week — live, not just a year-end summary.

**All-State archive** — All-State teams, 2022–2025, in one place.

**Bracket tools** — A permutation explorer and a fair-bracket generator that stress-test how different seedings actually play out.

**SD1 draw suite** — A live seeding board, draw tool, and printable/live brackets built to run an actual special-district tournament in the room, on the day, with cloud-saved state.

**2027 format tools** — Built ahead of the new event: a mixed-doubles standby-list tool and the dual team finals format, matching the adopted bracket structure and seeding.

**Changelog & after-action reports** — The work shown openly: what changed, what was tested, what was learned.

---

## Stack & build

**Generation** A single Python program computes every model and emits one self-contained `index.html` with the data embedded — no database, no API, no server to defend, hosts anywhere.
**Geocoding** Nominatim / OpenStreetMap, geocoded once and cached so fresh clones never hit the network; powers the simulator's travel optimization.
**Frontend** Vanilla JS + Bootstrap + DataTables over embedded JSON; React/TypeScript/Vite in the original prototype.
**Live tooling** Netlify Functions (v2) + Netlify Blobs for the cloud-saved SD1 draw.
**Hosting** Netlify — static, zero-infrastructure, offline-capable.
**Data** ~1,200 team-seasons, every flight, 2021–present, straight from the OSAA source API.

---

## Design decisions

The boring choices are deliberate. Static HTML and embedded JSON instead of a
backend, because the audience — coaches and athletic directors — needs
something fast, free, and saveable, not a platform to log into. A dataset this
size belongs *in* the page. The model exposes raw, intuitive scores (0–3.95
FWS, ERA+-style FWS+) up front and keeps the normalized math underneath.

The interesting choices are everywhere else: the rating design that makes
stacking pointless, the tiebreaker logic that refuses to produce circular
results, the travel optimization that protects top seeds while cutting miles
for the rest, and the decision to publish the methodology so the numbers can be
trusted rather than taken on faith.

The throughline: a clear, honest, fully transparent model — built end to end,
from raw API to live tournament board — that's credible enough to move an
institution.

→ [oregontennis.org](https://oregontennis.org)
