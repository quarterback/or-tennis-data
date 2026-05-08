# 04 — Live Experimentation Discipline (A/B on Real Data)

**One-line:** Ran three rating models in parallel on live production data
for a season, then promoted one based on stated criteria — not vibes.

---

## What you did

Starting 2026-04-20, every team in `processed_rankings.json` carried
fields for **three** Power Index variants computed in parallel:

- `power_index`, `apr`, `normalized_fws` — Current (RPI baseline)
- `power_index_toss`, `adjusted_fws`, `schedule_multiplier` — TOSS
- `power_index_qws`, `apr_qws`, `qws_iterations` — QWS

A "Model" dropdown in the UI swapped the State/Class Rank/PI columns
between models. Default was Current; switching to TOSS or QWS re-sorted
the table by that model's rank and tagged the PI cell with
`[TOSS]`/`[QWS]`.

On 2026-04-26 (one week of live data later), TOSS was promoted to
primary. Legacy stayed in the dropdown for comparison; QWS continued as
the experimental B.

## Single mutation seam for promotion

`generate_site.py:1241–1242`:

```python
school['power_index_legacy'] = school['power_index']
school['power_index'] = school.get('power_index_toss', school['power_index'])
```

Everything downstream — sort, league rank, H2H, playoff sim, class rank
— reads `school['power_index']`. Promoting TOSS is one assignment in one
place. **That's the architectural payoff for treating model promotion as
a data swap, not a code rewrite.**

## Independent rank maps per model

`generate_site.py:1273–1301`: each alt model gets its own pre-computed
`rank_toss_map`, `rank_qws_map`, `rank_legacy_map` so the frontend
dropdown can re-display ranks without re-running a pipeline.

## Decision criteria stated explicitly

From `AAR-power-index-ab-test.md`, "Why TOSS (not QWS) as primary":

1. **Honors the "don't penalize scheduling up" constraint more cleanly.**
   QWS's flat 50-point loss penalty doesn't differentiate a 3-5 loss to
   #1 from a 0-8 blowout by the cellar — both cost 50.
2. **Smaller, more defensible change.** TOSS keeps OSAA-compatible RPI
   APR intact and only adjusts how flight scores count. Explainable in
   one sentence to coaches.
3. **Fixes the obvious cases either way.** The biggest distortions
   (Ridgeview #16→62, Sam Barlow #32→66, The Dalles #11→42) corrected
   under both models.

QWS wasn't dismissed — it was named as a 2027 candidate with a tuned
loss penalty (`100 × (1 - opp_PI)` so losing to #1 costs ~20 vs losing
to the cellar costing ~100).

## Calibration as a real exercise

From `AAR-toss-ogs-fold-in.md`:

| Split | APR | FQI | oGS | Effect |
|---|---|---|---|---|
| Mild | 0.45 | 0.45 | 0.10 | Directional but soft |
| **Moderate** | **0.40** | **0.40** | **0.20** | Sweet spot |
| Aggressive | 0.35 | 0.35 | 0.30 | Began diluting FQI's anti-stacking |

Three weight splits dry-run side by side before picking 40/40/20. Then,
after a week of live data, rebalanced again to 65/25/10 when the
40/40/20 split allowed an 8-5-2 flight-dominant team to outrank an 8-2
team with stronger record.

## Resume bullets specific to this skill

- *Ran three rating-system variants in parallel as a forward-only A/B
  test on live production data, then promoted the primary on stated
  criteria (constraint fit, defensibility, eye-test agreement) backed by
  one week of side-by-side data.*
- *Architected the model-promotion seam so flipping the primary rating
  model was a single field overwrite at one call site, with all
  downstream consumers (sort, league ranks, H2H tiebreakers, playoff
  simulator) picking up the change automatically.*
- *Calibrated multi-component rating weights through dry-run side-by-side
  comparison of mild/moderate/aggressive splits before committing,
  rebalanced again after one week of live data when the eye-test surfaced
  a residual distortion.*

## Where to grow

- Predictive evaluation: did TOSS forecast playoff outcomes better than
  Legacy? Out-of-sample log-loss on 2024–2025.
- Feature flagging / experiment platforms (Statsig, GrowthBook, even
  homegrown). The date-gate approach you used is fine for one experiment
  but doesn't scale to running many overlapping ones.
- Quasi-experimental causal language (interrupted time series) for talking
  about formula promotions to a statistical audience.
