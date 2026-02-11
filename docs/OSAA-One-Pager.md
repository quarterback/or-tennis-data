# Oregon Tennis Power Index & Playoff Simulator
## One-Page Summary for OSAA

---

## What It Does
Ranks Oregon high school tennis teams using 5 years of dual match data (2021-2025) and simulates OSAA-compliant playoff brackets with automatic league champion home game guarantees and same-league conflict avoidance.

---

## Power Index Formula
```
Power Index = (APR × 50%) + (FWS × 50%)
```

**APR (Adjusted Performance Rating)** — Standard college sports RPI:
- 25% Win Percentage + 50% Opponent Win % + 25% Opponent's Opponent Win %
- Rewards strength of schedule (who you play matters more than just winning)

**FWS (Flight-Weighted Score)** — Tennis-specific roster depth:
- Measures wins across 8 positions (4 singles, 4 doubles)
- Weighted by importance: S1/D1 = 1.0, S2 = 0.75, D2 = 0.50, S3/D3 = 0.25, S4/D4 = 0.10
- **Key innovation**: Proportional weighting prevents forfeit penalties
- Rewards teams that win broadly (6-1 > 4-3), not just barely

**Why hybrid?** Traditional RPI ignores roster depth. Power Index recognizes tennis teams can't win on one player alone.

---

## OSAA Compliance Features

### ✅ League Champion Home Game Guarantees
- Auto-bids moved up minimum places to ensure first-round home games
- Example: #12 league champion → #8 in 16-team bracket
- Home game cutoffs: 16-team (1-8 host), 12-team (5-8 host), 8-team (1-4 host)

### ✅ Same-League First-Round Avoidance (3-Move Rule)
- Attempts up to 3 visitor swaps when same-league matchup occurs
- Always moves lower seed, never removes home games
- Prefers downward moves (to lower seeds), upward if needed
- Unresolved after 3 moves = left as-is (per OSAA policy)

### ✅ League Champion Seeding Priority
- At-large teams cannot outrank league champions from same league
- Maintains proper league hierarchy in playoff seeding

---

## Three Bracketing Modes

| Mode | Purpose | Key Feature |
|------|---------|-------------|
| **Pure Seeding** | Traditional | 1v16, 2v15, basic same-league avoidance |
| **Regional** | Travel savings | Greedy nearest-neighbor matching (33-45% mileage reduction) |
| **OSAA Bracketing** | Full compliance | League champion guarantees + 3-move conflict resolution |

---

## Data & Validation

**Dataset**: 1,214 ranked teams, 5 seasons (2021-2025), all classifications
**Tiebreaker**: Head-to-head when teams within 2% Power Index (2024: 24-28 H2H adjustments/gender)
**Transparency**: All calculations traceable to source matches, complete methodology documentation

**Rankings validated against**:
- State tournament results (strong correlation)
- League championship history (depth scores align)
- Regional travel analysis (mileage savings confirmed)

---

## Key Advantages

✅ **Fair**: 50% schedule strength + 50% roster depth = balanced evaluation
✅ **OSAA-Compliant**: Implements all team sports playoff rules automatically
✅ **Transparent**: Documented methodology, no "black box" rankings
✅ **Travel-Optimized**: Regional mode saves 33-45% first-round travel miles
✅ **Defensible**: Every ranking decision has documented rationale
✅ **Easy to Use**: Static HTML dashboard, runs in any browser, no server needed

---

## Technical Summary

**Format**: Interactive HTML dashboard with JSON data export
**Browser Support**: Chrome, Firefox, Safari, Edge (all modern browsers)
**No Installation**: Self-contained static site, no backend required
**Audit Trail**: Complete ranking history with year-by-year comparison

**Core Files**:
- `index.html` — Interactive dashboard
- `public/data/processed_rankings.json` — Ranking data
- `docs/power-index-explained.md` — Full methodology

---

## Bottom Line

The Power Index combines traditional strength-of-schedule metrics with tennis-specific roster depth analysis to produce **fair, transparent, and OSAA-compliant rankings**. The playoff simulator automatically handles league champion home game guarantees and same-league conflict avoidance per official OSAA team sports rules.

**Ready for immediate use** in state tournament seeding and bracket generation with 5 years of validated data.

---

**Questions?** Full documentation available in `/docs/` directory
**System Status**: Operational for 2021-2025 seasons | Updated February 2026
