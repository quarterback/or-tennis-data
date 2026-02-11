# Oregon High School Tennis Ranking System
## Executive Summary for OSAA

---

## Overview

The Oregon High School Tennis Power Index is a comprehensive ranking system designed to evaluate team performance across five years (2021-2025) of dual match data. The system combines traditional strength-of-schedule metrics with tennis-specific roster depth analysis to produce fair, transparent, and defensible rankings.

---

## Power Ranking Methodology

### Core Formula
```
Power Index = (APR × 50%) + (FWS × 50%)
```

### 1. APR (Adjusted Performance Rating) — Strength of Schedule
**Standard RPI Formula used in college sports:**
- **Win Percentage (25%)**: Team's dual match record
- **Opponent Win Percentage (50%)**: Strength of schedule
- **Opponent's Opponent Win Percentage (25%)**: Indirect schedule strength

This heavily weights who you play (75% of APR) over just winning, rewarding teams that face tough competition.

### 2. FWS (Flight-Weighted Score) — Roster Depth
**Tennis-specific metric measuring depth across all positions:**
- Tracks wins at 4 singles positions and 4 doubles positions
- Each position weighted by competitive significance:
  - Singles 1 & Doubles 1: 1.00 (most valuable)
  - Singles 2: 0.75
  - Doubles 2: 0.50
  - Singles 3 & Doubles 3: 0.25
  - Singles 4 & Doubles 4: 0.10

**Key Innovation:** Uses proportional weighting to prevent forfeit penalties. If a match only has 4 flights contested, FWS is calculated against the weight of those 4 flights, not penalizing teams for shortened matches.

### Why FWS Matters
Traditional RPI treats a 6-1 win (dominant roster) the same as a 4-3 win (bare minimum). Power Index rewards teams that win broadly across all eight positions, reflecting true team strength in a sport where roster depth is critical.

---

## Playoff Simulator Features

### OSAA-Compliant Bracketing
The tool includes three bracketing modes:

1. **Pure Seeding**: Traditional 1v16, 2v15 format with basic same-league avoidance
2. **Regional Mode**: Travel-optimized using greedy nearest-neighbor algorithm (documented 33-45% mileage savings)
3. **OSAA Bracketing Mode** (NEW): Full compliance with OSAA team sports playoff rules

### OSAA Bracketing Mode Implementation

**League Champion Home Game Guarantees:**
- League champions automatically moved up minimum places to ensure first-round home games
- Example: #12 league champion → moved to #8 in 16-team bracket
- Bracket home game cutoffs:
  - 16-team: Seeds 1-8 host
  - 12-team: Seeds 5-8 host (1-4 have byes)
  - 8-team: Seeds 1-4 host

**Same-League First-Round Avoidance (3-Move Rule):**
- When same-league matchup occurs in first round, attempts up to 3 visitor swaps
- Always moves lower-ranked team (visitor), never removes host's home game
- Prefers moving downward (to lower seeds), moves upward if necessary
- If unresolved after 3 attempts, matchup remains (per OSAA policy)

**League Champion Seeding Priority:**
- At-large teams cannot be seeded higher than league champions from the same league
- Ensures proper league hierarchy is maintained in playoff seeding

---

## Data Transparency & Validation

### Data Sources
- 5 years of dual match results (2021-2025)
- 1,214 ranked teams across all classifications
- Historical state tournament results for validation
- Geographic coordinates for 90+ Oregon cities (travel optimization)

### Head-to-Head Tiebreaker
- Applied when teams within 2% Power Index difference
- Requires direct head-to-head record (split series ignored)
- Includes circular conflict prevention (A>B>C>A scenarios)
- 2024-2025 season: 24-28 H2H adjustments applied per gender

### Validation Metrics
- System tracks league win percentage separately for context
- FWS+ normalized score (100 = average) for quick comparison
- Flight breakdown showing win rate by position
- All calculations traceable to source match data

---

## Tool Capabilities

### Interactive Dashboard Features
- Year-by-year rankings (2021-2025) by gender and classification
- League-by-league performance analysis with depth scoring
- Playoff field simulator with auto-bid selection
- Distance calculation for first-round matchups (mileage optimization)
- Real-time bracket generation with conflict detection

### Technical Details
- Static HTML dashboard (no server required)
- Runs in any modern web browser
- JSON data export for external analysis
- Complete audit trail of all ranking decisions

---

## Key Differentiators from Traditional RPI

| Aspect | Traditional RPI | Oregon Power Index |
|--------|----------------|-------------------|
| Formula | WP + OWP + OOWP only | 50% APR + 50% FWS |
| Depth consideration | Not factored | Major factor (50%) |
| Tennis-specific | No position weighting | 8-position flight weights |
| Forfeit handling | Full match penalties | Proportional weighting |
| Tiebreakers | None | H2H with conflict prevention |

---

## Use Cases

### Primary Applications
1. **State Tournament Seeding**: Fair, data-driven playoff seeding
2. **Schedule Strength Analysis**: Objectively measure league competitiveness
3. **Travel Optimization**: Reduce first-round travel burden by 33-45%
4. **Historical Trends**: Track program growth year-over-year

### Compliance Benefits
- Fully implements OSAA team sports playoff rules
- Transparent methodology (no "black box" rankings)
- Defensible decisions with documented rationale
- Automated conflict detection and resolution

---

## Credibility & Testing

### System Validation
- Rankings correlate strongly with state tournament results
- League depth scores align with historical championship performance
- Travel optimization validated against 2024 regional analysis
- H2H tiebreaker tested with circular conflict scenarios

### Documentation
- Complete methodology explained in `/docs/power-index-explained.md`
- System architecture documented in `/docs/portfolio-overview.md`
- Source code available for audit (`generate_site.py`, lines 549-765)

---

## Contact & Implementation

**System Status**: Fully operational for 2021-2025 seasons
**Last Updated**: February 2026
**Data Format**: JSON export compatible with existing OSAA systems
**Browser Support**: All modern browsers (Chrome, Firefox, Safari, Edge)

**Key Files:**
- Interactive Dashboard: `index.html`
- Ranking Data: `public/data/processed_rankings.json`
- Methodology Guide: `docs/power-index-explained.md`

---

## Summary

The Oregon High School Tennis Power Index provides a comprehensive, fair, and transparent ranking system that:
- Combines traditional strength-of-schedule (APR) with tennis-specific roster depth (FWS)
- Fully implements OSAA team sports playoff rules for league champion home games
- Offers three bracketing modes including travel-optimized regional matching
- Maintains complete data transparency with documented methodology
- Provides interactive tools for playoff simulation and schedule analysis

The system is ready for immediate use in state tournament seeding and playoff bracket generation, with full OSAA compliance and defensible ranking decisions based on five years of validated match data.
