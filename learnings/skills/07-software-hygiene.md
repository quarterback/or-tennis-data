# 07 — Software Engineering Hygiene

**One-line:** Constants as dependency map, comments that earn their keep,
pure-function helpers, deterministic tiebreakers, and explicit phase
naming for multi-step logic.

---

## Constants as a dependency map

`generate_site.py:24–106`. Every weight, prior, gate, and threshold has
a name and a comment explaining *why* it's that value. A few examples:

```python
TOSS_APR_WEIGHT = 0.65  # Dual match outcomes (RPI-style) — primary signal
TOSS_FQI_WEIGHT = 0.25  # Flight Quality Index (opp-APR-weighted FWS)
TOSS_OGS_WEIGHT = 0.10  # Opp-weighted game share (set/game-level dominance)

TOSS_PRIOR_MATCHES = 5
TOSS_PRIOR_VALUE = 0.5

MIN_RANKED_MATCHES = 3
LEAGUE_DEPTH_TOP_N = 4
H2H_THRESHOLD = 0.02
H2H_LEAGUE_RANK_THRESHOLD = 2
```

Rolling the formula back is editing constants, not chasing call sites
— exactly what the AAR's "Rollback" section claims:

```
TOSS_APR_WEIGHT = 0.50
TOSS_FQI_WEIGHT = 0.50
TOSS_OGS_WEIGHT = 0.0
```

## Comments earn their keep

The rule on display: comments explain the *why* and the invariants, not
the *what*. Example at `generate_site.py:1234–1238`:

> "Promote TOSS to primary for 2026+: everything downstream … reads
> `school['power_index']`, so overwriting it swaps the whole system onto
> TOSS in one place."

That comment tells you the *invariant* you'd otherwise have to reverse-
engineer. Try removing it and asking whether someone reading the code
cold could guess.

## Pure-function helpers

Every one of these is a unit-test target with no global state:

- `dedupe_meets(meets)` — input list, output list.
- `get_meet_result(meet, school_id)` — `'win' | 'loss' | 'tie'`.
- `_adjusted_models_enabled(today=None)` — bool.
- `_toss_is_primary(today=None)` — bool.
- `composite_ranks(all_ranks, team_ids)` — dict.
- The five `*_rankings()` functions in `computer_rankings.py`.

## Defensive recovery patterns

- **Opponent-id fallback scan** when the first pass missed
  (`generate_site.py:832–836`).
- **Dict-key polymorphism** for upstream JSON sometimes serializing
  team ids as strings, sometimes as ints
  (`generate_site.py:851`):
  ```python
  mg = s.get(str(my_tid)) if s.get(str(my_tid)) is not None else s.get(my_tid)
  ```
- **Deterministic tiebreakers everywhere** so re-runs are reproducible:
  - Dedup: `(flight_count, -meet_id)` tuple comparison.
  - Composite-rank tiebreak: composite → median (asc, more consistent
    placement wins) → main-site PI (desc) → school_id
    (`scripts/generate_weekly_rankings.py:464–469`).

## Explicit phase naming for multi-step logic

The H2H tiebreaker has three named phases (`generate_site.py:1318–1505`):

- **PHASE 1: In-League H2H enforcement** — same-league teams within
  threshold league-rank distance.
- **PHASE 2: Standard adjacent-pair swap** — statewide PI threshold.
- **PHASE 3: Classification-level H2H enforcement** — same-class teams
  not adjacent in state ranking.

Plus a `would_create_circle()` cycle guard. Naming the phases is what
makes the code reviewable — without the names this would be a 200-line
nested loop with no handles.

## Idempotent generation

`main()` runs end-to-end and produces the same artifact for the same
inputs. No incremental state to reconcile; no migration path to
maintain. The cost is regeneration time; the benefit is "the build is
the test."

## Resume bullets specific to this skill

- *Modeled ~20 ranking-system parameters as named constants with inline
  rationale, enabling formula rollback through a constants edit rather
  than call-site changes.*
- *Designed multi-phase tiebreaker logic with explicit phase naming,
  cycle detection, and deterministic ordering, producing reproducible
  rankings even on tied composite scores.*

## Where to grow

- A pytest suite on the pure helpers — currently zero.
- Type hints on the data-flow functions (`build_rankings`,
  `build_weekly_rankings`). They're large enough to benefit, simple
  enough that `mypy --strict` would land cleanly.
- Dataclasses (or pydantic) for the per-team record. Right now it's a
  dict, which means every field access is a string lookup.
