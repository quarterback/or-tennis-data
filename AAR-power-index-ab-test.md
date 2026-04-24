# After Action Report: Power Index A/B Test

**Date:** 2026-04-24
**Effective:** 2026-04-20 forward
**Branch:** `claude/fix-ranking-league-balance-HdQrV`
**Author:** Engineering, after multi-round design review with site owner and a designer-supplied alternative spec.

## What we did

Starting with the Saturday-2026-04-25 publish window, the rankings system computes **three** Power Index variants in parallel and surfaces all of them on the main rankings page via a Model dropdown (Current / TOSS / QWS). The Current model is the default and continues to drive all downstream UI (playoff simulator, head-to-head, league standings). TOSS and QWS are visible for live A/B comparison through end of the 2026 season.

The weekly publish cadence also shifts from Saturdays to Sundays starting **2026-04-26** so that Saturday match results are included in that week's snapshot.

## Why we did it

The site owner's read of the season-to-date rankings: the Power Index was over-rewarding teams that ran up dominant flight scores against weak-league opponents. Specifically, the Flight-Weighted Score (FWS) — half of the Power Index — is computed without any reference to opponent strength, so an 8-0 sweep of a cellar team contributes the same as an 8-0 sweep of a state contender. Teams in genuinely competitive leagues, who can win 5-3 matches but rarely 8-0, were being penalized in the depth half of the formula even when their dual-match record signaled they were stronger.

