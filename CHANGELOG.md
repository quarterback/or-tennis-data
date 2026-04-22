# Changelog

## 2026-04-22

### Changed: Power Index now weights opponent strength by league depth (two-pass APR)

**Problem:** APR's OWP term (strength of schedule) averaged opponents' raw win percentages with no league context. That let teams dominating weaker leagues carry OWP scores indistinguishable from teams beating comparably-ranked opponents in deeper leagues — so Power Index rewarded weak-schedule wins and penalized top-bracket teams forced to play each other.

**Fix:** APR is now computed in two passes. Pass 1 uses the existing RPI formula to produce a first-cut APR, and those APRs feed a per-league depth score (top-4 APR average, already computed for the existing league-quality display). Pass 2 recomputes OWP using a league-depth-weighted opponent strength — each opponent's contribution is scaled by `opp_league_depth / median_league_depth` for that year+gender. The depth calculation uses leave-one-out: both the opponent and the team being evaluated are excluded, so a team can't inflate its own strength-of-schedule by being in its own league. OOWP, APR, and Power Index are then recomputed from the pass-2 OWPs. FWS is untouched, so the anti-stacking half of PI is unchanged.

**Impact on 2026:** Biggest Boys movement is Cascade (SD-2) #26→#32 and Marist Catholic (SD-2) #27→#33 dropping, with PIL teams (Wells, Franklin) and Three Rivers teams (Lakeridge) rising. Girls top-10 barely reshuffles — Wells moves up one, McMinnville down one — consistent with the top already being dominated by teams playing strong slates. Vale is unchanged at Girls #5 and rises to Boys #46 (from #42), which reflects their actual non-league slate rather than SD-5 alone.

### Fixed: Quality Wins calculation used drifting in-memory ranks instead of published weekly ranks

**Problem:** `generate_weekly_rankings.py` recomputed every prior week's rankings from scratch on each run and chained them through memory as the `prev_rankings` input for quality-win calculations. Because the underlying match data keeps evolving (new match ingests, tiebreaker corrections, schema updates), the retroactive "previous week" rankings drifted from what was actually published. The result was quality-win totals that didn't match the visible prior-week rankings — Marist Catholic's 6-2 win over Catlin Gabel (4A-1A #2 at the time) showed 0 quality wins instead of 1, and 20+ girls teams and 30+ boys teams had similar mismatches in the Week 3 snapshot. Earlier-week snapshots also still carried the pre-rename `top25_wins` field.

**Fix:** Weekly generation now treats the published `public/data/weekly/<date>.json` snapshots as the canonical source of prior-week ranks. When the loop starts a week and no prior ranks are held in memory (single-week runs, partial reruns), it loads them from disk via the new `load_published_week` helper. Full `--all` runs still chain in memory because each freshly-written snapshot matches what would be read back from disk. Regenerated all three 2026 weeks end-to-end to bring existing snapshots into agreement with the canonical rule; Marist Catholic now correctly shows 1 quality win in Week 3.

### Changed: Unified "Quality Wins" column on weekly rankings

**Problem:** The "Top 25 W" column on the weekly rankings page only counted wins against opponents ranked top-25 overall. Since the overall rankings skew toward 6A teams (who play each other more), teams in smaller classifications had no way to get credit for beating strong opponents within their own classification.

**Fix:** Replaced "Top 25 W" with a unified "Quality Wins" column that counts wins against opponents who were either top-25 overall *or* top-10 within their own classification at the time the match was played. A single win against an opponent who qualifies for both still counts as one quality win (no double-counting).

### Fixed: Tiebreaker wins/losses incorrectly reported as ties

**Problem:** When a dual match ended with equal flight scores (e.g., 4-4), Oregon uses a tiebreaker system (sets won, then games won) to determine a winner. The upstream data feed records these tiebreaker outcomes in a `winnerSchoolId` field, but oregontennis.org was ignoring it and only comparing flight scores — so every 4-4 match was reported as a tie, even when one team officially won the tiebreaker.

**Impact:** 126 team records corrected across 2024-2026 seasons. Examples from 2026:
- Westview Girls: 4-1-1 → 5-1-0
- Crescent Valley Girls: 4-0-1 → 5-0-0
- Ridgeview Boys: 3-0-3 → 5-1-0
- Nelson Boys: 5-1-1 → 6-1-0
- Valley Catholic Girls: 4-1-1 → 5-1-0

Some teams moved significantly in rankings as a result (e.g., Ridgeview Boys +21 spots, Sam Barlow Boys +15).

**Fix:** All four match-result functions (`get_dual_match_record`, `get_league_record`, `get_head_to_head`, `get_head_to_head_detailed`) now fall back to `winnerSchoolId` when flight scores are tied, matching the official tiebreaker outcome.

### Fixed: H2H boost not applying in overall state rankings

**Problem:** The head-to-head tiebreaker system had two phases: Phase 1 handled same-league teams (bubble swaps), Phase 2 checked adjacent pairs in the overall ranking. But when two same-classification teams had teams from other classifications ranked between them, they were never adjacent, so the H2H boost was never evaluated for the overall state ranking.

**Fix:** Added Phase 3 — classification-level H2H enforcement. Groups teams by classification and checks H2H for pairs within class rank or PI proximity, using bubble swaps. This catches 3-6 additional swaps per year/gender that were previously missed.

### Changed: Default table sort order

Rankings table now defaults to sorting by **Rank** (ascending) instead of Power Index (descending). This ensures the display order reflects H2H tiebreaker adjustments. A "Rank" button was added to the sort toggle alongside Power Index and APR.
