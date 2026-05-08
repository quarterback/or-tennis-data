# Skills & Learning Compendium — Oregon HS Tennis Rankings

A retrospective excavation of the skills, judgment, and ways of thinking
demonstrated across this project. Compiled from a walk through the AARs,
`generate_site.py`, `scripts/computer_rankings.py`,
`scripts/generate_weekly_rankings.py`, `scripts/build_rankings.py`, the
React/TypeScript frontend in `src/`, and the design docs in `docs/`.

The framing is deliberately resume- and learning-goal-oriented: every claim
is anchored to actual evidence in the repo (file paths and line numbers
where available), so the compendium can serve double duty as a portfolio
artifact and as a self-assessment.

---

## Table of contents

1. [The big picture in one paragraph](#the-big-picture-in-one-paragraph)
2. [Skills, by category](#skills-by-category)
   - 2.1 [Sports-rating system design](#21-sports-rating-system-design)
   - 2.2 [Statistical reasoning under uncertainty](#22-statistical-reasoning-under-uncertainty)
   - 2.3 [Numerical methods and algorithm debugging](#23-numerical-methods-and-algorithm-debugging)
   - 2.4 [Live experimentation discipline (A/B on real data)](#24-live-experimentation-discipline-ab-on-real-data)
   - 2.5 [Backwards-compatibility and versioning rigor](#25-backwards-compatibility-and-versioning-rigor)
   - 2.6 [Root-cause data-quality work](#26-root-cause-data-quality-work)
   - 2.7 [Software engineering hygiene](#27-software-engineering-hygiene)
   - 2.8 [Data pipeline / cadence engineering](#28-data-pipeline--cadence-engineering)
   - 2.9 [Frontend / full-stack reach](#29-frontend--full-stack-reach)
   - 2.10 [Domain modeling](#210-domain-modeling)
   - 2.11 [Stakeholder & requirements management](#211-stakeholder--requirements-management)
   - 2.12 [Technical writing for mixed audiences](#212-technical-writing-for-mixed-audiences)
3. [Ways of thinking on display](#ways-of-thinking-on-display)
4. [File-by-file evidence index](#file-by-file-evidence-index)
5. [Resume-ready phrasings](#resume-ready-phrasings)
6. [Learning goals to write toward next](#learning-goals-to-write-toward-next)
7. [What you could plausibly improve](#what-you-could-plausibly-improve)

---

## The big picture in one paragraph

You designed and operate a multi-model sports-rating system for Oregon high
school tennis. You scraped/ingest match data, built a multi-pass rating
pipeline (RPI-style APR with two-pass league-depth adjustment, an
opponent-weighted Flight Quality Index, an opponent-weighted Game Share
metric, and an iterated quality-weighted alternative), shipped them as a
forward-only A/B test on live data, decided the primary on stated criteria,
authored a portable PRD for the new metric so other states/sports can adopt
it, and wrote decision-grade After-Action Reports plus a non-technical policy
memo to the OSAA State Championship Committee. On top of that, the same data
feeds five computer-ranking algorithms (Elo, Colley, Massey, PageRank,
Win-Score) used to publish weekly composite rankings with quality-win
tracking and narrative generation. The work is hobbyist in setting and
professional in execution.

---

## Skills, by category

### 2.1 Sports-rating system design

You have built or implemented, from first principles, every metric in this
list:

- **OSAA-style RPI APR** — `WP × 0.25 + OWP × 0.50 + OOWP × 0.25`
  (`generate_site.py:39–43`).
- **Flight-Weighted Score (FWS)** — sport-specific roster-depth metric with a
  per-flight weighting table from S1/D1=1.00 down to S4/D4=0.10
  (`generate_site.py:24–34`, `calculate_fws_per_match` at `:731`).
- **Two-pass league-depth-adjusted APR** — recomputes OWP using
  leave-one-out league depth, so a team can't inflate its own SoS by being
  in its own league (`generate_site.py:72–76`, `loo_depth` helper at `:148`).
- **FQI (Flight Quality Index / portable name oFWS)** — opponent-APR-weighted
  flight score, formal spec authored in `docs/oFWS-PRD.md`.
- **oGS (opponent-weighted Game Share)** — set-type-aware aggregate game
  share, weighted by opponent strength
  (`calculate_fws_per_match`, `generate_site.py:844–865`).
- **TOSS** — composite three-component Power Index
  (`0.65·APR + 0.25·FQI + 0.10·oGS`), with the weights named as constants and
  documented in the AAR (`generate_site.py:49–53`).
- **QWS** — ITA-style iterated quality-weighted APR, with a flat loss
  penalty and explicit convergence guard (`generate_site.py:1190–1227`).
- **Five computer-ranking algorithms** — Elo, Colley, Massey, PageRank,
  Win-Score (`scripts/computer_rankings.py`).
- **Composite ranks** — average + median + std-dev across the five systems
  (`composite_ranks` at `scripts/computer_rankings.py:214`).

Anti-gaming logic is layered into the metrics themselves: FWS's
high-flight-weighting discourages "stacking" a star at a low flight; oGS
prevents a 6-2 flight win that came in three sets from looking the same as a
6-2 flight win in straight sets; LOO league depth prevents self-propping SoS.

### 2.2 Statistical reasoning under uncertainty

- **Empirical-Bayes shrinkage** as five phantom matches at the neutral
  baseline added to the per-match arithmetic mean
  (`generate_site.py:1155–1158`):
  ```python
  fqi = (total + TOSS_PRIOR_MATCHES * TOSS_PRIOR_VALUE) / (len(records) + TOSS_PRIOR_MATCHES)
  ```
  You also recognized that APR is *already* shrunk via the OWP/OOWP graph
  and explicitly chose not to double-shrink it (`:55–61`, comment).
- **Minimum-sample threshold**: `MIN_RANKED_MATCHES = 3` — teams below
  threshold appear as `NR`, not as a low-confidence numeric rank
  (`generate_site.py:65–70`, partition at `:1252–1264`;
  `scripts/generate_weekly_rankings.py:26`, `MIN_MATCHES = 3`).
- **Validation through correlation**: Spearman rank correlation across
  models (Current / TOSS / QWS at 0.97, 0.95, 0.98); Pearson correlation
  before/after weight rebalances (~0.96) to size the impact of formula
  changes. Captured in `AAR-power-index-ab-test.md` and
  `AAR-toss-ogs-fold-in.md`.
- **Distribution sanity checks**: TOSS schedule multiplier distribution
  reported (min 0.82 / median 0.95 / max 1.06) before promoting the model.
- **Spot checks against expected ordering**: top-of-table teams (Lincoln,
  Jesuit, Grant, OES, Catlin Gabel) verified to remain near the top across
  all three models before any switch.

### 2.3 Numerical methods and algorithm debugging

- **Singular-matrix bug in Massey ratings** caught and fixed: the
  Laplacian-style `M` was rank-deficient on a disconnected match graph;
  `np.linalg.solve` raised, the `except` set every rating to 0.0, and the
  stable sort then fell back to insertion order (school_id ascending). Fix
  was to use `np.linalg.lstsq` so each connected component gets its own
  minimum-norm solution (`scripts/computer_rankings.py:115–117`).
- **Iterative fixed-point computation** with explicit convergence guard:
  Jacobi-style iteration of QWS using the prior round's
  `power_index_qws`, breaking on `max |Δ| < QWS_CONVERGE_EPS` or
  `QWS_MAX_ITER` (`generate_site.py:1190–1227`). Converges in ~3
  iterations on live data.
- **PageRank power iteration** with damping=0.85, early-exit on
  `np.allclose(r, r_new, atol=1e-8)`, and column-normalized adjacency
  (`scripts/computer_rankings.py:122–163`). Tie handling is explicit
  (0.5/0.5 split — and you noticed the meet is walked from both sides, so
  the halves sum correctly).
- **Margin-dampened Elo** with `np.log1p(abs(margin))` so blowouts don't
  rocket-ride the rating (`scripts/computer_rankings.py:30–46`). Tie
  handling is tri-state (`a_won` can be `None` for true ties).
- **Massey margin cap** (`cap=6`) to bound the influence of lopsided
  results (`scripts/computer_rankings.py:87`).

### 2.4 Live experimentation discipline (A/B on real data)

- **Three models computed in parallel** on every team, every week, before
  any promotion. Baseline `power_index` is never modified during the parallel
  phase (`generate_site.py:1102–1106`).
- **Single mutation seam for promotion**:
  ```python
  school['power_index_legacy'] = school['power_index']
  school['power_index'] = school.get('power_index_toss', school['power_index'])
  ```
  (`generate_site.py:1241–1242`). Everything downstream (sort, league rank,
  H2H, playoff sim, class rank) reads `school['power_index']`, so flipping
  the primary model is one assignment in one place.
- **Independent rank maps per model** so the dropdown can re-display ranks
  without re-running pipelines (`generate_site.py:1273–1301`).
- **Decision criteria stated explicitly** before deciding TOSS over QWS:
  honors the "don't penalize scheduling up" constraint, smaller defensible
  change, fixes the obvious cases either way (`AAR-power-index-ab-test.md`,
  "Why TOSS (not QWS) as primary").
- **Calibration as a real exercise**: dry-ran Mild (45/45/10), Moderate
  (40/40/20), Aggressive (35/35/30) weight splits side by side before
  picking 40/40/20 (`AAR-toss-ogs-fold-in.md`, "Weight calibration"). Then
  rebalanced again to 65/25/10 a week later when live data showed the prior
  weights letting flight-dominant, weaker-record teams outrank stronger-
  record teams (`CHANGELOG.md` 2026-04-26).

### 2.5 Backwards-compatibility and versioning rigor

- **Date-gated feature flags as pure helpers** with env-var overrides
  (`_adjusted_models_enabled`, `_toss_is_primary` at
  `generate_site.py:109–127`). The `today` parameter makes them trivially
  testable.
- **Forward-only changes**: historical seasons (2021–2025) keep only the
  baseline fields; the three pre-cadence-shift Saturday weekly snapshots
  are byte-identical to before the change. Verified with the
  `ADJ_MODELS_ENABLED=0` invariance test
  (`AAR-power-index-ab-test.md`, "Baseline invariance").
- **Backwards-compat field aliases**: `normalized_fws`, `fws_plus`,
  `adjusted_fws` retained in JSON so external consumers don't break on
  rename (`generate_site.py:1135`, `:1161`; `CHANGELOG.md` 2026-04-26).
- **Backwards-compat function aliases**: `get_week_saturday =
  get_week_publish_date`, `all_week_saturdays = all_week_publish_dates`
  for older callers during the cadence transition
  (`scripts/generate_weekly_rankings.py:75–76, 137–138`).
- **Cadence transition rollforward**: between Apr 19 and Apr 25 inclusive,
  no-arg invocation rolls forward to Apr 26 instead of overwriting the
  last Saturday snapshot (`scripts/generate_weekly_rankings.py:60–65`).

### 2.6 Root-cause data-quality work

You diagnosed and fixed a series of subtle data bugs, each documented in
the changelog with a specific user-visible trigger case:

| Bug | Trigger case | Root cause | Fix |
|-----|--------------|-----------|-----|
| Duplicate dual matches | VC girls 7-2 vs Molalla 6-4 (both coaches posted) | Every consumer read raw `data['meets']` without dedup | `dedupe_meets()` keyed on `(date, sorted(school_ids))`, kept entry with most flights |
| Tournament-format duals dropped | Lincoln boys showing 4-0 vs API's 8-0-0 | `is_dual_match()` filtered any title containing "Tournament" | Removed the title check; structural `1 winner, 1 loser` guard catches genuine multi-team events |
| Tiebreaker losses miscoded as ties | La Salle Prep girls 3-2-5 vs OSAA 4-5-2 | Result inferred from flight scores only, ignoring `winnerSchoolId` | Tri-state result + `winnerSchoolId` fallback, propagated to all five computer-ranking algorithms |
| Stale league rank after H2H swap | League #1 sat below a league-mate in state rank | `school_league_rank` built once before swap, never recomputed | Rebuild from post-swap order |
| Massey ranked by school_id | Jesuit girls 9-0 at Massey #117 of 127 | Singular Laplacian on disconnected graph → all-zero ratings → stable sort fell back to insertion order | `lstsq` for minimum-norm solution per component |
| Quality-wins drift | Marist Catholic showing 0 quality wins vs visible 1 | Prior weeks recomputed in memory off evolving raw data | `load_published_week()` treats published JSON as canonical |

The pattern across all of these: **trace the bug to the actual line where the
wrong value is set, not just the symptom.** The `winnerSchoolId` fix
required updating four match-result functions in lockstep — and you found
the divergent copy in the weekly script that the canonical version had
already fixed.

### 2.7 Software engineering hygiene

- **Constants as a dependency map at the top of the file**
  (`generate_site.py:24–106`). Every weight, prior, gate, and threshold has
  a name and a comment explaining *why* it's that value. Rolling the formula
  back is editing constants, not chasing call sites — exactly what the
  AAR's "Rollback" section claims.
- **Comments earn their keep**. They explain *why* an invariant exists, not
  *what* the next line does. Example at `generate_site.py:1234–1238`:
  > "Promote TOSS to primary for 2026+: everything downstream … reads
  > `school['power_index']`, so overwriting it swaps the whole system onto
  > TOSS in one place."
- **Pure-function helpers** (`dedupe_meets`, `get_meet_result`,
  `_adjusted_models_enabled(today)`, `composite_ranks`) — easy to reason
  about, easy to unit-test, no global state.
- **Defensive recovery patterns**: opponent-id fallback scan when the first
  pass missed (`generate_site.py:832–836`); dict-key polymorphism for ints
  vs strings in upstream JSON (`:851`); deterministic tiebreakers everywhere
  (e.g., `(flight_count, -meet_id)` tuple comparison in `dedupe_meets`).
- **Explicit phase naming** in multi-step logic. The H2H tiebreaker has
  three named phases (in-league, adjacent-pair, classification-level), each
  with a documented purpose and a `would_create_circle()` cycle-guard so
  pairwise swaps can't produce intransitive cycles
  (`generate_site.py:1318–1505`).
- **Idempotent generation**: `main()` runs end-to-end and produces the same
  artifact for the same inputs. No incremental state to reconcile.

### 2.8 Data pipeline / cadence engineering

- **Continuous week numbering across a Saturday→Sunday cadence shift**
  (`scripts/generate_weekly_rankings.py:79–86`). The week-number function
  bridges the transition seamlessly: weeks 1–3 are Saturdays, week 4
  onwards are Sundays, no off-by-one.
- **Prior-publish-date helper that bridges the transition**: the Sunday of
  week 4 (2026-04-26) looks back to the Saturday of week 3 (2026-04-18),
  not 2026-04-19 (`scripts/generate_weekly_rankings.py:89–98`).
- **Published artifacts treated as canonical** for prior-week inputs.
  Quality-win calculation reads `public/data/weekly/<date>.json` instead of
  recomputing from drifting raw match data
  (`scripts/generate_weekly_rankings.py:101–115`).
- **Three CLI modes** with explicit semantics: current-week,
  `--all` (chain in memory), `--week YYYY-MM-DD` (single-week, load priors
  from disk).
- **Composite-rank tiebreaker chain**: composite → median (ascending — more
  consistent placement wins) → main-site PI (descending) → school_id
  (deterministic fallback) (`scripts/generate_weekly_rankings.py:460–469`).

### 2.9 Frontend / full-stack reach

- **TypeScript React app** consuming the JSON artifact: `App.tsx`,
  `RankingsTable.tsx`, `dataFetcher.ts`, `rankingCalculator.ts`,
  `types.ts`. Vite for dev/build (`package.json`).
- **Typed domain model** (`src/types.ts`): `School`, `SchoolData`,
  `SchoolStats`, `SchoolRanking`, `FLIGHT_WEIGHTS` typed and exported.
- **Same APR formula re-implemented in TypeScript** for client-side
  rendering of historical seasons (`src/rankingCalculator.ts:79`):
  `apr = (stats.wwp * 0.35) + (owp * 0.65)`. Cross-language correctness is
  on you, but it works.
- **GitHub-as-CDN data layer**: `dataFetcher.ts` reads
  `master_school_list.csv` and per-year JSON files directly from GitHub raw
  URLs and the contents API. No backend, no auth, no rate-limit handling
  beyond what the API gives you — but the static-site model makes that
  fine.
- **Inline static-site generation in Python**: `generate_html()` in
  `generate_site.py:1935+` produces a single ~3.4MB `index.html` with
  embedded JSON and DataTables/Bootstrap UI. The data is the page; no
  hydration round-trip needed.

### 2.10 Domain modeling

- **Domain primitives are first-class**: `FLIGHT_WEIGHTS` keyed by
  `(match_type, flight_number)`; per-flight stats keyed `S1`/`S2`/`D1`/etc.
  These names map directly to how a coach talks. A reader who knows tennis
  can read the data structures without translation.
- **Tennis-specific scoring rules encoded explicitly**:
  - Best-of-3 sets and 8-game pro sets contribute raw game totals.
  - Regular-set tiebreaker (the 7-6 case) → 1 deciding game, not raw TB
    points.
  - Match tiebreaker (set #3 with one side ≥ 10) → 1 game, not 17.
  - Flights without set-level data fall back to a binary one-game outcome
    so coverage stays high (98.1% in 2026).

  The detection is one line:
  `is_match_tb = (n >= 3) and len(vals) >= 2 and max(vals) >= 10`
  (`generate_site.py:856`).
- **Tri-state result type** (`'win' | 'loss' | 'tie'`) with explicit
  Oregon-tiebreaker fallback to `winnerSchoolId`. Distinguishes "couldn't
  tell" (`None`) from "true tie" — and the distinction propagates all the
  way through the five computer-ranking algorithms.
- **Proportional weighting for forfeits/short matches**: per-match
  denominator is the sum of weights of flights *contested*, not a fixed
  `MAX_FWS` (`calculate_fws_per_match` at `generate_site.py:731`).
- **Flight ID polymorphism**: handles `match.get(my_tid)` whether the
  upstream feed serialized team ids as strings or ints
  (`generate_site.py:851`).

### 2.11 Stakeholder & requirements management

- **Constraints surfaced up front**: every AAR opens with the site owner's
  explicit constraints before describing the design — "no back-dating,"
  "don't remove FWS," "no class-aware multiplier," "no explicit league-
  strength metric." Designs are then evaluated against those constraints.
- **Explainability named as a deciding factor**: TOSS chosen over QWS in
  part because it's "explainable in one sentence to coaches" — choosing the
  smaller defensible change over the structurally cleaner one is mature
  product judgment.
- **Non-goals as first-class deliverables**: every AAR has a "What we
  didn't do" / "Non-goals (worth restating)" section. Articulating what
  isn't changing is half the value of a design doc.
- **Deciding under uncertainty with a follow-up plan**: "Watch through end
  of season, decide for 2027 with evidence." Not pretending closure when
  the question is genuinely open.

### 2.12 Technical writing for mixed audiences

You produced four distinct genres of document, each fit for its audience:

- **Engineering AARs** (`AAR-power-index-ab-test.md`,
  `AAR-toss-ogs-fold-in.md`) — repeatable structure: *What we did → Why →
  What we considered → What shipped → How we know it works → What's next →
  Files changed → Non-goals*. Decision-grade, not status-grade.
- **Portable PRD** (`docs/oFWS-PRD.md`) — generalizes the metric beyond
  Oregon tennis, with goals, non-goals, formula, two-pass computation
  rationale, and adoption notes for other states/sports. Versioned
  ("Version: 1.0, Status: Implemented").
- **Policy memo** to the OSAA State Championship Committee
  (`memo_team_format_roster_analysis.md`) — short, evidence-tabled, with a
  conclusion that names a workable accommodation. Written for non-technical
  decision-makers.
- **Coach-facing methodology** (`docs/power-index-explained.md`,
  `docs/OSAA-One-Pager.md`, public `methodology.html`) — formulas with
  plain-English component explanations, examples, and traceable
  ranking-decision rationale.
- **Stakeholder proposals** (`docs/team-championship-proposal-v2.md`,
  `docs/proposed-special-districts.md`,
  `docs/regional-bracket-analysis.md`) — comparative tables, precedent
  citations, scoped recommendations.
- **Changelog as decision record** — every entry is structured *Problem →
  Root cause → Fix → Impact*, with magnitudes ("largest QWS drops were
  Sam Barlow -49 spots, Ridgeview -40, Redmond -32"). The changelog reads
  like a release-notes-meets-postmortem hybrid that keeps long-term context.

---

## Ways of thinking on display

1. **"What's the smallest change that fixes the actual complaint?"** —
   chose TOSS over QWS, multiplier on FQI rather than APR rewrite.
2. **Distinguishing additive from replacement changes** — explicitly framed
   oGS as additive so FQI's anti-stacking job stays intact.
3. **Treating calibration parameters as decisions to be defended** — every
   constant has a stated reason in the writeup, not just a value.
4. **Reasoning about second-order effects** — recognized OOWP transitively
   encodes opponent-of-opponent so a standalone OOWP term would be
   redundant.
5. **Naming follow-ups instead of pretending closure** — "Watch through end
   of season, decide for 2027 with evidence" is the right epistemic
   posture.
6. **Trace the bug to the line, not the symptom** — the Massey-rank-by-
   school-id story is a textbook case of asking *what does the failing path
   actually do?* instead of just patching what the user saw.
7. **Surface constraints up front** — every AAR leads with what the
   stakeholder won't accept, then designs against that.
8. **Articulate non-goals deliberately** — what isn't changing is as
   important as what is.
9. **Validate with multiple independent angles** — correlation, distribution
   sanity, eye-test, expected-ordering spot-checks. No single number decides.
10. **Single mutation seam for system-wide swaps** — push the change to one
    line whose effect is broad, instead of changing many call sites.

---

## File-by-file evidence index

### `generate_site.py` (4672 lines, single-file static-site generator)
- Lines 24–106: Constants block — flight weights, RPI weights, TOSS
  weights, Bayes priors, gate dates, QWS hyperparameters. Every value
  commented with rationale.
- Lines 109–127: Date-gated feature flags as pure helpers.
- Lines 336–398: `is_dual_match` (structural, not title-only) and
  `dedupe_meets` (date + sorted-pair key, max-flights tiebreaker).
- Lines 401–444: `get_meet_result` — tri-state with `winnerSchoolId`
  fallback.
- Lines 731–913: `calculate_fws_per_match` — proportional weighting,
  set-type-aware game accounting, super-TB detection.
- Lines 916–1244: `build_rankings` — Pass 1 (RPI), Pass 2 (LOO league
  depth), Pass 3 (TOSS), Pass 4 (QWS), promotion seam.
- Lines 1245–1505: Output assembly with NR-partition; H2H Phases 1–3 with
  cycle guard.
- Lines 1935+: `generate_html` — inline template-literal HTML/CSS/JS with
  embedded JSON.

### `scripts/computer_rankings.py` (237 lines)
- `elo_rankings` (`:22`) — log-margin damping, tri-state outcomes.
- `colley_rankings` (`:51`) — `(2I + C)r = 1 + ½(w − l)`.
- `massey_rankings` (`:87`) — sum-to-zero constraint, `lstsq` for
  disconnected graphs.
- `pagerank_rankings` (`:122`) — power iteration, damping, column
  normalization, tie-split symmetry.
- `win_score_rankings` (`:166`) — sum of beaten-opponents' WP.
- `composite_ranks` (`:214`) — average + median + std.

### `scripts/generate_weekly_rankings.py` (925 lines)
- `:38–134` — cadence helpers (`first_saturday`, `get_week_publish_date`
  with rollforward, `get_prior_publish_date` bridging the transition,
  `all_week_publish_dates`).
- `:101–115` — `load_published_week` for canonical prior-week inputs.
- `:287–357` — `extract_matches`: tri-state `won`, dedup-aware `seen` set,
  match log for quality-win tracking.
- `:380–399` — `compute_quality_wins`: top-25 overall OR top-10 in class,
  no double-counting.
- `:402–472` — `build_weekly_rankings` with deterministic tiebreaker
  chain.
- `:489+` — `generate_narrative` — positive-only narrative generation
  (top-10 spotlight, undefeated, risers, quality-win leaders).

### `scripts/build_rankings.py` (365 lines)
- Slimmer JSON-only variant of the pipeline; same dedup, same
  proportional-weighting FWS, two-pass APR.

### `src/` (TypeScript React frontend)
- `dataFetcher.ts` — GitHub raw + contents API as data layer; no auth,
  no backend.
- `rankingCalculator.ts` — APR re-implementation in TypeScript for
  client-side rendering.
- `App.tsx` — year/classification filters; `useEffect` chained on year
  change to refetch.
- `types.ts` — typed domain model.

### `docs/`
- `oFWS-PRD.md` — formal portable spec (Version 1.0, Status: Implemented).
- `power-index-explained.md` — coach-facing methodology.
- `OSAA-Executive-Summary.md`, `OSAA-One-Pager.md` — stakeholder briefs.
- `proposed-special-districts.md`, `regional-bracket-analysis.md`,
  `team-championship-proposal-v2.md` — policy proposals with comparative
  tables and precedent citations.

### Top-level documents
- `AAR-power-index-ab-test.md` — full A/B test design and decision.
- `AAR-toss-ogs-fold-in.md` — three-component fold-in with calibration
  table.
- `memo_team_format_roster_analysis.md` — OSAA committee memo.
- `CHANGELOG.md` — Problem → Root cause → Fix → Impact entries with
  magnitudes.

---

## Resume-ready phrasings

Each is anchored to specific evidence in the repo. Use as-is or trim.

- *Designed and shipped a multi-model sports-rating system for Oregon HS
  tennis (RPI, opponent-weighted Flight Quality Index, opponent-weighted
  Game Share, ITA-style iterated Quality-Weighted Wins), running variant
  formulas as a forward-only A/B test on live data and selecting the
  primary on stated criteria (constraint fit, defensibility, eye-test
  agreement).*

- *Authored a portable Product Requirements Document (`oFWS PRD v1.0`) for
  an opponent-weighted flight-rating metric, generalizing the Oregon
  implementation so other states or racquet sports (badminton, squash) can
  adopt the same approach.*

- *Diagnosed a silent ranking failure in a Massey/Laplacian solver caused
  by a disconnected match graph; replaced `np.linalg.solve` with
  `np.linalg.lstsq` to obtain minimum-norm solutions per connected
  component, restoring correct ratings for hundreds of teams.*

- *Applied empirical-Bayes shrinkage and minimum-sample thresholds to
  stabilize season-opening rankings, eliminating a class of small-sample
  distortions that head-to-head tiebreakers had been masking.*

- *Implemented a three-phase head-to-head tiebreaker resolver
  (in-league → adjacent-pair → classification-level) with explicit
  cycle-detection to prevent intransitive swap chains.*

- *Encoded set-type-aware game accounting (best-of-3 sets, 8-game pro
  sets, 7-point set tiebreakers, 10-point match tiebreakers) so a single
  super-tiebreaker decision doesn't dominate season-long game-share
  statistics 17× over a regular game.*

- *Ran a Saturday→Sunday weekly publishing cadence migration with
  continuous week numbering, mid-week rollforward semantics, and
  byte-identical historical artifacts — backed by an explicit
  `ADJ_MODELS_ENABLED=0` invariance test.*

- *Wrote decision-grade After-Action Reports (problem → options
  considered → what shipped → validation → non-goals → follow-ups) used
  by a non-technical site owner to evaluate live formula changes
  mid-season.*

- *Authored a data-driven policy memo to the OSAA State Championship
  Committee on roster-size feasibility for a team dual-match format,
  sourced from a season-long match-level dataset I built and maintain.*

- *Built a five-system computer-ranking pipeline (Elo, Colley, Massey,
  PageRank, Win-Score) producing a composite rank with median and
  standard-deviation diagnostics, plus an automated weekly narrative
  generator.*

- *Modeled tri-state match outcomes (`win | loss | tie`) end-to-end across
  five ranking algorithms, distinguishing tiebreaker-decided results from
  true draws and propagating the distinction through Elo updates,
  Colley's right-hand side, PageRank authority distribution, and
  Win-Score credit assignment.*

---

## Learning goals to write toward next

Things you've already touched empirically and could now formalize:

1. **Sports-rating literature**. RPI, Massey, Colley, Elo, ITA QW,
   Bradley-Terry, paired-comparison models. There's a clean, finite
   reading list at the intersection of "things you've already implemented"
   and "things with formal underpinnings." Worth doing for the publishable
   PRD-style writing it would unlock.

2. **Predictive evaluation of ranking changes**. Move from rank-correlation
   + spot checks to: does TOSS predict playoff outcomes better than Legacy?
   Out-of-sample log-loss, Brier score, calibration curves on prior
   seasons. Turns "the eye test approves" into "we measured it."

3. **Causal language for non-causal interventions**. The 2026 promotion of
   TOSS isn't a randomized experiment — it's a regime change. Reading
   around quasi-experimental design (interrupted time series, regression
   discontinuity) would let you talk about formula promotions in terms
   that statisticians recognize.

4. **Production-grade Python data engineering**. Replacing the 4672-line
   single-file generator with: a `pipeline/` package, Jinja2 templates,
   pytest unit tests on the pure helpers, type-checked dataclasses for
   the per-team record. Each is a discrete, finishable exercise.

5. **Frontend modernization**. The Python-generated `index.html` is fine
   for the static use case, but the React app already exists. Reconciling
   them — making the React app consume `processed_rankings.json` directly
   and become the canonical UI — would eliminate a class of HTML-string
   escaping bugs.

6. **Geographic/operations research**. The regional bracket analysis is
   already a real operations-research exercise (minimize travel under
   bracket constraints). Formalizing it (TSP-flavored, MIP, or a heuristic
   with an optimality gap) is a portfolio-quality piece on its own.

---

## What you could plausibly improve

These are honest gaps the codebase suggests, not knocks:

- **Tests.** The pure-function helpers (`dedupe_meets`, `get_meet_result`,
  `calculate_fws_per_match`, `_toss_is_primary`, the five computer-ranking
  algorithms) are perfect unit-test targets. Right now correctness is
  verified by changelog spot-checks and visual diff on the rendered site.
  A pytest suite would let you change the math with confidence.
- **Single-file size.** `generate_site.py` is 4672 lines, ~half of which
  is an HTML template literal. Splitting into `pipeline/`, `templates/`,
  and `cli/` is a real refactor with real value.
- **Templating.** The HTML is f-string interpolation of escaped JS. A
  migration to Jinja2 (or even just a templates folder) would eliminate
  a class of escaping bugs and make UI changes reviewable.
- **Incremental generation.** The pipeline recomputes top-to-bottom every
  run. As the dataset grows, an incremental mode (only recompute affected
  `(year, gender)` partitions) is a standard data-engineering exercise
  with a clear win.
- **Configuration externalization.** Every constant is in `generate_site.py`.
  As the model count grows, a `rankings.toml` (or a small dataclass) lets
  you spin up an alternate model without touching the pipeline file.
- **TS/Python parity.** The APR formula is implemented in two languages
  (`src/rankingCalculator.ts:79` and `generate_site.py`). Right now
  correctness is enforced by you. A canonical artifact (the JSON) plus
  one renderer would close the drift risk.

---

*Compiled across one conversation. Every claim above traces to a specific
file and (where useful) line number in this repository. The intent is that
each numbered or bulleted item is independently citable in a resume bullet,
a portfolio writeup, a learning plan, or a self-evaluation.*
