# 08 — Data Pipeline & Cadence Engineering

**One-line:** Continuous week numbering through a Saturday→Sunday cadence
shift, published artifacts as canonical truth, and three CLI modes with
explicit semantics.

---

## The cadence shift

Weeks 1–3 of the 2026 season shipped on Saturdays (Apr 4, 11, 18).
Starting week 4, weekly snapshots publish on Sundays so Saturday match
results land in that week's file.

The challenge: don't break week numbering, don't double-publish during
the transition, and let mid-week invocations do the right thing.

## Continuous week numbering across the transition

`scripts/generate_weekly_rankings.py:79–86`:

```python
def get_week_num(publish_date):
    pd = ...
    if pd <= SATURDAY_LAST_PUBLISH:
        return max(1, ((pd - first_saturday()).days // 7) + 1)
    sat_weeks = ((SATURDAY_LAST_PUBLISH - first_saturday()).days // 7) + 1
    sunday_offset = (pd - SUNDAY_FIRST_PUBLISH).days // 7
    return sat_weeks + 1 + sunday_offset
```

| Date | Day | Week # |
|---|---|---|
| 2026-04-04 | Sat | 1 |
| 2026-04-11 | Sat | 2 |
| 2026-04-18 | Sat | 3 |
| 2026-04-26 | Sun | 4 |
| 2026-05-03 | Sun | 5 |

No off-by-one across the boundary.

## Mid-week rollforward

`scripts/generate_weekly_rankings.py:60–65`:

```python
# In-window rollforward: between Apr 19 and Apr 25 inclusive, default
# to Apr 26 (the first Sunday cadence publish).
if SATURDAY_LAST_PUBLISH < dt < SUNDAY_FIRST_PUBLISH:
    return SUNDAY_FIRST_PUBLISH
```

A no-arg invocation between Apr 19 and Apr 25 produces the *upcoming*
Sunday's snapshot, not a stale Saturday overwrite. This is the kind of
edge case most people only spot in retrospect — you got it on the way in.

## Prior-publish-date helper bridges the transition

`scripts/generate_weekly_rankings.py:89–98`:

```python
def get_prior_publish_date(publish_date):
    pd = ...
    if pd == SUNDAY_FIRST_PUBLISH:
        return SATURDAY_LAST_PUBLISH
    return pd - timedelta(days=7)
```

Without that special case, Sunday week 4 would look back to Apr 19 (the
day after Saturday week 3) and find no snapshot. With it, Sunday week 4
correctly looks at Saturday week 3.

## Published artifacts as canonical truth

`scripts/generate_weekly_rankings.py:101–115`:

```python
def load_published_week(project_root, week_date):
    """Published weekly rankings are the canonical source of prior-week
    ranks for quality-win calculations — using them keeps historical
    quality-win totals stable even as raw match data evolves."""
    path = os.path.join(project_root, 'public', 'data', 'weekly',
                        f"{week_date.strftime('%Y-%m-%d')}.json")
    if not os.path.exists(path):
        return None, None
    with open(path) as f:
        data = json.load(f)
    return data.get('boys', []), data.get('girls', [])
```

This is the right architectural move. Quality wins were drifting
because every run recomputed prior weeks from evolving raw data. The
fix is to pin the inputs: yesterday's published JSON is the source of
truth for today's quality-win calculation.

## Three CLI modes with explicit semantics

```
python scripts/generate_weekly_rankings.py                  # current week only
python scripts/generate_weekly_rankings.py --all            # all weeks through today
python scripts/generate_weekly_rankings.py --week 2026-04-04  # specific week
```

- Current-week: useful for the cron run.
- `--all`: chains in memory because each freshly-written snapshot
  matches what would be read back from disk.
- `--week`: loads priors from disk via `load_published_week`. Single-
  week reruns and partial reruns just work.

## Composite-rank tiebreaker chain

`scripts/generate_weekly_rankings.py:464–469`:

```python
results.sort(key=lambda x: (
    x['composite_rank'],
    x['median_rank'],       # ascending — more consistent placement wins
    -x['power_index'],      # descending
    x['school_id'],         # deterministic fallback
))
```

Four-key sort with each key chosen for a reason. The comment naming
why `median_rank` ascending wins ("more consistent placement wins") is
the kind of comment that would save someone six months from now.

## Resume bullets specific to this skill

- *Designed a Saturday→Sunday weekly publishing cadence migration with
  continuous week numbering, mid-week rollforward semantics that produced
  the upcoming Sunday's snapshot rather than overwriting the prior
  Saturday, and explicit prior-week bridging across the boundary.*
- *Established published JSON artifacts as the canonical source of
  prior-week ranks for downstream calculations, eliminating a class of
  drift bugs caused by recomputing historical inputs from evolving raw
  data.*

## Where to grow

- Cron / scheduled GitHub Actions for the publish pipeline (probably
  already there — git log shows updates every ~4 hours).
- Schema versioning on the published JSON artifact so future shape
  changes can be detected by readers.
- Incremental generation: only recompute affected `(year, gender)`
  partitions. Right now everything regenerates.
