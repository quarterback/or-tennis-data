# 06 — Root-Cause Data-Quality Work

**One-line:** Diagnosed six distinct user-visible data bugs by tracing each
to the actual line where the wrong value was set, then fixed every
downstream consumer in lockstep.

---

## The six bugs (each with a real trigger case)

### 1. Duplicate dual matches inflated records

**Trigger:** Valley Catholic girls 7-2-0 vs Molalla 6-4-0 — both teams
counted the April 7 match twice. Audit found 51 duplicate pairs across
92 school files.

**Root cause:** Every consumer (`get_dual_match_record`,
`get_league_record`, `get_head_to_head`, `get_head_to_head_detailed`,
`process_school_data`, FWS calculation, the weekly match graph) read raw
`data['meets']` without checking for duplicates.

**Fix:** `dedupe_meets()` keyed on `(date, sorted(school_ids))`,
applied once at load time so every downstream consumer sees the cleaned
list. Tiebreaker: keep the entry with the most flight match data, then
lowest meet id (`generate_site.py:351–398`).

### 2. Tournament-format duals dropped from records

**Trigger:** Lincoln boys showed 4-0 on the site while the API said
8-0-0. The four "missing" wins were all titled *Caldera Tournament*.

**Root cause:** `is_dual_match()` blanket-filtered any title containing
"Tournament," but in the 2026 data every "Tournament" meet was actually
a single head-to-head dual match.

**Fix:** Removed the title check. The structural guard (1 winner, 1
loser) at the bottom of `is_dual_match()` still excludes genuine
multi-team events like *OES Invitational* (1 winner, 3 losers).

### 3. Tiebreaker losses miscoded as ties

**Trigger:** La Salle Prep girls weekly record read 3-2-5; OSAA and the
main site both reported 4-5-2. Three of the five "ties" were 4-4 meets
the Oregon tiebreaker awarded to the opponent.

**Root cause:** `extract_matches` in the weekly script inferred results
purely from flight scores (`won = my_score > opp_score`), ignoring the
`winnerSchoolId` field that tennisreporting.com sets based on the Oregon
tiebreaker. The canonical `get_meet_result` in `generate_site.py`
already handled this — the weekly pipeline had a divergent copy.

**Fix:** Added a tiebreaker-aware `get_meet_result` to the weekly
script mirroring the site version, switched to tri-state `won` (True /
False / None for true draws), and updated `computer_rankings.py` so
Elo, Colley, PageRank, and Win-Score all handle ties explicitly.

### 4. League rank stale after H2H tiebreaker swaps

**Trigger:** League standings showed a team at league rank #1 while the
same team sat *below* a league-mate in the overall state ranking.
Affected 466 teams across 139 (year, gender, league) groups going back
to 2021.

**Root cause:** `school_league_rank` was built once from the initial PI
sort (used as a *condition* for the H2H swap pass), then never
recomputed after the swap pass reordered teams.

**Fix:** Rebuild `school_league_rank` from the post-swap order. State
rank and league rank are now monotonic within every league.

### 5. Massey ranked teams by school_id (the textbook one)

**Trigger:** Jesuit girls 9-0 sat at Massey #117 of 127.

**Root cause:** Disconnected match graph → singular Laplacian → solver
raised → except clause set every rating to 0.0 → stable sort fell back
to insertion order (school_id ascending).

**Fix:** `np.linalg.lstsq` for minimum-norm solution per connected
component. (Detailed in [03-numerical-methods.md](03-numerical-methods.md).)

### 6. Quality-wins drift

**Trigger:** Marist Catholic's 6-2 win over Catlin Gabel (4A-1A #2 at
the time) showed 0 quality wins instead of 1.

**Root cause:** `generate_weekly_rankings.py` recomputed every prior
week's rankings from scratch and chained them through memory. As
underlying match data evolved, the retroactive "previous week" rankings
drifted from what was actually published.

**Fix:** `load_published_week()` reads
`public/data/weekly/<date>.json` as the canonical source of prior-week
ranks (`scripts/generate_weekly_rankings.py:101–115`). Single-week
runs and partial reruns now load from disk; full `--all` runs still
chain in memory (which matches what would be read back from disk).

## The pattern across all six

Each fix has the same shape:

1. **Specific user-visible trigger case** named.
2. **Root cause** identified at the line where the wrong value was set.
3. **Fix** applied at the right level of the stack (load-time dedup,
   not per-consumer dedup; canonical published artifact, not a memory
   chain).
4. **Lockstep update** across every consumer that touched the buggy
   path. The `winnerSchoolId` fix updated four match-result functions
   plus all five computer-ranking algorithms.
5. **Magnitudes reported** in the changelog: 466 teams, 51 pairs, 92
   files, 106 entries.

## Resume bullets specific to this skill

- *Diagnosed and fixed six distinct data-quality bugs in a multi-year
  sports-rating pipeline, each traced to the specific line where the
  wrong value was set, with magnitude reporting (466 teams across 139
  groups going back to 2021) in the changelog.*
- *Authored a load-time deduplication pass that consolidated 51
  duplicate dual-match pairs affecting 92 school files, ensuring every
  downstream consumer (records, league standings, head-to-head, RPI,
  flight-weighted score) saw a single cleaned source.*
- *Identified and corrected silent algorithmic failures (singular
  matrices, divergent function copies, stale derived state after a
  reorder pass) where the bug was not in the obvious code path.*

## Where to grow

- A test fixture per bug — "would the test suite have caught this?" is a
  productive lens.
- Schema validation at ingest (`pydantic` or `cerberus`) so feed changes
  surface as parse errors, not silent zeros.
- Reconciliation reports: a daily cross-check that team records match
  the upstream feed's `overallRecord` for every team. The Lincoln
  Tournament bug existed for a while before someone noticed.
