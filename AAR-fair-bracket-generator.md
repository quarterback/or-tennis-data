# A Fairer Way to Seed the OSAA Tennis Bracket

**What this is:** an interactive tool that rebuilds an OSAA-style individual tennis state draw so that **byes are earned by merit instead of handed out partly by lot**. It honors every OSAA/USTA separation rule, works for any number of special districts (4, 5, 6, 7, 8+), and recomputes team points under two scoring systems so you can see how much of the old point spread was an artifact of free byes. [Open the generator →](fair-bracket.html)

## The problem: a bye is worth points

OSAA's smaller-classification tennis bracket (4A/3A/2A/1A) takes the top four finishers from each special district. With five districts that is **20 entries dropped into a 32-line bracket — so 12 of them draw a first-round bye.**

That would be harmless if a bye were just a rest. It isn't. Team points are awarded by how deep you go, and a bye is a free step deeper. Worse, OSAA's own scoring rule spells out the inequity in black and white:

**"Each singles player or doubles team receives two (2) points for each win in the main draw … If a player receives a bye in the first round of the main draw, four (4) points are given only if the second-round match is won."**

Read that carefully. A player who **was handed a bye** and then wins one match banks **4 points**. A player who had to **play and win a first-round match** banks **2 points** for the very same single win. The bye is worth a free +2 — and in a 20-into-32 draw, twelve of those byes are floating around to be assigned.

## The smoking gun: Special District 3, 2026 doubles

Here is how the byes actually fell for one district's doubles teams in the real 2026 girls draw:

| District finish | Team | Got a bye? |
|---|---|---|
| 1st (champion) | Cohee / Mahar | No — played round 1 |
| 2nd | Ravassipour / Olson | **Yes** |
| 3rd | Hung / Ho | **Yes** |
| 4th | Smith / Clark | No — played round 1 |

Inside a single district, the **champion and the fourth-place team had to play in, while the second- and third-place teams rested.** A team that finished third in its district got a structurally easier, higher-scoring path than the team that won that same district. Draw that "by lot" across five districts and the distortion is everywhere — and it compounds for schools that qualify several entries, since each extra entry is another lottery ticket for a free bye.

## The fix: rank everyone once, then give byes top-down

The tool builds a single **merit order** for the whole field:

**seeds → district champions → 2nd-place → 3rd-place → 4th-place**

Byes are then assigned strictly down that list. No fourth-place team ever draws a bye before a champion does. With 20 entries and 12 byes, that is the four committee seeds, the remaining district champions, all five runners-up, and then the two best third-place teams — and the bottom eight (the rest of the 3rds and 4ths) play a first-round qualifier, exactly as a fair draw should.

The unavoidable wrinkle is honest math: 20 entries don't divide cleanly into powers of two, so **some** tier has to be split (here, two of five third-place teams get byes and three don't). The point isn't to pretend that goes away — it's to **confine the split to a single adjacent tier, decided on merit, instead of scattering free byes across champions and runners-up by chance.**

Every OSAA separation rule is enforced while this happens:

- Players/teams from the same district can't meet in the first round.
- Players from the same school can't meet before the semifinals (so a school's entries are spread across different quarters — which also prevents a multi-entry school from stacking an easy region).
- A school's district 1st and 2nd finishers can't meet before the final.

## It generalizes

The same engine works for any field size, because it derives the bracket from the entry count:

| Districts (×4 qualifiers) | Entries | Bracket | Byes |
|---|---|---|---|
| 4 | 16 | 16-line | 0 |
| 5 | 20 | 32-line | 12 |
| 6 | 24 | 32-line | 8 |
| 7 | 28 | 32-line | 4 |
| 8 | 32 | 32-line | 0 |

Verified across all of these: zero separation-rule violations, and in merit mode every bye goes to a higher-ranked entry than every play-in entry. Flip the toggle to "by lot" and the tool flags the inversions the current procedure can create.

## Two ways to keep score

The generator runs a chalk simulation (higher merit wins) and tallies team points under both:

- **Round-reached (legacy):** the OSAA system above, where a bye can convert one win into four points.
- **Per-win:** one point per match actually won, plus a small podium bonus, and **a bye is worth zero** — because you have to win a match to score.

Per-win is the simpler, more honest fix: it makes the unavoidable byes point-neutral, so it no longer matters who gets them. The structural merit-bye draw is the answer if you want to keep the legacy point table.

## A worked example: 2026 4A/3A/2A/1A girls

The real tournament is a clean illustration. Marist Catholic won the team title with **28 points** to Catlin Gabel's 19 — a nine-point solo championship. Now rescore the exact same results under main-draw per-win plus a 4-3-2-1 podium bonus, leaving the consolation bracket at its real value (capped at 2):

| Team | Official | Per-win + 4-3-2-1 (+ consolation) |
|---|---|---|
| Marist Catholic | 28 | 15 |
| Catlin Gabel | 19 | 15 |
| St. Mary's, Medford | 15.5 | 9.5 |
| Oregon Episcopal | 12 | 8 |

The nine-point runaway becomes a **15–15 tie** — and because OSAA shares team titles, that's a **co-championship**, not a tiebreak: Marist and Catlin Gabel both first, no second place, St. Mary's third. The swing is entirely the first-round bye points. Four Marist entries drew a bye and won one match for four points each; Catlin Gabel had two. Once a win has to be a win, Catlin Gabel's two finalists (champion Perez/Mehta and runner-up Shah) match Marist's champion-plus-depth — and under the merit-bye draw, Marist's **third- and fourth-place** district doubles teams would not have drawn byes in the first place.

None of this is a knock on the teams — they played the bracket they were given, and they won it. The point is narrower: **the bracket and its bye points, not the tennis, produced the margin.**

## What it does and doesn't claim

It does not predict winners, re-rank players, or argue any team was undeserving. It is a structural tool: given district finishes and the committee's seeds, it produces a draw whose byes track merit and whose point outcomes don't hinge on the luck of the lottery. The seeds shown are a stand-in (the champions of the first districts); plug in the real committee seeds and the rest of the draw falls out around them.

[Open the generator →](fair-bracket.html)
