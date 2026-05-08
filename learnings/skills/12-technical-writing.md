# 12 — Technical Writing for Mixed Audiences

**One-line:** Five distinct genres of document, each fit for its audience —
AARs for engineering, PRDs for adopters, memos for committees,
methodology for coaches, changelogs as decision records.

---

## The five genres on display

### 1. Engineering AARs

`AAR-power-index-ab-test.md`, `AAR-toss-ogs-fold-in.md`. Repeatable
structure:

> What we did → Why → What we considered → What shipped → How we know
> it works → What's next → Files changed → Non-goals → References

This is the structure that distinguishes a *decision record* from a
*status report*. It tells a future reader (including yourself):

- The state of the world before.
- The constraints that were named.
- The options that were considered (and rejected).
- What was actually shipped.
- How correctness was validated.
- What was deliberately not done.
- What the open questions are.

You can lift this template into any team and it works.

### 2. Portable PRD (v1.0)

`docs/oFWS-PRD.md`. The Oregon-specific FQI metric is generalized to
oFWS — the same math, written so a different state or a different
racquet sport (badminton, squash) can adopt it without reading the
Oregon code.

Sections:
- Summary
- Problem this solves
- Goals and non-goals
- Design (core formula, layers, aggregation, two-pass computation)
- Classification-relative companion metric (FQI+)
- Edge cases & failure modes
- Field reference

Marked **Version: 1.0, Status: Implemented**. That's a portable
artifact — you could publish it as a blog post, send it to another
state's athletic association, or use it as a reference in a paper.

### 3. Policy memo to a non-technical committee

`memo_team_format_roster_analysis.md`. Memo format:

```
TO: OSAA State Championship Committee
FROM: Oregon Tennis Rankings Project
DATE: March 16, 2026
RE: Roster Size Analysis — Viability of Team Dual Match Format

Summary: ... only 4 boys programs and 2 girls programs ...
Findings: [tables]
Context: [methodology limitations, exclusions]
District Breakdown: [tables]
Conclusion: ... 86 (93%) had at least 6 players ... Accommodations
            for these programs (e.g., default/forfeit provisions for
            unfilled flights) could address the issue without
            preventing the remaining programs from competing.
```

Notice the conclusion: it doesn't just say "the data refutes your
concern." It names a workable accommodation. Persuasive policy writing
gives the decision-maker a path forward, not just a counterargument.

### 4. Coach-facing methodology

`docs/power-index-explained.md`, `docs/OSAA-One-Pager.md`,
`docs/OSAA-Executive-Summary.md`, the public `methodology.html`. Plain-
English explanations of formulas, with examples and traceable ranking-
decision rationale. The one-pager is one page, deliberately.

### 5. Changelog as decision record

`CHANGELOG.md` is not just a list of changes. Each entry is structured:

> **Problem:** Concrete user-visible trigger case.
> **Root cause:** What was broken and where.
> **Fix:** Specific change.
> **Impact:** Magnitudes — "466 teams across 139 (year, gender, league)
> groups going back to 2021."

Reading the changelog gives you the entire history of the system's
design decisions, not just what code shipped when.

## Stakeholder proposals

`docs/team-championship-proposal-v2.md`,
`docs/proposed-special-districts.md`,
`docs/regional-bracket-analysis.md`. Each follows a recognizable
proposal structure:

- What we're proposing.
- Comparable precedent (table of how OSAA already structures other sports).
- Cross-classification comparison (a comparative table is worth a thousand
  words).
- Specific recommendations.

The regional bracket analysis is particularly strong: it leads with the
quantitative result ("44.8% travel reduction in 4A/3A/2A/1A") and only
then explains the methodology. That's the right ordering for a
decision-maker.

## Resume bullets specific to this skill

- *Authored a portable Product Requirements Document (`oFWS PRD v1.0`)
  generalizing a sport-specific rating metric, formatted so other
  states or racquet sports could adopt the math without reading the
  Oregon implementation.*
- *Wrote decision-grade After-Action Reports following a repeatable
  structure (problem → options considered → what shipped → validation
  → non-goals → follow-ups), used as the basis for live mid-season
  formula promotions.*
- *Drafted a data-backed policy memo to the OSAA State Championship
  Committee that named a specific accommodation rather than only
  refuting the underlying concern.*
- *Maintained a changelog of structured incident records (problem →
  root cause → fix → impact with magnitudes), serving as the running
  decision history of the rating system.*

## Where to grow

- Publish the oFWS PRD somewhere reachable (a personal site, an OSAA-
  facing portal, a blog post). The doc is portable — let it travel.
- A "writing playbook" that codifies the AAR structure and the
  memo-to-committee structure for re-use on the next project. You've
  effectively invented an internal style guide; capture it.
- Practice condensation: the AAR-to-one-paragraph compression. Half the
  value of a long doc is the ability to extract its lead sentence.
