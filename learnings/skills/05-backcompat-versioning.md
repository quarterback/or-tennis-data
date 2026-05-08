# 05 — Backwards-Compatibility & Versioning Rigor

**One-line:** Forward-only changes with byte-identical historical artifacts,
date-gated feature flags, and field/function aliases for in-flight
renames.

---

## Date-gated feature flags as pure helpers

`generate_site.py:109–127`:

```python
def _adjusted_models_enabled(today=None):
    override = os.environ.get('ADJ_MODELS_ENABLED')
    if override in ('0', '1'):
        return override == '1'
    return (today or date.today()) >= ADJUSTED_FWS_EFFECTIVE_DATE


def _toss_is_primary(today=None):
    if not _adjusted_models_enabled(today):
        return False
    override = os.environ.get('TOSS_PRIMARY')
    if override in ('0', '1'):
        return override == '1'
    return (today or date.today()) >= TOSS_PRIMARY_DATE
```

Three things to notice:

1. **Pure functions** — no state, no class, just date math.
2. **`today` parameter** — trivially testable (`_toss_is_primary(date(2026, 4, 25))`).
3. **Env-var overrides** for forcing a state without touching the clock.

## Forward-only changes verified by invariance test

From `AAR-power-index-ab-test.md`, "Baseline invariance":

> `ADJ_MODELS_ENABLED=0 python generate_site.py` produces a
> `processed_rankings.json` byte-identical to the pre-change `main`
> branch. The new models are entirely additive when the gate is off.

That's the right kind of test for this scenario — not "do the new fields
look reasonable" but "is the artifact identical when the gate is off."

## Backwards-compat field aliases

JSON consumers don't break on rename:

- `normalized_fws` retained alongside `fqi` (`generate_site.py:1135`).
- `fws_plus` retained alongside `fqi_plus`.
- `adjusted_fws = fqi  # Backcompat alias` (`:1161`).
- `normalized_fws_raw` preserved as the opponent-blind baseline for
  debugging.

## Backwards-compat function aliases

`scripts/generate_weekly_rankings.py:75–76, 137–138`:

```python
get_week_saturday = get_week_publish_date
all_week_saturdays = all_week_publish_dates
```

Older callers using the Saturday-only names keep working through the
cadence transition.

## Forward-only at the season level

- Historical seasons (2021–2025) keep only baseline fields. No
  `power_index_toss`/`power_index_qws` keys at all on those entries.
- The three pre-cadence-shift Saturday weekly snapshots (2026-04-04, 11,
  18) are byte-identical to before the change.
- 2021–2025 still use the original 50/50 APR + FWS Power Index. Only the
  2026 season gets the new formulas.
- Stated as a non-goal in every AAR: *"We are not recomputing 2021-2025.
  Historical rankings are historical artifacts."*

## Cadence transition rollforward

`scripts/generate_weekly_rankings.py:60–65`: between Apr 19 and Apr 25
inclusive, no-arg invocation rolls *forward* to Apr 26 (the first Sunday
publish) instead of overwriting the last Saturday snapshot. Edge case
that most people only spot in retrospect.

## Resume bullets specific to this skill

- *Ran a Saturday→Sunday weekly publishing cadence migration with
  continuous week numbering, mid-week rollforward semantics, and
  byte-identical historical artifacts — backed by an explicit
  `ADJ_MODELS_ENABLED=0` invariance test.*
- *Designed a date-gated feature-flag system with env-var overrides for
  testing, allowing forward-only rollout of a new ranking formula while
  keeping the artifact byte-identical when the gate was off.*

## Where to grow

- A small JSON schema registry / changelog so external consumers can
  pin to a schema version. Right now there's no formal contract.
- Property-based tests (Hypothesis) for the gate functions: *for any
  date before the gate, every output should match the prior `main`
  branch's artifact for that date.*