The owner explicitly did **not** want to back-date any change ("would not do this retroactively"), did **not** want to remove FWS entirely (it captures a real signal — roster depth), and did not want to introduce an explicit "league strength" metric (OSAA doesn't use one). The fix needed to be implicit, schedule-aware, and forward-only.

## What we considered

Two distinct design approaches surfaced during review:

1. **TOSS** (engineering-proposed) — leave APR alone (it already includes strength-of-schedule via OWP and OOWP, plus the Pass 2 league-depth adjustment). Make FWS opponent-aware by multiplying each match's FWS contribution by the opponent's APR relative to the median, clamped to a [0.75, 1.25] band. Smallest blast radius, surgical fix to the specific distortion the owner called out, and naturally captures the transitive "if you beat a team that played strong opponents, you get credit" property because APR contains OOWP.

2. **QWS** (designer-proposed, modeled on the ITA college tennis ranking) — replace RPI-style APR entirely with a quality-weighted wins formula: each win earns points equal to the opponent's Power Index × 100, each loss costs a flat 50 points, normalize per team and iterate to convergence. Larger structural change, mirrors a proven college-tennis ranking, eliminates known RPI cascading-weak-opponent pathologies. The flat 50-point loss penalty was a point of concern (it doesn't differentiate a close loss to the #1 team from a 0-8 blowout against the cellar) but expected-value math still incentivizes scheduling up because strong-opponent **wins** are worth more.

After comparison, the owner chose to **ship both** in parallel rather than pick one blind. The two formulas attack different halves of the Power Index: TOSS adjusts the FWS half, QWS replaces the APR half. Running both alongside the unchanged Current model through end of 2026 lets us see — on live data — which approach better matches the eye test, and decide for the 2027 season with evidence rather than intuition.

## What shipped

### Three models, every team, every week

For every team in the 2026 rankings, `processed_rankings.json` now carries:

- `power_index`, `apr`, `normalized_fws`, `rank`, `class_rank` — Current (baseline, unchanged)
- `power_index_toss`, `adjusted_fws`, `schedule_multiplier`, `rank_toss`, `class_rank_toss` — TOSS
- `power_index_qws`, `apr_qws`, `qws_iterations`, `rank_qws`, `class_rank_qws` — QWS

Historical seasons (2021-2025) and the three already-published weekly snapshots (`public/data/weekly/2026-04-04.json`, `04-11.json`, `04-18.json`) keep only the baseline fields and are byte-for-byte unchanged.

### Main rankings table — Model dropdown

A new "Model" filter in the rankings toolbar swaps the State, Class Rank, and Power Index columns to display the selected model's values. Default is **Current**. Switching to TOSS or QWS:

- Re-displays each row's rank, class rank, and PI from the corresponding `_toss` / `_qws` fields
- Re-sorts the table by the alt model's rank
- Tags the PI cell with a small `[TOSS]` / `[QWS]` label so it's obvious which model is in view
- Leaves all other features (playoff simulator, H2H tooltips, league standings, FWS+, search) on the baseline data — by design, since those views encode tiebreaker logic the alt models intentionally do not run through

### TOSS — the math

For each dual match the team played:

```
m_i        = clamp(opp_APR / median_APR, 0.75, 1.25)
adjusted_fws = sum(match_fws_i * m_i) / sum(m_i)
power_index_toss = (APR * 0.50) + (adjusted_fws * 0.50)
```

`opp_APR` is the **Pass-2** APR (post-league-depth-adjustment), so the multiplier already encodes the transitive opponent-of-opponent signal. Unknown opponents (e.g. Idaho schools that occasionally show up in border-school schedules) fall back to APR = 0.5, matching the existing OWP/OOWP convention. The weighted-average normalization (`÷ sum(multiplier)`, not `÷ count`) keeps `adjusted_fws` on [0, 1] so it composes cleanly with the existing 50/50 PI split.

**Behavior in practice:**
- Beating a strong opponent 5-3: `(5/8) × ~1.25 = ~0.78` credit (vs `~0.62` raw)
- Beating a weak opponent 8-0: `(8/8) × ~0.75 = 0.75` credit (vs `1.0` raw)
- Losing 3-5 to a strong opponent: `(3/8) × ~1.25 = ~0.47` credit (vs `~0.38` raw) — losses to strong teams are softened, not punished extra
- Losing 0-8 to a weak opponent: `0 × ~0.75 = 0` credit — no change (zero is zero)

### QWS — the math

For each team across the 2026 season:

```
total_matches = wins + losses + ties
quality_points = sum(opp_PI * 100 for each WIN, plus 0.5 * opp_PI * 100 for each TIE)
loss_penalty   = 50 * losses + 0.5 * 50 * ties
raw_apr_qws    = (quality_points - loss_penalty) / total_matches
apr_qws        = clamp((raw_apr_qws + 50) / 150, 0, 1)
power_index_qws = (apr_qws * 0.50) + (normalized_fws * 0.50)
```

Iterated: seed `opp_PI = opponent Win%` on iteration 0, then use the previous iteration's `power_index_qws` for subsequent iterations until `max |Δ PI| < 0.01` or 5 iterations. On live 2026 data, every team converges in **3 iterations**.

### Cadence shift — Saturdays to Sundays

Weeks 1-3 (2026-04-04 / 04-11 / 04-18) shipped on Saturdays. Beginning week 4 (2026-04-26), weekly snapshots publish on Sundays so any Saturday match results land in that week's file. Week numbering is continuous across the transition:

| Date          | Day | Week # |
|---------------|-----|--------|
| 2026-04-04    | Sat | 1      |
| 2026-04-11    | Sat | 2      |
| 2026-04-18    | Sat | 3      |
| 2026-04-26    | Sun | 4      |
| 2026-05-03    | Sun | 5      |
| 2026-05-10    | Sun | 6      |

`get_week_publish_date()`, `get_prior_publish_date()`, and `all_week_publish_dates()` in `scripts/generate_weekly_rankings.py` handle the transition. The legacy `get_week_saturday()` / `all_week_saturdays()` names are kept as aliases for backward compatibility. Running the script with no arguments during the cadence transition window (Apr 19-25) intentionally rolls *forward* to 2026-04-26 instead of overwriting the prior Saturday snapshot.

## How we know it works

### Baseline invariance

`ADJ_MODELS_ENABLED=0 python generate_site.py` produces a `processed_rankings.json` byte-identical to the pre-change `main` branch. The new models are entirely additive when the gate is off. (The gate is also automatically off for any run before 2026-04-20.)

### Historical untouched

The three pre-existing weekly snapshots in `public/data/weekly/` show no diff from `main`. Historical seasons 2021-2025 emit only the baseline fields — no `power_index_toss` / `power_index_qws` keys at all.

### Distribution sanity (2026 Boys, 121 teams)

- TOSS schedule multiplier: min 0.82, median 0.95, max 1.06. Tight distribution because most APRs cluster near the median — the model is doing what it should without saturating extremes.
- QWS iterations: min 3, max 3, mean 3.0 across all 1,472 team-year records. Convergence is fast and stable.
- Spearman rank correlation, 2026 Boys:
  - Current ↔ TOSS: **0.97**
  - Current ↔ QWS: **0.95**
  - TOSS ↔ QWS: **0.98**

Both fixes agree on the big picture. Where they diverge — and they do — that's the comparison data we built this for.

### Spot checks

The expected ordering at the top of 2026 Boys (Lincoln, Jesuit, Grant, OES, Catlin Gabel) holds across all three models with only minor reshuffles. The biggest QWS drops are mid-pack 6A/5A teams whose records were padded by weak league bottoms (Sam Barlow -49 spots, Ridgeview -40, Redmond -32). The biggest QWS rises are teams that played tough schedules and earned losses but had quality wins to show for it (Springfield +21, Century +20, Thurston +20). These are exactly the patterns the formula is designed to surface.

## What's next

1. **Watch through end of season.** Each week's snapshot will preserve its Current/TOSS/QWS triple. By end of the 2026 season we'll have ~6 weeks of side-by-side data showing how the three models reorder teams as matches accumulate.
2. **Decide for 2027.** With live evidence in hand we can pick one model as the primary, or keep multiple available, or refine the formulas (e.g. an opponent-scaled QWS loss penalty instead of the flat 50, or a wider TOSS clamp band). No code change happens until we have data to argue from.
3. **Coach feedback.** With the Model dropdown live on the main page, coaches can compare for themselves. We expect questions; the [methodology page](methodology.html#ab-test) explains all three formulas.

## Files changed

- `generate_site.py` — TOSS and QWS computation, server-side alt-model rank/class-rank, model selector dropdown, dynamic rank/PI/class-rank columns, methodology banner.
- `public/methodology.html` — new "Alternative Models (A/B Test)" section with formulas and JSON field references.
- `scripts/generate_weekly_rankings.py` — Saturday-to-Sunday cadence with continuous week numbering and backward-compat aliases.
- `CHANGELOG.md` — short summary entry pointing here.
- `AAR-power-index-ab-test.md` (this file) and rendered `public/aar-power-index-ab-test.html`.
- `public/data/processed_rankings.json` — regenerated artifact carrying the new fields.

## Non-goals (worth restating)

- We are **not** changing the APR/FWS 50/50 split in any model.
- We are **not** removing or modifying any component of the baseline Current model. It stays as the experimental control.
- We are **not** applying H2H tiebreakers to alt-model ranks. Pure PI sort keeps comparison data clean.
- We are **not** recomputing 2021-2025. Historical rankings are historical artifacts.
- We are **not** rewriting the three pre-2026-04-20 weekly JSON snapshots.

## References

- [Methodology page (A/B test section)](methodology.html#ab-test)
- [Changelog](changelog.html)
