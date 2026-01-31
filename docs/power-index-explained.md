# Oregon High School Tennis Power Index

## Overview

The Power Index is a ranking system designed to evaluate Oregon high school tennis teams by combining **match outcomes** with **roster depth**. Unlike simple win-loss records, the Power Index rewards teams that win across all flight positions, not just at the top of their lineup.

---

## The Formula

```
Power Index = (APR × 0.50) + (FWS × 0.50)
```

| Component | Weight | Measures |
|-----------|--------|----------|
| **APR** (Adjusted Performance Rating) | 50% | Match outcomes + strength of schedule |
| **FWS** (Flight-Weighted Score) | 50% | Roster depth across all positions |

---

## APR: Adjusted Performance Rating

APR uses the standard RPI formula employed by many state athletic associations:

```
APR = (WP × 0.25) + (OWP × 0.50) + (OOWP × 0.25)
```

| Term | Definition |
|------|------------|
| **WP** | Win Percentage — your team's wins ÷ total matches |
| **OWP** | Opponent Win Percentage — average win % of teams you played |
| **OOWP** | Opponent's Opponent Win Percentage — average win % of your opponents' opponents |

### Why APR matters
- Rewards teams that play strong schedules
- A win against a .700 team counts more than a win against a .300 team
- Accounts for the "quality" of your wins and losses

---

## FWS: Flight-Weighted Score

FWS measures how well a team performs **across all flight positions** in dual matches. Each flight is weighted based on its competitive significance:

### Flight Weights

| Flight | Weight | Rationale |
|--------|--------|-----------|
| Singles 1 | 1.00 | Top position, highest competition |
| Singles 2 | 0.75 | Strong competition |
| Singles 3 | 0.25 | Mid-level |
| Singles 4 | 0.10 | Development position |
| Doubles 1 | 1.00 | Top doubles, equal to #1 singles |
| Doubles 2 | 0.50 | Strong competition |
| Doubles 3 | 0.25 | Mid-level |
| Doubles 4 | 0.10 | Development position |

**Maximum possible FWS per match: 3.95 points**

### How FWS is calculated

For each dual match:
1. Sum the weights of flights your team won
2. Divide by the total weight of flights actually contested
3. Average across all dual matches

### Proportional Weighting for Short Matches

FWS uses **proportional weighting** to fairly handle forfeits and shortened matches.

**Example A — Full Match (8 flights played):**
- Team wins: 1S, 2S, 1D, 2D (weights: 1.0 + 0.75 + 1.0 + 0.5 = 3.25)
- Available weight: 3.95
- Match FWS: 3.25 ÷ 3.95 = **0.82**

**Example B — Short Match (only 4 flights played: 1S, 2S, 1D, 2D):**
- Team wins: 1S, 1D (weights: 1.0 + 1.0 = 2.0)
- Available weight: 1.0 + 0.75 + 1.0 + 0.5 = 3.25
- Match FWS: 2.0 ÷ 3.25 = **0.62**

This ensures teams aren't penalized for flights that were never contested due to forfeits or scheduling.

---

## Putting It Together

### Sample Calculation

| Team | Record | APR | FWS (normalized) | Power Index |
|------|--------|-----|------------------|-------------|
| Lincoln | 10-2 | 0.657 | 0.800 | **0.729** |
| Grant | 11-1 | 0.702 | 0.720 | **0.711** |

In this example:
- **Grant** has a better record and APR
- **Lincoln** has stronger depth (higher FWS)
- The Power Index balances both factors

---

## Display Values

On oregontennis.org, you'll see:

| Column | Range | Description |
|--------|-------|-------------|
| **Power Index** | 0.000 – 1.000 | Combined ranking metric |
| **APR** | 0.000 – 1.000 | Strength-of-schedule adjusted record |
| **FWS** | 0.00 – 3.95 | Raw flight points (coach-friendly) |
| **SOS** | 0.000 – 1.000 | Strength of Schedule (OWP) |

*Note: FWS is displayed as raw points (0–3.95) for intuitive reading, but normalized (0–1) for the Power Index calculation.*

---

## Head-to-Head Tiebreaker

When two teams have Power Index values within **2%** of each other, head-to-head results are applied:
- If Team A beat Team B and they're within 2% PI, Team A ranks higher
- This only applies to teams that actually played each other
- Split series (1-1) do not trigger adjustments

---

## Key Benefits

1. **Rewards Depth**: Teams can't win on #1 singles alone
2. **Fair Scheduling**: Strength of schedule is factored in
3. **Handles Forfeits**: Proportional weighting prevents unfair penalties
4. **Transparent**: All components are visible and verifiable

---

## Glossary

| Term | Definition |
|------|------------|
| **Dual Match** | Team vs. team competition (not tournaments) |
| **Flight** | Position in lineup (1S, 2S, 3S, 4S, 1D, 2D, 3D, 4D) |
| **Normalized** | Scaled to 0–1 range for fair comparison |
| **Proportional Weighting** | Dividing by available points, not maximum possible |

---

## Questions?

Contact oregontennis.org for methodology questions or data corrections.

---

*Last updated: January 2025*
