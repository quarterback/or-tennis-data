# 02 — Statistical Reasoning Under Uncertainty

**One-line:** Applied empirical-Bayes shrinkage, minimum-sample thresholds,
and multi-angle validation (correlation, distribution sanity, eye test)
instead of trusting raw averages.

---

## Evidence

### Empirical-Bayes shrinkage as five phantom matches

`generate_site.py:1155–1158`:

```python
fqi = (total + TOSS_PRIOR_MATCHES * TOSS_PRIOR_VALUE) / (len(records) + TOSS_PRIOR_MATCHES)
```

`TOSS_PRIOR_MATCHES = 5` and `TOSS_PRIOR_VALUE = 0.5`. A team with `N`
real matches gets pulled `5 / (N + 5)` of the way toward the league
baseline: a 5-match team is shrunk 50%, a 13-match team 28%, a full
season 25%.

You also recognized that **APR is already shrunk via the OWP/OOWP graph**
and explicitly chose not to double-shrink it (comment at
`generate_site.py:55–61`). That's a non-obvious move — most people apply
the same regularization to every metric.

### Minimum-sample thresholds

- `MIN_RANKED_MATCHES = 3` in `generate_site.py:65–70`. Below threshold,
  teams emit `null` rank and render as `NR`. Numeric metrics still
  compute, so a team reappears with a rank as soon as match #3 is played.
- Mirrored at `scripts/generate_weekly_rankings.py:26` (`MIN_MATCHES = 3`).

### Validation through multiple angles

From `AAR-power-index-ab-test.md`:

- **Spearman rank correlation**, 2026 Boys: Current↔TOSS 0.97,
  Current↔QWS 0.95, TOSS↔QWS 0.98.
- **Distribution sanity**: TOSS schedule multiplier min 0.82, median
  0.95, max 1.06.
- **Convergence sanity**: QWS iterations min 3, max 3, mean 3.0 across
  1,472 team-year records.
- **Spot checks**: top-of-table (Lincoln, Jesuit, Grant, OES, Catlin
  Gabel) verified to remain near the top across all three models.
- **Pearson correlation** between old and new primary PI (~0.96) used to
  size the impact of the oGS fold-in.

## The reported case

The bug that drove the empirical-Bayes change wasn't theoretical — a 4-1
team was ranking just ahead of a 10-3 league rival on raw PI even though
the 10-3 team had won the head-to-head. The H2H swap rescued the state
rank, but the underlying number was the wrong way around. Shrinkage
fixed the number, not just the symptom.

## Resume bullets specific to this skill

- *Applied empirical-Bayes shrinkage and minimum-sample thresholds to
  stabilize season-opening rankings, eliminating a class of small-sample
  distortions that head-to-head tiebreakers had been masking.*
- *Validated ranking changes across multiple angles — Spearman/Pearson
  correlation, distribution sanity, expected-ordering spot checks — so no
  single metric drove formula promotions.*

## Where to grow

- Predictive validation: Brier score, log-loss, calibration on out-of-
  sample playoff outcomes.
- Quasi-experimental framing: interrupted time series, regression
  discontinuity for talking about formula promotions in causal language.
- Bayesian rating models proper (Glicko, TrueSkill) — the natural
  extension of "shrinkage that knows how much you've seen."
