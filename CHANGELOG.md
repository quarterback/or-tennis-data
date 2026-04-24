# Changelog

## 2026-04-24

### Added: Power Index A/B test (TOSS + QWS) and Sunday publish cadence

**What:** The main rankings table now has a Model dropdown (Current / TOSS / QWS) that swaps the displayed Rank, Class Rank, and Power Index between three formulas computed in parallel from 2026-04-20 forward. The Current model is the default and continues to drive the playoff simulator, head-to-head, and league standings. Weekly publishing also shifts from Saturdays to Sundays starting 2026-04-26 so Saturday match results are included in that week's snapshot. Historical seasons (2021-2025) and the three already-published Saturday weekly snapshots are unchanged.

**Why:** The current Power Index over-rewards dominant flight scores against weak-league opponents because FWS has no opponent-strength awareness. Two design approaches surfaced — TOSS (opponent-APR-weighted FWS) and QWS (ITA-style quality-weighted APR) — and rather than pick one blind, we're running both alongside the unchanged baseline through end of season to compare on live data.

**Detail:** See the [Power Index A/B Test AAR](aar-power-index-ab-test.html) for the full design, math, validation results, and rollout plan. The [methodology page](methodology.html#ab-test) has user-facing explanations of all three formulas.

### Fixed: Duplicate dual matches inflated team records and rankings

**Problem:** Some teams showed inflated win or loss totals because both coaches posted the same dual match to tennisreporting.com, producing two distinct meet entries. The reported trigger case was Valley Catholic girls at **7-2-0** vs. Molalla girls at **6-4-0** on 2026-04-07; both teams had the April 7 VC-vs-Molalla match counted twice. An audit across 2021-2026 found 51 duplicate match pairs affecting 92 school files.

**Root cause:** Every meet-iteration site (`get_dual_match_record`, `get_league_record`, `get_head_to_head`, `get_head_to_head_detailed`, `process_school_data`, FWS calculation, and the weekly match graph) consumed the raw `data['meets']` array without checking for duplicate `(date, team_a, team_b)` entries. `scripts/generate_weekly_rankings.py::extract_matches` had a partial guard, but it only gated `match_list`; `match_graph`, `team_records`, `team_top_flight`, and `team_match_log` were all written before the dedup check.

**Fix:** Added a `dedupe_meets()` helper to `generate_site.py`, `scripts/build_rankings.py`, and `scripts/generate_weekly_rankings.py` that collapses any pair of dual meets with the same date and same two school IDs, keeping the entry with the most completed flight match data (ties broken by lowest meet id). The dedup runs once at load time, so every downstream consumer sees the cleaned `meets` list. Non-dual meets (tournaments, state championships) are untouched.

**Impact:** Valley Catholic girls 2026: 7-2-0 -> 6-2-0. Molalla girls 2026: 6-4-0 -> 6-3-0. 106 duplicate meet entries removed across the 2021-2026 history, correcting records, league standings, head-to-head tables, FWS, OWP, and weekly composite rankings.

## 2026-04-23

### Fixed: Weekly rankings counted tiebreaker losses as ties

**Problem:** La Salle Prep girls' record on the weekly rankings page read **3-2-5** while OSAA and the main site both reported **4-5-2**. Three of the five "ties" were 4-4 meets the Oregon tiebreaker awarded to the opponent — Summit, Hood River Valley, and Crescent Valley — and one missing win was simply a later-dated match. Every team's weekly record that included a tiebreaker outcome was off by the same pattern.

**Root cause:** `scripts/generate_weekly_rankings.py::extract_matches` inferred a team's result purely from flight scores (`won = my_score > opp_score`) and treated any 4-4 as a tie, ignoring the `winnerSchoolId` field that tennisreporting.com sets based on the Oregon tiebreaker (sets won, then games won). The canonical `get_meet_result` in `generate_site.py` already handled this correctly — the weekly pipeline had a divergent copy.

**Fix:** Added a tiebreaker-aware `get_meet_result` helper to the weekly script mirroring the site version, switched `extract_matches` to tri-state `won` (True/False/None, where None marks a true tie with no `winnerSchoolId`), and updated `scripts/computer_rankings.py` so Elo, Colley, PageRank, and Win-Score handle ties explicitly (0.5 credit each way) instead of implicitly via the `margin==0` sentinel that could no longer distinguish a tiebreaker loss from a true draw. Regenerated all three 2026 weekly snapshots; a full cross-check confirms every team's weekly W-L-T now matches `processed_rankings.json` exactly.

## 2026-04-22

### Fixed: Tournament-format dual matches dropped from team records

**Problem:** Lincoln (Portland, OR) boys showed **4-0** on the site while tennisreporting.com reported **8-0-0**. The four "missing" wins were all titled *Caldera Tournament*. Follow-up audit found nine other schools similarly under-counted, including Bend boys (displayed 4-3-1 vs. API 8-3-1), Roseburg boys (displayed 6-3-2 vs. API 10-3-2), and South Medford boys (displayed 4-4 vs. API 8-4).

**Root cause:** `is_dual_match()` in `generate_site.py` dropped any meet whose title contained the word "Tournament". In the 2026 data, every "Tournament" meet is actually a single head-to-head dual match (one winner, one loser, full per-flight scores) — events like the Caldera Tournament, Roseburg Invitational Tournament, and RHS Tournament are scheduled as clusters of dual matches played in one location, and tennisreporting.com's own `overallRecord` counts each one. The blanket title filter was a blunt instrument that excluded them from record totals, league standings, head-to-head tables, RPI opponent sets, and FWS.

**Fix:** Removed the `'Tournament' in title` check. The existing structural guard at the bottom of `is_dual_match()` (one winner, one loser) still filters out genuinely multi-team events — e.g., the `OES Invitational` (1 winner, 3 losers) remains correctly excluded as a points-based event.

**Impact:** Ten 2026 boys teams and their opponents now reconcile exactly with tennisreporting.com's `overallRecord`. A full pass across all 264 schools × 2 genders shows **0 remaining record mismatches**, ties included. Lincoln boys moved from rank uncertain to rank #1 at 8-0-0. Upcoming events the season will see — Jesuit Tournament, Central Oregon Invite, Roseburg Tournament, Bigfoot Invitational — are all handled by this same change, because each appears in the feed as a set of 1v1 dual matches.

### Fixed: Massey column silently ranked teams by school_id when match graph was disconnected

**Problem:** The Massey column on the weekly rankings was nonsense whenever the match graph had more than one connected component, which has been the case for every 2026 girls week published so far. On the 2026-04-18 snapshot, Jesuit girls (9-0, consensus #1 everywhere else) appeared at Massey #117 out of 127, while Vale, Stayton, Century, Hillsboro, and Glencoe occupied Massey #1-5. The ordering was not tennis at all — it was school_id ascending.

**Root cause:** `massey_rankings` in `scripts/computer_rankings.py` builds an n×n Laplacian-style matrix `M` whose row sums are zero, then replaces the last row with a sum-to-zero constraint to pin the solution. That constraint lifts the rank by one — fine for a connected graph, but the 2026 girls graph has two components (one small-school cluster never played outside itself), so post-constraint `M` is still rank n-1, not n. `np.linalg.solve` raised `LinAlgError`, the `except` branch set every rating to 0.0, and then `ratings_to_ranks` did a stable descending sort. Stable sort on all-equal keys preserves insertion order, which comes from `teams = sorted(match_graph.keys())` — i.e., school_id. Jesuit's school_id 124879 happens to sit 117th in that order. The same failure mode will have silently hit any prior gender/year whose match graph ever fragmented.

**Fix:** Swapped `np.linalg.solve(M, p)` for `np.linalg.lstsq(M, p, rcond=None)`, which returns the minimum-norm least-squares solution even when `M` is singular. Each connected component gets its own self-consistent Massey ratings (centered near zero by the sum-to-zero row) rather than collapsing everything to 0. Regenerated all three 2026 weekly snapshots; Jesuit girls is now Massey #1 in weeks 2 and 3 (matching Elo/Colley/PageRank/Win-Score) and Massey #1 in week 1 before other systems had enough match history to converge. Tradeoff: ratings across disconnected components are not strictly comparable, but that is already true of Massey on disconnected data in theory, and the new behavior is vastly closer to truth than "sort by school_id."

### Fixed: Playoff simulator could seed the same school twice

**Problem:** On the Playoff Simulator page, the home-game-guarantee step could place the same league champion at two different seeds. Example from 4A/3A/2A/1A Girls 2026 with an 8-team bracket: Marist Catholic appeared as AUTO at both seed 4 and seed 6, while another team was silently dropped from the field. The "First 4 Out" list and first-round matchups both reflected the corrupted field.

**Fix:** The loop that moves league champions up into home-game seeds (`generate_site.py` inside `generatePlayoffFieldFromSelection`) captured each mover's array index before any mutations, then used those stale indices to `splice(fromIdx, 1)`. After the first insertion at `lastHomeGameSeed - 1` shifted every element to the right of it, the next splice removed the wrong team — and re-inserted a champion that was still in the array, producing the duplicate. Movers are now pulled out of the field by `school_id` and reinserted as a contiguous block at the last home-game seed, and each champion's reported "moved from X to Y" uses its actual final seed instead of a fixed target. No duplicates can appear in the qualifying field, and no unrelated team is dropped.

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
