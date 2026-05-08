# 10 — Domain Modeling

**One-line:** Tennis-specific scoring rules, flight weights, and tri-state
match outcomes encoded as first-class types — readable by a coach, not a
translation from a generic data model.

---

## Domain primitives are first-class

`generate_site.py:24–34`:

```python
FLIGHT_WEIGHTS = {
    ('Singles', '1'): 1.00,
    ('Singles', '2'): 0.75,
    ('Singles', '3'): 0.25,
    ('Singles', '4'): 0.10,
    ('Doubles', '1'): 1.00,
    ('Doubles', '2'): 0.50,
    ('Doubles', '3'): 0.25,
    ('Doubles', '4'): 0.10,
}
```

Per-flight stats keyed `S1`/`S2`/`D1`/etc. These names map directly to
how a coach talks. A reader who knows tennis can read the data
structures without a translation layer.

The TypeScript side mirrors this in `src/types.ts` so the same domain
vocabulary holds across the stack.

## Tennis-specific scoring rules encoded explicitly

From `generate_site.py:844–865`, three rules for game accounting:

1. **Best-of-3 sets and 8-game pro sets** contribute raw game totals.
   A 6-4, 6-2 flight contributes 12 games to the winner, 6 to the loser.
2. **Regular-set tiebreaker** (the 7-6 case) counts as a single deciding
   game for the set winner, not the raw tiebreaker point total.
3. **Match tiebreaker** (the 10-point super-TB that replaces a third
   set when sets are split 1-1) counts as one game to the winner and
   zero to the loser. A 10-7 super-TB is one decision, not 17 games.

The detection is one line:

```python
is_match_tb = (n >= 3) and len(vals) >= 2 and max(vals) >= 10
```

Without the super-TB rule, third-set tiebreakers would be weighted 17×
the influence of a regular game and the metric would surface a class of
artifacts — players who happen to play a lot of third-set super-TBs.

## Tri-state result type

`generate_site.py:401–444`. Returns `'win' | 'loss' | 'tie'`, with
explicit fallback to `winnerSchoolId` only when scores are tied:

```python
if school_score > opponent_score:
    return 'win'
elif school_score < opponent_score:
    return 'loss'

# Scores tied — check winnerSchoolId (tiebreaker: sets, then games)
winner_school_id = meet.get('winnerSchoolId')
if winner_school_id is not None:
    return 'win' if winner_school_id == school_id else 'loss'

return 'tie'
```

Returns `None` on missing data — distinguishes "couldn't tell" from
"true tie." That distinction propagates all the way through the five
computer-ranking algorithms.

## Proportional weighting for forfeits

`calculate_fws_per_match` at `generate_site.py:731`. Per-match
denominator is the sum of weights of flights *contested*, not a fixed
`MAX_FWS = 3.95`:

> Full match (8 flights): Denominator = 3.95
> Short match (1S, 2S, 1D, 2D only): Denominator = 3.0 (1.0+0.75+1.0+0.5)

A team is not penalized when the *opponent* forfeits — their score is
divided by what was actually contested.

## Defensive against upstream variability

- **Flight ID polymorphism**: `s.get(str(my_tid))` falls back to
  `s.get(my_tid)` because the upstream feed sometimes serializes team
  IDs as strings, sometimes as ints (`generate_site.py:851`).
- **School name overrides**: `_SCHOOL_NAME_OVERRIDES = {'Ida B.
  Wells-Barnett High School': 'Wells'}` — codifies one-off naming
  decisions instead of doing replacements at display time.
- **Title-case repair**: ALL-CAPS school names get titled
  (`name == name.upper() and len(name) > 2`).

## Resume bullets specific to this skill

- *Modeled tri-state match outcomes (`win | loss | tie`) end-to-end
  across five ranking algorithms, distinguishing tiebreaker-decided
  results from true draws and propagating the distinction through Elo
  updates, Colley's right-hand side, PageRank authority distribution,
  and Win-Score credit assignment.*
- *Encoded set-type-aware game accounting (best-of-3, 8-game pro sets,
  7-point set tiebreakers, 10-point match tiebreakers) so a single
  super-tiebreaker decision doesn't dominate season-long game-share
  statistics 17× over a regular game.*
- *Designed proportional-weighting flight-score normalization so a team
  is not penalized for an opponent's forfeit — per-match denominator is
  the sum of contested-flight weights rather than the theoretical
  maximum.*

## Where to grow

- A `Match` dataclass instead of dict-of-dicts. Right now the upstream
  JSON shape leaks throughout the pipeline.
- An ADT for `MatchResult = Win | Loss | Tie | Unknown` (or a Python
  enum) instead of strings + `None`.
- Player-level modeling — currently everything is team-aggregated.
  Adding per-flight player ratings would unlock individual rankings.
