# Resume Bullets

Standalone, copy-pasteable bullets organized by likely target role. Every
bullet is anchored to evidence in the codebase or design docs — see
[`skills/`](skills/) for the source.

Use these as starting points: trim, combine, or rewrite for the role.
The first version of each is the long form; many include a short form
underneath.

---

## For data-engineering / data-platform roles

- *Designed and operate a multi-model sports-rating pipeline ingesting
  match-level data for 264 schools across six seasons, applying load-
  time deduplication (51 duplicate pairs across 92 files), tri-state
  result modeling, and proportional-weighting normalization for
  forfeits and short matches.*
  - Short form: *Designed and operate a multi-year, multi-model
    sports-rating pipeline serving 264 schools across six seasons.*

- *Established published JSON artifacts as the canonical source of
  prior-week ranks for downstream calculations, eliminating a class of
  drift bugs caused by recomputing historical inputs from evolving raw
  data.*

- *Diagnosed and fixed six distinct data-quality bugs in the pipeline,
  each traced to the specific line where the wrong value was set, with
  magnitude reporting (e.g., 466 teams across 139 groups) in the
  changelog.*

- *Authored a load-time deduplication pass with deterministic
  tiebreakers (max flight count, then lowest meet ID) that consolidated
  duplicate dual-match entries across every downstream consumer
  (records, league standings, head-to-head, RPI, flight-weighted score).*

- *Designed a Saturday→Sunday weekly publishing cadence migration with
  continuous week numbering, mid-week rollforward semantics, and
  byte-identical historical artifacts — backed by an explicit
  invariance test.*

---

## For applied / sports-analytics roles

- *Designed and shipped a multi-model sports-rating system (RPI,
  opponent-weighted Flight Quality Index, opponent-weighted Game
  Share, ITA-style iterated Quality-Weighted Wins) operating as a
  forward-only A/B test on live data, with primary-model selection
  based on stated criteria (constraint fit, defensibility, eye-test
  agreement).*

- *Authored a portable Product Requirements Document (`oFWS PRD v1.0`)
  generalizing an opponent-weighted flight-rating metric so other
  states or racquet sports (badminton, squash) can adopt the same
  approach without reading the Oregon implementation.*

- *Built a five-system computer-ranking pipeline (Elo, Colley, Massey,
  PageRank, Win-Score) producing a composite rank with median and
  standard-deviation diagnostics, plus an automated weekly narrative
  generator.*

- *Applied empirical-Bayes shrinkage and minimum-sample thresholds to
  stabilize season-opening rankings, eliminating small-sample
  distortions that head-to-head tiebreakers had been masking.*

- *Diagnosed a silent ranking failure in a Massey/Laplacian solver
  caused by a disconnected match graph; replaced `np.linalg.solve` with
  `np.linalg.lstsq` to obtain minimum-norm solutions per connected
  component, restoring correct ratings for hundreds of teams.*

- *Modeled tri-state match outcomes (`win | loss | tie`) end-to-end
  across five ranking algorithms, distinguishing tiebreaker-decided
  results from true draws and propagating the distinction through Elo
  updates, Colley's right-hand side, PageRank authority distribution,
  and Win-Score credit assignment.*

- *Encoded set-type-aware game accounting (best-of-3, 8-game pro sets,
  7-point set tiebreakers, 10-point match tiebreakers) so a single
  super-tiebreaker decision doesn't dominate season-long game-share
  statistics 17× over a regular game.*

---

## For software-engineering / generalist roles

- *Architected the model-promotion seam in a multi-model rating system
  so flipping the primary rating model was a single field overwrite at
  one call site, with all downstream consumers (sort, league ranks,
  head-to-head tiebreakers, playoff simulator) picking up the change
  automatically.*

- *Modeled ~20 ranking-system parameters as named constants with inline
  rationale, enabling formula rollback through a constants edit rather
  than call-site changes.*

- *Designed multi-phase tiebreaker logic (in-league, adjacent-pair,
  classification-level) with explicit phase naming, cycle detection,
  and deterministic ordering, producing reproducible rankings even on
  tied composite scores.*

