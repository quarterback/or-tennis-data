# Bringing the Ladder and Position Matrix to oregontennis.org

**What this is:** a coach-facing **Lineups** section that, for any one team, shows its **ladder ("letter order")** — the rank order of players with the court(s) each played and their **win-loss record at every court** — plus a season **position matrix** showing where each rostered player appeared, court by court. It reads from the real match results already scraped into the site, sits behind a sign-in, and is deliberately kept off the public navigation while OSAA reviews it. [Open the tool →](lineups.html)

**Date:** 2026-07-16 (built and shipped to branch)
**Branch:** `claude/tournament-lineup-challenges-6a54ts`
**Author:** Engineering, iteratively scoped with the site owner.
**Access:** private preview — shared-passcode sign-in, not linked from the main nav.

## Why this exists

The proposed state-tournament format leans on three things a coach or administrator needs to *see*, not just trust:

1. **A team's ladder** — the rank order of players by strength, which a coach verifies and, at a point before the playoffs, submits as a **final locked ladder**.
2. **Letter order with results** — being able to look at that ladder and see, per player, the positions they played and how they did there.
3. **An anti-stacking check** — a way to confirm a team didn't quietly drop a strong player to a low court to steal a flight.

All of this already exists in the tennis simulator (the "Lineup Lab" and the per-player, by-position records), but in the simulator the position records are buried on each player's own page. The job here was to **migrate those tools onto oregontennis.org** and surface the records where they actually matter — at the team-ladder level — using the match data the site already collects.

## What we built

Two views over one team at a time, reachable by narrowing **classification → district → gender → team**:

- **Team Ladder.** Players in rank order. Each row shows the court(s) that player played as chips carrying the **win-loss record at that court** (`1S 2–4`, `1D 2–0`, …), the player's usual court emphasized, and an overall record. A coach with the team's access code can reorder to their verified order and submit or lock the final ladder.
- **Position Matrix.** A player × court grid (1S–4S, 1D–3D) of how many times each player appeared at each court, heat-shaded by volume, with an overall record column and a per-cell record on hover. Each row expands to that player's full match log — date, court, result, set scores and opponent.

The whole section opens on a **sign-in gate** — a shared passcode, hashed in the browser so the plain code isn't sitting in the page source, remembered for the session. It is a soft gate to keep the preview private, not per-coach account security.

## How the data is derived

A standalone builder, `build_lineup_data.py`, transforms the scraped meet JSON (`data/<year>/school_<id>_gender_<g>.json`) into per-team files the page fetches. It is wired into `generate_site.py`'s build as a best-effort step, so it refreshes whenever the data pipeline runs.

The key move is **attribution by `schoolId`.** Every player object in a match line already carries the school it belongs to, so for each team file we keep only the lines where a player's `schoolId` matches that file's school. That cleanly pulls a team's own appearances out of both ordinary duals and multi-team postseason events, with no cross-file de-duplication needed. From there:

- **Slots** are counted per court (`S1`–`S4`, `D1`–`D3`).
- **Records** are tallied per court and overall from each appearance's win flag (a court match doesn't tie: not-won is a loss).
- **The derived ladder** orders players by the strength of the court they usually play, with singles and doubles interleaved — a 1-doubles regular ranks among the stronger players rather than beneath every singles player. This is a *starting point*, nothing more (see below); the coach sets the real order.

## Decisions worth recording

**One team at a time — no all-teams printout.** An early cut rendered every team's ladder in a filtered class/district at once. That was the wrong shape: it's long, and a coach only cares about the specific opponent they're playing. The tool exists so the information is *available and reachable per team*, mostly for a playoff matchup — not to be read end to end. The filters exist to *find* the one team, not to dump all of them.

**The coach's ladder is authoritative; the derived order is only a fallback.** If a coach has submitted a ladder, that order *is* the ladder — the view says so ("Coach ladder · draft/locked"). Only when no coach ladder exists do we show the data-derived order, clearly labeled as such. Any player missing from a coach's saved order falls in behind by derived order, so nobody disappears. We did **not** try to make the derivation cleverer (e.g. weighting by win rate at each court) — usual-court is a good enough default for the one job it has, which is to seed the coach's verification.

**Challenge matches stay on paper.** The original brief included logging same-team challenge matches to establish the singles order. We deliberately left that out of the system. Most coaches will never use it, it would pollute the data, and paper forms already handle the rare case. The only thing written to the backend is the submitted ladder — a tiny record per team.

**Records surfaced at the ladder, not just the player page.** The one concrete gap versus the simulator was *where* the by-position records lived. Putting them directly on the ladder rows — and on the matrix cells — is the whole point: you verify an opponent's letter order and see their per-court results in the same glance.

## Architecture notes

Nothing here is new plumbing — it reuses what the SD1 tournament tools already proved out:

- **Static page.** `public/lineups.html` is self-contained (site CSS conventions, dependency-free vanilla JS), like the existing SD1 pages.
- **Derived data.** Per-team JSON under `public/data/lineups/<year>/`, plus an index for the pickers. Scoped to **2026 only** for the demo.
- **Persistence.** `netlify/functions/lineups.mjs` stores the submitted ladder in Netlify Blobs, mirroring the `scores.mjs`/`draws.mjs` functions and their `/api/<name>/*` routing. Writes are gated by a **per-team access code** (claim-on-first-submit, with an optional `LINEUPS_ADMIN_TOKEN` override); everyone can view without a code.

## What it does and doesn't claim

It does not rank teams, predict winners, or judge that any lineup was improper. It is a transparency tool: it takes the results already in the system and lets an authorized viewer see one team's verified (or, failing that, data-derived) ladder and the court-by-court record behind it. When this graduates from an OSAA preview to coaches submitting binding ladders, the honest next step is real per-coach accounts — the per-team submit codes already in the backend are the write-side of that.

[Open the tool →](lineups.html)
