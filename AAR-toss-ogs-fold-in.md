# After Action Report: Game-Share Fold-In to TOSS

**Date:** 2026-04-26 (computed and shipped)
**Effective:** 2026-04-26 — primary Power Index formula updated for 2026+ season-long rankings
**Branch:** `claude/marist-quality-win-analysis-AUd3L`
**Author:** Engineering, after iterative review with site owner.

## What we did

The primary Power Index formula on the 2026 season rankings now reads:

```
PI = 0.40 × APR + 0.40 × FQI + 0.20 × oGS
```

Where `oGS` is a new third component: the opponent-APR-weighted aggregate share of *games* (not flights) a team won across the season. Both FQI and oGS use the same per-match opponent multiplier — `opp_APR / median_APR` — so the schedule-aware scaling that was already in FQI applies identically to game share.

Historical seasons (2021–2025) keep the original 50/50 APR + FWS formula and are unchanged. The three already-published Saturday weekly snapshots (2026-04-04, 2026-04-11, 2026-04-18) keep their original published values and are unchanged. The change applies forward only, starting with the 2026-04-26 season-long rankings; weekly snapshots from Week 4 (2026-04-26 Sunday cadence) onward use the new formula.

## Why we did it

One week after promoting TOSS (APR + FQI, 50/50) to the primary Power Index on 2026-04-26, a residual distortion remained visible: a small number of undefeated teams in shallow conferences continued to sit above demonstrably stronger teams from deeper conferences, despite the FQI multiplier already penalizing weak-opponent flight wins. The mechanism was structural: a team that wins 8–0 in flights every match has a raw FWS near 1.0, and a multiplier of `1.0 × 0.7 = 0.7` (the typical case for thin-conference opponents) still sits well above field median. The multiplier is correct in direction but too weak in magnitude to reorder the top of the rankings against the kind of dominant flight outcomes that arise from running the table on a shallow schedule.

Two failure modes were visible to readers:

- **Top-of-rankings inflation:** undefeated small-classification teams sat at or near #1 statewide on the strength of running their conference 9–0 with high flight-win rates against opponents whose own quality was suppressed by the same conference dynamics.
- **Mid-pack deflation:** middling-record teams in deeper conferences who lost flights 5–3 or 4–4 against state-contender opposition sat lower than their on-court quality suggested, because those competitive losses contribute the same FWS as one-sided losses.

The site owner's explicit constraint was that the fix must not introduce a class-aware multiplier. No region or classification of the state should be hand-weighted up or down. The fix had to come from a signal already present in the data.

## What we considered

Two design directions surfaced:

1. **Steeper opponent multiplier on FQI.** Replace the linear `opp_APR / median_APR` with a non-linear curve (squared, or piecewise more aggressive below 1.0). Single-knob change, easy to roll back, but amplifies an existing parameter rather than adding new information. Risks tuning sensitivity issues if the median APR shifts season to season.

2. **Add a third component sourced from set/game data.** Tennis exposes per-set, per-game outcomes that are absent from most team-sport rating systems. Folding in opponent-weighted aggregate game share gives the index a second, independent signal: not just "did you win the flight?" but "by how much?" — distinguishing a 6–2 flight win that came in straight 6–0 sets from a 6–2 flight win that went the distance.

Both directions were dry-run against the current data. The single-knob approach moved teams in roughly the same direction but added no information the existing parameters didn't already encode. The fold-in approach correlated 0.86–0.90 with the existing PI but disagreed in *interpretable* ways — the divergent cases looked like the cases the owner was complaining about, not noise. We chose direction 2.

## Weight calibration

Three weight splits were dry-run side by side:

| Split | APR | FQI | oGS | Effect |
|-------|-----|-----|-----|--------|
| Mild | 0.45 | 0.45 | 0.10 | Directional but soft; some over-rewarded teams still sat too high |
| **Moderate** | **0.40** | **0.40** | **0.20** | Sweet spot: top-of-rankings inflation resolved without overcorrecting |
| Aggressive | 0.35 | 0.35 | 0.30 | Punitive on undefeated thin-conference teams; began diluting FQI's anti-stacking purpose |

Moderate landed on the right balance for the season's data. It moved the teams the eye-test flagged as over-rewarded into reasonable bands while keeping the FQI signal dominant enough to preserve its anti-stacking role.

## Game-share computation

Per dual match, the team's `game_share` is `games_won / games_played` summed across all flights, with three format-specific rules:

- **Best-of-3 sets and 8-game pro sets** contribute raw game totals (a 6–4, 6–2 flight contributes 12 games for the winner, 6 for the loser).
- **Tiebreaker games within a regular set** (the 7–6 case) count as a single deciding game for the set winner, not the raw tiebreaker point total.
- **Match tiebreakers** — the 10-point super-tiebreaker that replaces a third set when sets are split 1–1 — count as one game to the winner and zero to the loser. A 10–7 super-TB is one decision, not 17 games. Without this rule the metric would over-weight third-set tiebreakers at 17× the influence of a regular game.

Flights without set-level data fall back to a binary one-game outcome (one to the winner, zero to the loser) so coverage stays high. In the 2026 dataset, set-level data is present on 98.1% of contested flights.

The team's season-long `oGS` is the arithmetic mean of `(match_game_share × opp_APR / median_APR)` across all dual matches — the same formula shape as FQI, just with game share replacing flight score as the per-match input.

## What shipped

### Code changes (`generate_site.py`)

