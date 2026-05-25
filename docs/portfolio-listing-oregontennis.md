# oregontennis.org

*A ranking engine, playoff simulator, and governance argument for a sport nobody was measuring.*

---

Oregon high school tennis had no real way to rank teams. Win-loss records
ignored who you played and how deep your roster ran; seeding was committee
guesswork. So I built the thing that should have existed — a transparent,
defensible rating system, the public site that renders it, and the written
case for the state to adopt a better format.

It started as a stats question and turned into a full argument: data
pipeline, four original rating models, a simulator, a live seeding tool used
during an actual tournament, and a stack of proposals aimed at the people who
run the sport.

---

## What it does

— Ingests match-level results for every team, every flight, back to 2021
— Rates teams four different ways and lets you see where the models disagree
— Simulates playoff brackets, including a regional mode that cuts travel miles
— Runs a live seeding draw during the postseason, saved to the cloud
— Makes the case, in writing, for a team championship format that doesn't exist yet

---

## The models

**APR** — Adjusted Power Rating. RPI-style strength of schedule: your wins
matter, your opponents' wins matter more, their opponents matter too. Answers
*"how good are you, given who you played?"*

**FWS / oFWS** — Flight-Weighted Score. Tennis dual meets are eight positions,
not one. A team winning 6–1 every match is deeper than one scraping 4–3. FWS
weights each flight, normalizes for short matches, and the opponent-weighted
variant folds in *who* you beat. Answers *"how deep is your roster?"*

**Power Index** — The blend. Half APR, half normalized FWS — winning and depth
in one number.

**TOSS** — A later model built to fold in game-share margin, A/B-tested against
the Power Index with the results written up rather than asserted.

**H2H engine** — When two teams are close, head-to-head breaks the tie — but
only when it doesn't create a rock-paper-scissors loop (A beats B beats C beats
A). Split series defer to the metrics. The edge cases are the whole job.

---

## The pieces

| | |
|---|---|
| **Data pipeline** | OSAA athletics API → raw JSON → identity reconciliation across years → cascading statistics → static output. Handles forfeits, ties, missing flights, classification changes, and dirty city names. |
| **Static site generator** | A single Python program that computes every model and emits one self-contained `index.html` with the data embedded. No database, no API, no server to defend. Hosts anywhere. |
| **Playoff simulator** | What-if bracket builder. Regional mode protects the top seeds, optimizes the middle for geography, and anchors the bottom — using real coordinates, geocoded once and cached so fresh clones never hit the network. |
| **SD1 seeding tool** | A live draw board for a special-district tournament, with cloud persistence on Netlify Functions + Blobs. Built to be used in the room, on the day. |
| **Fair bracket generator** | A separate experiment in seeding brackets that balance competitive integrity against travel burden. |
| **The docs** | PRDs, an executive summary, a one-pager, a full team-championship proposal, redistricting analysis, and after-action reports. The part that turns a hobby project into a governance pitch. |

---

## Stack

**Generation** Python — statistics, geocoding (Nominatim, cached), single-file HTML emit
**Frontend** Vanilla JS + Bootstrap + DataTables, embedded JSON; React/TypeScript/Vite in the original prototype
**Live tooling** Netlify Functions (v2) + Netlify Blobs for the seeding draw
**Hosting** Netlify — static, zero-infrastructure, offline-capable
**Data** ~1,200 team-seasons, every flight, 2021–present, straight from the source API

---

## Why it matters

The boring choices are deliberate. Static HTML and embedded JSON instead of a
backend, because the dataset is small and the audience — coaches, athletic
directors — needs something fast, free, and saveable, not a platform to log
into. The interesting choices are everywhere else: in the rating math, the
tiebreaker edge cases, the travel optimization, and the decision to write the
proposals instead of just shipping the numbers.

It's a portfolio piece because it spans the whole arc — noticing a real problem,
modeling it honestly, building the tool, running it live, and arguing for the
change. Not just *can I build this*, but *can I see what's worth building and
take it all the way to the people who decide.*

→ [oregontennis.org](https://oregontennis.org)
