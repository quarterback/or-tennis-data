# Opponent-Weighted Flight-Weighted Score (oFWS) — PRD

**Metric name (generic):** oFWS — Opponent-weighted Flight-Weighted Score
**Metric name (Oregon):** FQI — Flight Quality Index
**Version:** 1.0
**Status:** Implemented (Oregon HS girls + boys, 2021–2026)
**Scope:** Team rating systems for dual-match racquet sports (tennis, badminton, squash, etc.)

---

## 1. Summary

oFWS is a team rating component that measures how well a team performs at the **individual flight level** within dual matches, weighted by two independent factors:

1. **Flight importance** — higher flights (e.g., #1 singles) count more than lower flights.
2. **Opponent strength** — flight performance against stronger opponents counts more than flight performance against weaker ones.

The metric produces a single value in roughly the 0–1 range that can be averaged, compared across teams, or composited with other rating components (e.g., RPI / APR) into an overall team index.

oFWS is the generic, portable metric. **FQI** is the Oregon-specific label where this metric appears on the OregonTennis.org rankings table; the math is identical.

---

## 2. Problem this solves

Conventional dual-match rating systems (RPI, win percentage, etc.) treat every win as equivalent:

- An 8–0 sweep of the weakest team in the state looks identical to an 8–0 sweep of the #1 team.
- A competitive 3–5 flight loss to a state power looks identical to a 3–5 loss to a bottom-quartile opponent.
- A team with a weak schedule and no losses outranks a team with a strong schedule and a few competitive losses.

Raw Flight-Weighted Score (FWS) — which many rating systems use to measure "roster depth" by looking at flight-level results inside a dual match — fixes the "stacking" problem but not the schedule-quality problem. FWS still treats all opponents as equivalent.

The practical consequence is that teams with weak schedules are systematically over-rewarded and teams with strong schedules are systematically under-rewarded, because the rating rewards "don't lose" more than it rewards "play real competition."

oFWS is designed specifically to close this gap while preserving everything FWS was designed to do.

---

## 3. Goals and non-goals

### Goals

- **Reward flight-level performance against stronger opposition.** Flight wins against top-tier opponents should carry more weight than flight wins against bottom-tier opponents.
- **Remove the hidden penalty on scheduling up.** Teams in deeper conferences, or teams whose schedule is forced by geography to include strong opponents, should not be punished by the rating system for the flight-level losses that result.
- **Preserve the anti-stacking property of FWS.** Top flights still carry more weight than bottom flights; teams cannot inflate their rating by moving stars to bottom positions.
- **Produce a single number per team that slots into existing rating composites** (e.g., `PowerIndex = 0.5 × APR + 0.5 × oFWS`).
- **Remain tractable for small-volume leagues.** Must work for teams playing as few as 3 matches.

### Non-goals

- **oFWS does not require teams to play up.** The goal is not "incentivize scheduling stronger opponents." Beating peer-level opponents continues to be credited at baseline. The fix is in the ceiling, not the floor.
- **oFWS does not replace dual-match W/L metrics.** It is a complement to RPI/APR, not a substitute. A team that loses every dual match but wins flights should not rank higher than a team that wins dual matches.
- **oFWS is not a player rating.** It is a team-level metric that aggregates across all dual matches in a season.
- **oFWS is not classification-corrective by itself.** Cross-classification comparison still requires thoughtful interpretation; oFWS makes it fairer but doesn't eliminate the need for classification-relative companion metrics (e.g., FQI+).

---

## 4. Design

### 4.1 Core formula

For each team *T* with dual matches *M₁, M₂, …, Mₙ*:

```
oFWS(T) = mean over matches m of [ flight_score(m, T) × opponent_weight(m, T) ]
```

Where:

- **flight_score(m, T)** — the per-match flight-weighted score (the base FWS).
- **opponent_weight(m, T)** — a multiplier based on the opponent's baseline rating, centered at 1.0.

The mean is across all dual matches the team played. Each match contributes one (score, weight) pair.

### 4.2 Layer 1: flight_score (base FWS)

For each dual match *m* played by team *T*:

```
flight_score(m, T) = Σ(flight_weight × flight_won) / Σ(flight_weight × flight_contested)
```

Flight weights are tunable per sport/state. The Oregon implementation uses:

| Flight          | Weight |
|-----------------|-------:|
| 1st Singles     | 1.00   |
| 2nd Singles     | 0.75   |
| 3rd Singles     | 0.25   |
| 4th Singles     | 0.10   |
| 1st Doubles     | 1.00   |
| 2nd Doubles     | 0.50   |
| 3rd Doubles     | 0.25   |
| 4th Doubles     | 0.10   |

These weights are not normative — they reflect Oregon's 8-flight competitive reality. A state with 6 flights, 7 flights, or different flight-importance conventions can swap the weight table without changing the algorithm.

The denominator is the sum of weights of flights **actually contested** (not the theoretical max). This handles forfeits proportionally: a short match with only 4 flights played has a smaller denominator, so forfeiting flights doesn't "cap" the available score.

`flight_score(m, T)` lives in [0, 1].

### 4.3 Layer 2: opponent_weight

For each dual match, compute:

```
opponent_weight(m, T) = opp_rating(m) / median_rating
```

Where:

- **opp_rating(m)** — the opponent's baseline team rating. In Oregon this is pass-1 APR (RPI-style). Any team rating that represents "overall team quality" works (ELO, rating average, etc.).
- **median_rating** — the median baseline rating across all teams in the same cohort (same sport, same season, same gender).

Properties:

- A median-rating opponent produces a multiplier of exactly 1.0 (neutral).
- An above-median opponent produces a multiplier > 1.0 (amplifies the match's contribution).
- A below-median opponent produces a multiplier < 1.0 (discounts the match's contribution).
- Unknown opponents (e.g., cross-state teams, non-ranked opponents) default to the median rating, and thus are neutral.

This centering is important: it preserves absolute magnitude on average. A team playing only median opponents sees their oFWS equal to their raw FWS. A team playing above-median opponents sees oFWS > raw FWS. A team playing below-median opponents sees oFWS < raw FWS.

### 4.4 Aggregation

```
oFWS(T) = (1/n) Σ [ flight_score(mᵢ, T) × opponent_weight(mᵢ, T) ]
```

Simple arithmetic mean across matches. All matches weighted equally; the opponent-weight factor is already inside each term.

Output range: typically [0.2, 1.3] for a full-season team. Values above 1.0 indicate a team is competing well above baseline against above-median opponents. Values below 0.5 indicate weak flight-level performance, a weak schedule, or both.

### 4.5 Two-pass computation

oFWS requires opponent ratings as input. Opponent ratings, in turn, typically depend on team quality metrics. To avoid circularity:

1. **Pass 1:** Compute a baseline team rating using dual-match W/L metrics only (e.g., RPI/APR). oFWS is not used as input.
2. **Pass 2:** Use pass-1 ratings as the `opp_rating` input to oFWS. Compute oFWS for every team.
3. **Pass 3 (optional):** Composite pass-1 rating and pass-2 oFWS into the final rating (e.g., Power Index).

This is deliberately not iterative beyond pass 2. Iterating to convergence introduces instability and is unnecessary — a single oFWS pass with static opponent ratings is sufficient signal.

### 4.6 Classification-relative companion metric: FQI+

For user-facing readability, Oregon publishes an adjusted version:

```
FQI+(T) = 100 × FQI(T) / mean_FQI(classification_of(T))
```

Where `mean_FQI(c)` is the average FQI across all teams in classification *c* within the same season/gender.

FQI+ is a 100-indexed number: 100 = classification average, 115 = 15% above average, 85 = 15% below. This is standard sabermetric convention (parallel to OPS+ in baseball) and is purely a display aid.

FQI+ does not feed back into the Power Index; it exists only for contextualized reading of individual team values.

---

## 5. How oFWS differs from raw FWS

| Property                                            | Raw FWS | oFWS  |
|-----------------------------------------------------|:-------:|:-----:|
| Weights flights by competitive importance           |   Yes   |  Yes  |
| Penalizes stacking stars at bottom flights          |   Yes   |  Yes  |
| Handles forfeits proportionally                     |   Yes   |  Yes  |
| Distinguishes flight wins by opponent strength      |   No    |  Yes  |
| Credits competitive flight losses against top teams |   No    |  Yes  |
| Discounts flight sweeps against weak opponents      |   No    |  Yes  |
| Requires opponent ratings as input                  |   No    |  Yes  |
| Equivalent to raw FWS if all opponents are median   |   —     |  Yes  |

The last row is the key identity property: in a hypothetical season where every team plays only median-rated opponents, oFWS and raw FWS produce identical values. oFWS is strictly a refinement, not a replacement.

---

## 6. Portability

This metric was designed to be usable in any state or sport with dual-match structure. The three parameters that vary by context:

### 6.1 Flight weights

Oregon uses 8 flights (4 singles + 4 doubles). States with different flight structures substitute their own weight table. Examples:

- **6-flight tennis (3 singles + 3 doubles):** S1=1.00, S2=0.60, S3=0.20, D1=1.00, D2=0.50, D3=0.20.
- **5-flight tennis (3 singles + 2 doubles):** S1=1.00, S2=0.65, S3=0.25, D1=1.00, D2=0.50.
- **Badminton (5 flights: 2 singles + 3 doubles):** any weights summing to reasonable totals.

The algorithm makes no assumptions about flight count or naming. Weights are a config, not a hard-coded constant.

### 6.2 Baseline opponent rating

oFWS requires an `opp_rating` per team for the opponent-weight calculation. Oregon uses pass-1 APR (RPI variant). Any team-level rating works as long as it:

- Produces a scalar per team
- Is computed without using oFWS as input (no circular dependency)
- Distributes reasonably across the team population (so a median is meaningful)

Valid alternatives: raw win percentage, ELO rating, conference-adjusted W/L, an existing state-published rating. The only requirement is that the distribution be sensible enough that "median" has meaning.

### 6.3 Cohort for median calculation

The `median_rating` is computed over a cohort of teams considered to be in the same competitive universe. Oregon uses `(year, gender)` as the cohort — all girls teams in 2026, all boys teams in 2026, etc.

Other cohort definitions are valid:

- `(year, gender, classification)` — normalizes within classification only
- `(year, gender, region)` — normalizes within region for state-level applications

The coarser the cohort, the more oFWS represents performance against the full field. The finer the cohort, the more it isolates schedule ambition within a peer group. Oregon's choice of `(year, gender)` was deliberate to make schedule-up scheduling produce a visible rating lift.

### 6.4 Minimum matches

oFWS becomes statistically unreliable below ~3 matches. Oregon applies a 3-match minimum before publishing oFWS for a team. States with shorter seasons may apply a different threshold, possibly as low as 2, but below 2 the arithmetic mean is not meaningful.

---

## 7. Integration with a composite rating

Oregon's Power Index is:

```
PowerIndex = 0.50 × APR + 0.50 × oFWS
```

The 50/50 split reflects a design view that "winning matches" and "winning flights against real competition" should be given equal weight at the team-rating level. Other splits are defensible:

- **70/30 (APR/oFWS):** more traditional, rewards W/L record more
- **30/70 (APR/oFWS):** rewards flight-level excellence more
- **Variable by sport:** e.g., volleyball-style sports might weight flights differently than tennis

The metric is agnostic to how it's composited. Consumers should choose a weight split consistent with their rating philosophy and be transparent about it.

---

## 8. Diagnostic outputs

For transparency and debugging, implementations should retain and expose:

- **Raw (unweighted) FWS:** equivalent to the pre-oFWS metric. In Oregon this is `normalized_fws_raw` in the data object.
- **oFWS (opponent-weighted):** the final metric. In Oregon this is `fqi`.
- **Per-match (opp_id, flight_score) tuples:** internal record of which match contributed what. Needed for diagnostics, not typically exposed publicly.
- **FQI+ / classification-relative index:** display companion.

Comparing raw FWS against oFWS for any team tells you, at a glance, whether the team's schedule amplified or discounted their flight performance. A team with raw FWS = 0.72 and oFWS = 0.85 is competing at a higher level than raw FWS suggests (strong schedule). A team with raw FWS = 0.85 and oFWS = 0.65 is benefiting from a weak schedule.

---

## 9. Known limitations

### 9.1 Early-season instability

oFWS depends on opponent ratings, which are unstable early in a season when every team has few matches. Pass-1 APR is volatile at 2–3 matches; that volatility propagates into oFWS. In practice, oFWS rankings start to stabilize around week 3 of a 7-week season.

### 9.2 Disconnected match graphs

If a subset of teams never plays outside itself, the `opp_rating` distribution within that subgraph can be artificially compressed. In Oregon this occurs occasionally with remote small-schools districts. The metric still functions, but cross-subgraph comparisons should be interpreted carefully.

### 9.3 Unranked opponents

Cross-state opponents, club teams, etc., lack a baseline rating. These are treated as median (neutral). This is defensible but imperfect: a team playing a strong out-of-state opponent won't get credit for it. Implementations can choose to manually override these with approximated ratings where the data justifies it.

### 9.4 Flight weights are a judgment call

The exact weight values (1.00 / 0.75 / 0.25 / 0.10 for singles) are a design choice, not a derived result. Changing weights changes rankings. Implementations should document their chosen weights and resist frequent adjustment (week-over-week stability matters for credibility).

---

## 10. Implementation reference (Oregon)

Source files:

- `generate_site.py::calculate_fws_per_match` — computes `flight_score(m, T)` for each dual match.
- `generate_site.py::build_rankings` — post-pass-1 step computes `opp_rating`, median, and recomputes `normalized_fws` as the opponent-weighted mean.
- `generate_site.py` output object — includes `fqi`, `fqi_plus`, `normalized_fws_raw`, and legacy aliases `normalized_fws`, `fws_plus`.
- `public/methodology.html` — user-facing documentation.

The algorithm is ~40 lines of Python in total (not counting the underlying flight-score computation). It is not computationally expensive: O(matches × teams) per pass, with two passes per season-gender combination.

---

## 11. Why this matters beyond rankings

oFWS was developed in response to a specific observation: rating systems that reward "don't lose to weak teams" more than "play real competition" distort scheduling incentives at the program level. Teams that schedule up are penalized in the standings; teams that schedule down are rewarded. Over multiple seasons, this pushes the entire competitive ecosystem toward safer scheduling, which is bad for the sport.

An opponent-weighted flight metric reverses this incentive without requiring anyone to schedule up. It merely ensures that when a team does schedule up, and competes at flight level even in losses, the rating reflects that. Teams that prefer to stay in their competitive tier can do so without being "beaten" by ambitious schedulers; teams that want to schedule up no longer pay a rating tax for it.

This document exists so that other states, sports, and rating system maintainers can adopt the same metric in their own context without having to rediscover the design from scratch.