- *Implemented iterative fixed-point computations with explicit
  convergence guards for an ITA-style quality-weighted rating system,
  reaching stable solutions in ~3 iterations on production data.*

- *Built a TypeScript/React frontend (`Vite` + DataTables) consuming a
  versioned JSON artifact published by a Python pipeline, with
  cross-language verification of the rating formula in both
  implementations.*

- *Designed a date-gated feature-flag system with env-var overrides for
  testing, allowing forward-only rollout of a new ranking formula while
  keeping the artifact byte-identical when the gate was off.*

---

## For product / technical-writing / staff-engineering roles

- *Authored decision-grade After-Action Reports following a repeatable
  structure (problem → options considered → what shipped → validation
  → non-goals → follow-ups), used as the basis for live mid-season
  formula promotions.*

- *Surfaced stakeholder constraints up front in design documents
  ("don't back-date," "no class-aware multiplier," "preserve OSAA
  compatibility") and explicitly designed within them, treating
  political legitimacy as a first-class engineering concern alongside
  technical correctness.*

- *Named explainability as a deciding factor between competing rating
  formulas, choosing the smaller defensible change over the
  structurally cleaner one when the latter could not be justified to
  coaches mid-season.*

- *Drafted a data-backed policy memo to the OSAA State Championship
  Committee that named a specific accommodation ("default/forfeit
  provisions for unfilled flights") rather than only refuting the
  underlying roster-size concern.*

- *Maintained a changelog of structured incident records (problem →
  root cause → fix → impact with magnitudes), serving as the running
  decision history of the rating system.*

- *Calibrated multi-component rating weights through dry-run side-by-
  side comparison of mild/moderate/aggressive splits before
  committing, then rebalanced again after one week of live data when
  the eye-test surfaced a residual distortion.*

---

## Bullet-by-skill quick index

| Bullet's home skill | File |
|---|---|
| Rating system design | [`skills/01-rating-system-design.md`](skills/01-rating-system-design.md) |
| Statistical reasoning | [`skills/02-statistical-reasoning.md`](skills/02-statistical-reasoning.md) |
| Numerical methods | [`skills/03-numerical-methods.md`](skills/03-numerical-methods.md) |
| Live experimentation | [`skills/04-live-experimentation.md`](skills/04-live-experimentation.md) |
| Backwards-compatibility | [`skills/05-backcompat-versioning.md`](skills/05-backcompat-versioning.md) |
| Data quality | [`skills/06-data-quality.md`](skills/06-data-quality.md) |
| Software hygiene | [`skills/07-software-hygiene.md`](skills/07-software-hygiene.md) |
| Pipeline / cadence | [`skills/08-pipeline-cadence.md`](skills/08-pipeline-cadence.md) |
| Frontend / full-stack | [`skills/09-frontend-fullstack.md`](skills/09-frontend-fullstack.md) |
| Domain modeling | [`skills/10-domain-modeling.md`](skills/10-domain-modeling.md) |
| Stakeholder management | [`skills/11-stakeholder-management.md`](skills/11-stakeholder-management.md) |
| Technical writing | [`skills/12-technical-writing.md`](skills/12-technical-writing.md) |

---

## Project-summary lines (for the top of a resume entry)

Pick one based on space.

**Long:**
> Solo project. Designed and operate a multi-model power-index ranking
> system for Oregon high school tennis (`oregontennis.org`). Multi-pass
> rating pipeline, opponent-weighted flight metrics, five computer-
> ranking algorithms, A/B-tested formulas on live data, weekly
> publishing cadence, React + Python static-site stack. Authored a
> portable PRD for the rating method and a policy memo to the OSAA
> State Championship Committee.

**Medium:**
> Designed and operate a multi-model power-index ranking system for
> Oregon high school tennis: multi-pass pipeline, opponent-weighted
> flight metrics, five computer-ranking algorithms, A/B-tested formulas
> on live data, React + Python stack. Authored portable PRD and OSAA
> committee policy memo.

**Short:**
> Built and operate a multi-model sports-rating system with portable
> spec, published as `oregontennis.org`.