- New module-level constants: `TOSS_APR_WEIGHT = 0.40`, `TOSS_FQI_WEIGHT = 0.40`, `TOSS_OGS_WEIGHT = 0.20`.
- `calculate_fws_per_match()` extended to also return `games_won`, `games_played`, `game_share`, and per-match `game_share_match_records` (the same structure FQI uses for opponent reweighting).
- Match-tiebreaker detection: a set with `number ≥ 3` and either side ≥ 10 is treated as a super-TB (1 game total), not a regular set.
- Pass 3 (TOSS) now computes `ogs` per team and the new three-component `power_index_toss`. The `power_index` field continues to be overwritten by `power_index_toss` once TOSS is primary, so all downstream consumers (sort, league ranks, H2H, playoff sim, class rank) pick up the new formula automatically.

### JSON schema additions (`processed_rankings.json`)

For every 2026 entry:

- `games_won`, `games_played`, `game_share` — informational aggregates, present on all 2026 entries.
- `ogs` — the opponent-weighted game share that feeds TOSS, alongside the existing `fqi`.
- `power_index_toss`, `power_index_legacy`, `power_index_qws` — unchanged in structure; `power_index_toss` and `power_index` (when TOSS is primary) reflect the new three-component formula.

### Methodology page

A new section, `Opponent-Weighted Game Share (oGS)`, sits between the FQI and H2H sections and explains:

- What oGS is and how it relates to FQI (same opponent multiplier; different per-match input).
- How games are counted (set-type-aware, with super-TB and tiebreaker-game rules called out).
- Why it's additive rather than a replacement (FQI's anti-stacking role is preserved; oGS answers a different question).

The Overview & Formula section, the TOSS formula box, and the table of contents were updated to reflect the three-component structure. The QWS and Legacy formulas are unchanged.

### Weekly rankings

The weekly rankings generator (`scripts/generate_weekly_rankings.py`) reads `power_index` from the team rankings, so it picks up the new formula automatically for any week generated on or after 2026-04-26. Earlier weekly snapshots are not regenerated; they remain canonical at their published values.

## Outcomes

The Pearson correlation between the previous (50/50 APR + FQI) primary PI and the new (40/40/20) primary PI is roughly 0.96 across both genders for 2026 — most teams move zero or one rank slot. The reorderings cluster at the top of the table and in the mid-pack, exactly where the residual distortions sat:

- **Undefeated thin-conference teams** moved out of the top tier into more accurate bands. The single largest movement was an undefeated small-classification girls team going from #1 to #7 statewide — still elite, no longer artificially atop the field over teams with stronger schedules.
- **Mid-pack teams in deeper conferences** rose meaningfully. Teams with .500-ish records on tough schedules whose losses were close in games gained 5–25 spots. The top rises were mid-record teams that had been competitive in flights against state-contender opposition.
- **Bottom of the rankings** is largely unchanged. The metric is opponent-weighted, so weak-record teams playing weak schedules don't get an artificial boost just for being competitive in their narrow context.

No class-aware multiplier was introduced, no school is named in the formula, and no league is treated differently from any other. The signal comes entirely from per-match game data the upstream feed already provides.

## What we didn't do

- **No change to FQI itself.** The flight-weight gradient (S1=1.00 down to S4=0.10, D1=1.00 down to D4=0.10) and the opponent multiplier on flight scores are unchanged. FQI's stated job — discouraging singles-heavy stacking and rewarding deep, balanced rosters — is unaffected.
- **No change to APR.** APR is still the OSAA-style RPI: WP × 0.25 + OWP × 0.50 + OOWP × 0.25.
- **No change to historical seasons.** 2021–2025 use the 50/50 APR + FWS formula they always have.
- **No change to QWS or Legacy.** Both remain available via the Model dropdown for comparison; their formulas are unchanged.
- **No second-degree opponent weighting added explicitly.** OOWP is already in APR, and APR is what feeds the FQI/oGS multipliers, so second-degree strength of schedule is already transitively present. A standalone OOWP term was considered and rejected as redundant signal.

## Risks and follow-ups

- **Format-mix sensitivity.** Pro-set matches contribute fewer total games than best-of-3, which biases the denominator slightly for teams in pro-set-heavy slates. The bias is small in practice (most matches in the dataset are best-of-3) but worth monitoring if a region or tournament shifts heavily to pro sets.
- **Tournament events.** The current `is_dual_match` filter excludes events with "Tournament" or "State Championship" in the title. Tournament round-robin matches that get posted as individual duals will be included; those that get posted as a single multi-team event are not. The upstream data structure controls this, not the new formula.
- **Coverage drift.** Set-level data coverage is 98.1% in 2026. If that drops materially in future seasons (e.g., a feed change), the binary fallback will dilute the metric's signal. Worth checking annually before season start.
- **One season of data.** The calibration is informed by the spread of 2026 data. If subsequent seasons have a substantially different distribution of league depth or set-type usage, the 40/40/20 split may want re-tuning. The constants live at the top of `generate_site.py` and are easy to revisit.

## Rollback

If the formula needs to be reverted to 50/50 APR + FQI, set the constants in `generate_site.py`:

```
TOSS_APR_WEIGHT = 0.50
TOSS_FQI_WEIGHT = 0.50
TOSS_OGS_WEIGHT = 0.0
```

and regenerate. No data migration is required because `oGS` and `game_share` remain valid informational fields regardless of the weight applied to them in the PI formula.
