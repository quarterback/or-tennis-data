# 01 — Sports-Rating System Design

**One-line:** Designed and implemented multiple rating formulas from first
principles — RPI variants, opponent-weighted flight metrics, iterated
quality-weighted models, and five computer-ranking algorithms — and
composed them into a multi-pass pipeline.

---

## What you built

| Metric | What it measures | Where |
|---|---|---|
| **APR** (RPI-style) | `WP·0.25 + OWP·0.50 + OOWP·0.25` | `generate_site.py:39–43` |
| **Two-pass APR** | OWP reweighted by leave-one-out league depth | `generate_site.py:72–76`, `loo_depth` at `:148` |
| **FWS** (Flight-Weighted Score) | Roster depth via per-flight weights S1/D1=1.00 → S4/D4=0.10 | `generate_site.py:24–34`, `:731` |
| **FQI / oFWS** | Opponent-APR-weighted flight score | `generate_site.py:1141–1162`, spec in `docs/oFWS-PRD.md` |
| **oGS** | Opponent-weighted game share, set-type-aware | `generate_site.py:844–865`, `:1164–1182` |
| **TOSS** | `0.65·APR + 0.25·FQI + 0.10·oGS` composite | `generate_site.py:49–53` |
| **QWS** | Iterated ITA-style quality-weighted APR | `generate_site.py:1190–1227` |
| **Elo / Colley / Massey / PageRank / Win-Score** | Five computer rankings → composite | `scripts/computer_rankings.py` |

## Anti-gaming mechanisms layered into the design

- **High-flight weighting** in FWS discourages "stacking" a star at a low
  flight to inflate W/L.
- **Opponent multiplier** on FQI/oGS removes the hidden penalty for playing
  strong schedules.
- **Leave-one-out league depth** prevents a team from inflating its own
  strength-of-schedule by being in its own league.
- **Set-type-aware game accounting** stops a 10-7 super-tiebreaker from
  being weighted as 17 games against a regular 6-2 set.

## Resume bullets specific to this skill

- *Designed and shipped a multi-model sports-rating system (RPI,
  opponent-weighted Flight Quality Index, opponent-weighted Game Share,
  iterated Quality-Weighted Wins) operating as a forward-only A/B test on
  live data.*
- *Authored a portable Product Requirements Document (`oFWS PRD v1.0`)
  generalizing the opponent-weighted flight metric so other states or
  racquet sports (badminton, squash) can adopt the same approach.*
- *Built a five-system computer-ranking pipeline (Elo, Colley, Massey,
  PageRank, Win-Score) producing composite rank with median and
  standard-deviation diagnostics.*

## Where to grow

- Read the underlying literature: Bradley-Terry, Massey's original 1997
  thesis, Colley 2002, PageRank for sports (Govan/Langville/Meyer).
- Move from rank-correlation validation to predictive evaluation
  (out-of-sample Brier score, calibration curves on prior seasons).
