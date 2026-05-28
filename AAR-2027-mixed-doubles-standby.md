# How the 2027 Mixed Doubles Standby List Works

**What this is:** an interactive tool that models the new event coming to OSAA tennis in 2027 — a **16-line mixed doubles bracket that replaces the consolation round** in each classification — and demonstrates the one piece of it that is genuinely new to the championship: a **public standby list** that fills the open bracket lines in real time as Round 1 plays out. It also models the **dual team finals** and prints a drop-in schedule. [Open the tool →](2027-format.html)

## The format in one paragraph

In the proposed 2027 format every classification runs a mixed doubles bracket in the slots the consolation round used to occupy. Pairs are **same-school**, and only **one partner has to be a state qualifier** — the other can be a rostered teammate who played the regular season and districts but didn't qualify (a "**+roster**" partner). Each class's tournament also ends with **dual team finals**: a Boys final and a Girls final, each an 8-match dual played to clinch. None of that needs new machinery except one thing — how do you fill a mixed bracket when half its entrants aren't known until their singles/doubles matches are over?

## The problem a standby list solves

A 16-line mixed bracket is set in two waves:

- **Automatic district bids** are submitted the Saturday after districts and seed the known part of the draw.
- The **remaining slots can't be filled yet**, because the pairs that want them contain qualifiers who are still alive in singles and doubles. A qualifier can't play mixed and singles at the same time, so a pair only becomes *available* once its qualifier(s) **lose** and free up.

The number of each depends on the classification:

| Class | Automatic district bids | Provisional (standby) slots |
|---|---|---|
| 6A | 14 | 2 |
| 5A | 8 | 8 |
| 4A | 10 | 6 |

This is exactly how a consolation bracket has always filled — losers drop in as they become known. The only difference is that here the order is **published in advance** so every school can watch the gate board during Friday's Round 1 and know precisely what has to happen for their pair to get in.

## How the list is ranked

When the bracket is published, every provisional pair is already on the list, ranked by:

1. **Tier 1 before Tier 2.** Tier 1 is a pair whose qualifier lost a round-of-32 (pigtail) match; Tier 2 lost a round-of-16 first match (a R32-bye entry, or a 16-draw like 5A that has no R32 at all). Losing earlier ranks you higher, because your slot frees up sooner.
2. **Weaker district finish first, within a tier.** A pair built around a 4th-place qualifier sits ahead of one built around a champion.
3. **Lot** breaks remaining ties, reproducibly from the draw seed.

A subtlety the tool makes concrete: a **one-qualifier pair** (qualifier + roster partner) is averaged with the +roster side counted as a district finish of 5. That deliberately lifts it above a **two-qualifier pair**, which is harder to activate because **both** of its sides have to lose Round 1 before it can clear.

## How a slot actually fills

As each Round 1 result posts, a pair's status flips:

- **Qualifier loses** → that side is *met*. Once every qualifier on the pair has lost, the pair is **eligible**. If a provisional slot is still open, it **clears straight into the bracket** in completion order — no bumping of pairs already placed.
- **Qualifier wins** → the pair **drops out** (the student is still alive in singles/doubles, which is the point). A two-qualifier pair drops the moment *either* side wins.
- **Slots full** → later-eligible pairs are held as **alternates**, eligible but with nowhere to go.
- **Pool runs dry** → any unfilled bracket line simply **plays as a bye**.

The tool shows this as an airport-style gate board with four sections — *cleared into the field*, *pending R1*, *alternates*, and *out* — and a header strip counting slots open / eligible / pending / out.

## Driving the tool

- **Classification** — 6A, 5A, or 4A, each with its real special districts and bid split.
- **Draw seed** — every draw, name, and lot tie-break is reproducible from this number (a seeded RNG), so a given seed always produces the same board.
- **Allow upsets** — by default Round 1 runs chalk (higher seed wins); tick this to coin-flip first-round results so you can watch the list reorder under upsets.
- **Generate / Step R1 → / Simulate R1 / Reset** — publish a fresh list, post results one match at a time to watch slots fill, run all of Round 1 at once, or clear back to the published state.
- **Click any qualifier chip** to flip its individual Round 1 result by hand and see the board recompute.

## The dual team finals

The second 2027 addition is modeled in its own panel. Each class's dual tournament ends with a **Boys final and a Girls final** at the state site — an 8-match dual (4 singles + 4 doubles) played **to clinch: first school to 5 wins takes the title**, and remaining matches are dead rubbers. Pick any two schools, click winners to cycle results, or simulate; the panel marks the clinch match and greys out the dead rubbers. A **schedule / info sheet** then lays out the running order — mixed doubles in the former consolation slots, dual finals on the pre-individual day — and prints.

## What's real and what's illustrative

The seeding math, separation rules, bracket topology, and standby logic are real. The **people are not**: all student names are fictional, while schools and special districts are real. Two parts of the data are necessarily made up because no published source exists:

- **Automatic mixed district bids** aren't regulated by OSAA and have no data, so the tool generates a plausible spread (up to two same-school pairs per district that fields both genders).
- **Dual finalists** are illustrative — no dual-bracket data exists — so you pick the two schools yourself.

## What it does and doesn't claim

It doesn't predict who will qualify or win. It's a structural demonstration: given a published bid split and a set of Round 1 results, it shows exactly how the new mixed bracket fills, in what order, and why — so the part of the 2027 format that has no precedent at the state level can be seen working before it's ever run for real.

[Open the tool →](2027-format.html)
