# A Fairer Way to Seed the OSAA Tennis Bracket

**What this is:** an interactive tool that rebuilds an OSAA-style individual tennis state draw so that **byes are earned by merit instead of handed out partly by lot**. It honors every OSAA/USTA separation rule, works for any number of special districts (4, 5, 6, 7, 8+), and recomputes team points under two scoring systems so you can see how much of the old point spread was an artifact of free byes. [Open the generator →](fair-bracket.html)

## The problem: a bye is worth points

OSAA's smaller-classification tennis bracket (4A/3A/2A/1A) takes the top four finishers from each special district. With five districts that is **20 entries dropped into a 32-line bracket — so 12 of them draw a first-round bye.**

That would be harmless if a bye were just a rest. It isn't. Team points are awarded by how deep you go, and a bye is a free step deeper. Worse, OSAA's own scoring rule spells out the inequity in black and white:

**"Each singles player or doubles team receives two (2) points for each win in the main draw … If a player receives a bye in the first round of the main draw, four (4) points are given only if the second-round match is won."**

Read that carefully. A player who **was handed a bye** and then wins one match banks **4 points**. A player who had to **play and win a first-round match** banks **2 points** for the very same single win. The bye is worth a free +2 — and in a 20-into-32 draw, twelve of those byes are floating around to be assigned.

## The symptom: a district's own placements get scrambled

Because the unseeded portion of the draw is filled "by lot," it is routine to see a single district's four qualifiers land like this:

| District finish | Got a first-round bye? |
|---|---|
| 1st (champion) | No — played round 1 |
| 2nd | **Yes** |
| 3rd | **Yes** |
| 4th | No — played round 1 |

Inside one district, the **champion and the fourth-place team play in, while the second- and third-place teams rest.** The team that *finished third* gets a structurally easier, higher-scoring path than the team that *won* that same district. Spread that across every district and the distortion is everywhere — and it compounds for schools that qualify several entries, since each extra entry is another lottery ticket for a free bye. None of that reflects how anyone played; it's purely where the lot dropped them.

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

## Why the bye points matter so much

Consider two hypothetical schools with the same on-court results. School A enters two extra teams that each happen to draw a first-round bye and win one match; School B enters two finalists who win their way through. Under the current rule, each of School A's bye-aided teams banks **4 points off a single win**, while a team that has to *play* its opening match banks **2 points for that same win**. A school that stacks low-seeded entries into bye lines can out-point a school whose entries actually went deeper — not because of the tennis, but because of where the lot dropped them.

The two fixes below each neutralize that:

- **Merit byes** make "round reached" an honest proxy again, because no 3rd/4th-place entry can draw a bye over a champion or a 2nd to begin with.
- **Per-win scoring** makes a bye worth zero, so a single win is one point for everyone.

Run any field through the tool and toggle Byes between *Merit* and *By lot*, or the scoring between *round-reached* and *per-win*: the team totals visibly compress as the free-bye points come out.

## What it does and doesn't claim

It does not predict winners, re-rank players, or argue any team was undeserving. It is a structural tool: given district finishes and the committee's seeds, it produces a draw whose byes track merit and whose point outcomes don't hinge on the luck of the lottery. The seeds shown are a stand-in (the champions of the first districts); plug in the real committee seeds and the rest of the draw falls out around them.

[Open the generator →](fair-bracket.html)
