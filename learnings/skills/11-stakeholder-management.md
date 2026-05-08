# 11 — Stakeholder & Requirements Management

**One-line:** Constraints surfaced up front, explainability named as a
deciding factor, non-goals as first-class deliverables, and follow-up
plans named instead of pretending closure.

---

## Constraints surfaced up front

Every AAR opens with the site owner's explicit constraints *before*
describing the design.

From `AAR-power-index-ab-test.md`:

> The owner explicitly did **not** want to back-date any change ("would
> not do this retroactively"), did **not** want to remove FWS entirely
> (it captures a real signal — roster depth), and did not want to
> introduce an explicit "league strength" metric (OSAA doesn't use one).
> The fix needed to be implicit, schedule-aware, and forward-only.

From `AAR-toss-ogs-fold-in.md`:

> The site owner's explicit constraint was that the fix must not
> introduce a class-aware multiplier. No region or classification of the
> state should be hand-weighted up or down. The fix had to come from a
> signal already present in the data.

This is product-management muscle: capture the constraints, design within
them, *then* propose options. Skipping that step is how engineering and
stakeholders end up arguing about implementations that never had a chance
of being acceptable.

## Explainability as a deciding factor

From "Why TOSS (not QWS) as primary":

> **Smaller, more defensible change.** TOSS keeps the OSAA-compatible
> RPI APR intact and only adjusts how flight scores count. Explainable
> in one sentence to coaches. QWS replaces APR entirely with an iterated
> quality-weighted-wins formula — a structural change that's harder to
> defend mid-season without more data.

The structurally cleaner answer (QWS) loses to the more explainable
answer (TOSS). That's a mature engineering call — recognizing that a
ranking system has both a technical correctness dimension and a
political legitimacy dimension, and not treating the latter as someone
else's problem.

## Non-goals as first-class deliverables

Every AAR has a "What we didn't do" / "Non-goals (worth restating)"
section. From `AAR-toss-ogs-fold-in.md`:

> - **No change to FQI itself.** The flight-weight gradient and the
>   opponent multiplier on flight scores are unchanged.
> - **No change to APR.** APR is still the OSAA-style RPI.
> - **No change to historical seasons.** 2021–2025 use the 50/50 APR +
>   FWS formula they always have.
> - **No change to QWS or Legacy.** Both remain available via the Model
>   dropdown.
> - **No second-degree opponent weighting added explicitly.** OOWP is
>   already in APR.

Articulating what *isn't* changing is half the value of a design doc.
It tells the reviewer "you don't need to worry about X, Y, Z" — which
means they can spend their attention on what actually changed.

## Follow-up plans named instead of pretending closure

From `AAR-power-index-ab-test.md`, "What's next":

1. **Watch through end of season.** Each Sunday snapshot will preserve
   its TOSS-primary ranks plus `power_index_legacy` and
   `power_index_qws` for comparison.
2. **Decide for 2027.** With live evidence in hand we can keep TOSS,
   adopt QWS (possibly with a tuned loss penalty), or refine TOSS's
   clamp band. **No code change happens until we have data to argue from.**
3. **Coach feedback.** With the Model dropdown live on the main page,
   coaches can verify the switch themselves.

That last sentence — "no code change happens until we have data to argue
from" — is the right epistemic posture. The decision is open, and the
plan is to keep it open until evidence closes it.

## Multiple audiences, deliberately addressed

Each artifact is fit for a specific audience:

| Audience | Document | Genre |
|---|---|---|
| Engineering reviewers | AARs | Decision record + validation |
| Other states / sports | `docs/oFWS-PRD.md` | Portable spec (v1.0) |
| OSAA Committee (non-technical) | `memo_team_format_roster_analysis.md` | Policy memo with evidence tables |
| Coaches | `docs/power-index-explained.md`, `methodology.html` | Plain-English methodology |
| OSAA Champ Threshold Task Force | `docs/team-championship-proposal-v2.md` | Stakeholder proposal |

You don't try to use one document for all of them.

## Resume bullets specific to this skill

- *Surfaced stakeholder constraints up front in design documents
  ("don't back-date," "no class-aware multiplier," "preserve OSAA
  compatibility") and explicitly designed within them, treating
  political legitimacy as a first-class engineering concern alongside
  technical correctness.*
- *Authored decision-grade After-Action Reports (problem → options
  considered → what shipped → validation → non-goals → follow-ups) used
  by a non-technical site owner to evaluate live formula changes
  mid-season.*
- *Named explainability as a deciding factor between competing rating
  formulas, choosing the smaller defensible change over the
  structurally cleaner one when the latter could not be justified to
  coaches mid-season.*

## Where to grow

- Standing meeting / async cadence with the site owner — right now this
  reads like one-off document exchanges. A regular "what changed, what
  surprised us" rhythm scales better.
- Public methodology versioning — *"this site's rankings are computed
  per `methodology v3.2`"* — so coaches can pin to a version they
  understand.
- A short FAQ for common coach pushback ("why did my team move?",
  "why does FQI matter?"). Reduces the cost of every interaction.
