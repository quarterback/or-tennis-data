# Learning Plan — Quarterly Sequencing

The six learning goals from the compendium, sequenced into quarters,
each grounded in something this project already does empirically. The
plan assumes hobbyist pace — a few hours a week — and prioritizes
depth over breadth. Each quarter has one primary goal, one secondary,
and an artifact to ship.

The point of every quarter is the **artifact**. If nothing leaves the
quarter, the learning didn't happen.

---

## Q1 — Formalize the rating-system literature

**Primary goal:** Read the source papers behind the algorithms you've
already implemented, and write them up against your code.

**Secondary goal:** Improve the test coverage on the pure helpers so the
literature reading can include "what's the textbook variant of this,
and would my code break if I switched?"

### Reading list (in order)

1. **Massey, K. (1997).** *Statistical Models Applied to the Rating of
   Sports Teams.* The original thesis. You've implemented Massey
   ratings; the paper explains the linear-system framing and the
   options for the constraint row. Connects directly to the disconnected-
   graph bug you already fixed.
2. **Colley, W. (2002).** *Colley's Bias-Free College Football Ranking
   Method.* Short, accessible, derives the `(2I+C)r = 1+½(w-l)` system
   directly. You'll recognize every step.
3. **Govan, A., Langville, A., Meyer, C. (2008).** *Offense-Defense
   approach to ranking team sports.* PageRank-flavored sports ranking.
   You implemented win/loss PageRank already; this paper goes further
   with offense/defense decomposition.
4. **Glickman, M. (1995).** *The Glicko System.* Introduces rating
   reliability — your empirical-Bayes shrinkage is the kindergarten
   version of what Glicko does formally.
5. **Cattelan, M., Varin, C., Firth, D. (2013).** *Dynamic Bradley-Terry
   Modelling of Sports Tournaments.* Connects paired-comparison models
   to time-evolving team strength.

### Artifact to ship

A `docs/rating-systems-reading-notes.md` that, for each paper, has:
- One-paragraph summary.
- One paragraph on how your implementation matches or differs.
- One specific code-level question it raises about your code.

### Side quest

Stand up a `tests/` directory with pytest. Target the obvious wins:
- `test_dedupe_meets.py` — duplicate detection, tiebreaker behavior.
- `test_get_meet_result.py` — tri-state, tiebreaker fallback.
- `test_computer_rankings.py` — Massey on a disconnected graph (the
  regression test for the bug you fixed!).
- `test_toss_is_primary.py` — gate behavior across dates and env vars.

This is the smallest possible test suite that catches the bugs you
already shipped fixes for.

---

## Q2 — Predictive evaluation of ranking changes

**Primary goal:** Move from rank-correlation + spot checks to
predictive validation. Did TOSS forecast playoff outcomes better than
Legacy in 2024 and 2025?

**Secondary goal:** Quasi-experimental causal language — read enough
about interrupted time series to talk about a 2026 model promotion in
terms a statistician would recognize.

### What this looks like in practice

For 2024 and 2025 (where you have full-season data and known playoff
outcomes), retroactively compute TOSS, QWS, and Legacy power-indexes
weekly. For each playoff matchup, the model predicts the higher-rated
team wins. Score with:

- **Accuracy** — fraction of correct calls.
- **Brier score** — calibration, not just direction. Requires turning
  PI into a win probability (logistic on PI difference is fine to
  start).
- **Log-loss** — penalizes overconfident wrong calls.
- **Calibration plot** — buckets of predicted probability vs realized
  win rate.

### Reading list

1. **Hosmer, Lemeshow, Sturdivant.** *Applied Logistic Regression* —
   the relevant chapters on calibration, ROC, Brier. Skim, don't read
   cover-to-cover.
2. **Bertsimas, Kallus.** *From Predictive to Prescriptive Analytics*
   for the framing of "what does a calibrated forecast unlock?"
3. **Bernal, Cummins, Gasparrini (2017).** *Interrupted time series
   regression for the evaluation of public health interventions: a
   tutorial.* Short, generalizable to formula promotions.

### Artifact to ship

A `docs/predictive-evaluation-2024-2025.md` with:
- One paragraph framing the question.
- Brier scores and calibration plots for each model.
- Conclusion: did TOSS justify its promotion in retrospect?

This is the doc that closes the loop on Q4-2026's "decide for 2027 with
evidence."

---

## Q3 — Production-grade Python data engineering

**Primary goal:** Refactor `generate_site.py` into a `pipeline/` package
with type-checked dataclasses, separate templates, and a meaningful
test suite.

**Secondary goal:** Schema-validate the upstream feed so feed shape
changes surface as parse errors, not silent zeros.

### What this looks like

Target structure:

```
pipeline/
├── __init__.py
├── ingest.py          # is_dual_match, dedupe_meets, get_meet_result
├── flight_score.py    # calculate_fws_per_match
├── apr.py             # two-pass APR with LOO league depth
├── toss.py            # FQI, oGS, TOSS computation
├── qws.py             # iterated quality-weighted APR
├── h2h.py             # three-phase tiebreaker
├── output.py          # JSON serialization
└── models.py          # dataclasses: Match, Meet, TeamSeason, etc.

templates/
├── index.html.j2
├── methodology.html.j2
└── ...

cli/
└── generate.py        # main()

tests/
└── ...
```

Use **pydantic** or **dataclass + cattrs** for the domain models. Use
**Jinja2** for the templates. Move every constant to a single
`config.py` with type annotations.

### Reading list

1. **Beazley, D.** *Python Distilled* — modern Python idioms, dataclasses,
   typing. Skim.
2. **The pydantic docs** — especially v2 validators and serialization.
3. **Real Python's pytest patterns guides** — fixtures, parametrize,
   property-based testing with Hypothesis.

### Artifact to ship

A green `pytest` run with ≥30 tests, mypy-clean type annotations on the
pipeline, and a working `cli/generate.py` producing the byte-identical
artifact. Then delete the now-defunct sections of `generate_site.py`.

---

## Q4 — Operations research on the bracket problem

**Primary goal:** Take the regional bracket analysis from
`docs/regional-bracket-analysis.md` from a heuristic to a formal
optimization problem.

**Secondary goal:** Geographic visualization — the bracket problem is
inherently spatial.

### What this looks like

The current analysis says regional bracket optimization can save 44.8%
travel in 4A/3A/2A/1A. That's a heuristic result. The formal version:

- **Decision variables:** seed → bracket position assignment.
- **Constraints:** preserve seeding bands (#1-#4 cannot meet before
  semifinals, etc.); no same-league first-round matchups; bracket
  size matches OSAA threshold.
- **Objective:** minimize total first-round travel distance.
- **Solver:** start with a MIP via PuLP or python-mip; if intractable,
  fall back to a heuristic with a published optimality gap.

### Reading list

1. **Vanderbei, R.** *Linear Programming: Foundations and Extensions* —
   the LP/MIP fundamentals.
2. **Toth, P., Vigo, D.** *Vehicle Routing: Problems, Methods, and
   Applications* — the spatial-optimization framing applies to bracket
   problems with travel.
3. **Drezner, Z., Hamacher, H.** *Facility Location: Applications and
   Theory* — for the meta-question of "where should the state finals
   be?"

### Artifact to ship

A `docs/bracket-optimization.md` with:
- Formal problem statement.
- Implementation in PuLP or similar.
- Comparison: optimal vs heuristic vs strict-seeding, with a published
  optimality gap.
- Geographic visualization (Folium or Plotly) of the optimal vs strict
  bracket for one season.

This becomes a portfolio piece in its own right — operations research
on a real public-interest problem.

---

## Q5 — Frontend modernization

**Primary goal:** Reconcile the two renderers. Pick the React app as
canonical (it's the one with active typing) and have it consume the
published `processed_rankings.json` directly.

**Secondary goal:** Accessibility — Lighthouse / a11y audit on the
current rendered HTML.

### What this looks like

- Move the Python pipeline to *only* produce the JSON artifact. Stop
  generating HTML.
- The React app reads `public/data/processed_rankings.json` and
  renders. It already exists, just needs to be wired up to the full
  feature set (currently only renders APR; the production page has
  playoff sim, H2H tooltips, etc.).
- Add a `vite build` step to CI that publishes to `public/dist/`.
- Run Lighthouse on the result. Fix the obvious a11y issues.

### Reading list

1. **The Vite docs** on production builds and asset handling.
2. **Tan, K.** *Eloquent JavaScript* (latest ed.) — chapters on the DOM
   and the event system.
3. **WebAIM's WCAG quick reference** — focus on color contrast, focus
   visibility, and semantic HTML.

### Artifact to ship

A `public/dist/index.html` produced by Vite, replacing the Python-
generated `index.html`. Pipeline now emits only JSON. Lighthouse
score ≥90 on accessibility.

---

## Q6 — Bayesian rating models

**Primary goal:** Implement a Glicko or TrueSkill rating as a sixth
computer-ranking algorithm and compare to the existing five.

**Secondary goal:** Public communication — write up the project for a
broader audience (a blog post, an OACA presentation, or a sports-stats
mailing list).

### What this looks like

Glicko and TrueSkill both extend Elo with explicit uncertainty (a
rating *and* a rating deviation). They naturally handle the small-
sample problem your empirical-Bayes shrinkage approximates.

- Implement Glicko-2 in `scripts/computer_rankings.py`.
- Add it to the composite alongside Elo, Colley, Massey, PageRank,
  Win-Score.
- Compare: does the Glicko-2 rating's **deviation** correlate with the
  shrinkage factor `5 / (N + 5)`?

### Reading list

1. **Glickman, M.** *The Glicko-2 system.* Free online, ~10 pages.
2. **Herbrich, R., Minka, T., Graepel, T.** *TrueSkill: A Bayesian
   Skill Rating System.* Microsoft Research paper.
3. **Lichess's Glicko-2 implementation notes** — practical concerns for
   stable ratings under sparse play.

### Artifact to ship

A `docs/bayesian-rating.md` post comparing Glicko-2's intrinsic
uncertainty to your empirical-Bayes approximation, with one figure of
the correlation. If the correlation is high (it should be), you have a
short, publishable result: "two roads to the same place."

Then write the project up for a public audience: a blog post that
introduces the rating system, names one bug story (the Massey one),
and links to the resources.

---

## Cross-cutting practices through all six quarters

These aren't quarter-bound — practice them every quarter:

- **Always ship the artifact.** No quarter is "done" without the
  document or code at the end. The artifact is the deliverable; the
  reading is the input.

- **Write the AAR after each quarter.** Use the structure from this
  project: what you did, why, what you considered, what shipped, how
  you know, what's next. You'll have six AARs by the end — that's a
  portfolio.

- **Tie new work back to the existing code.** The strength of this
  project as a learning vehicle is that you have a real codebase to
  ground every abstraction in. Don't read papers in a vacuum; read
  them with the code open.

- **Schedule "no new reading" weeks.** Synthesis time. The act of
  writing the artifact is when you discover what you don't actually
  understand.

---

## Six-quarter summary

| Quarter | Primary goal | Artifact |
|---|---|---|
| Q1 | Rating-system literature | Reading notes + pytest suite |
| Q2 | Predictive evaluation | Brier/log-loss study on 2024-2025 |
| Q3 | Python data engineering | Refactored `pipeline/` + tests |
| Q4 | Operations research | Formal bracket optimization |
| Q5 | Frontend modernization | React app as canonical UI |
| Q6 | Bayesian rating | Glicko-2 + project writeup |

By end of Q6 you'll have:
- Six new technical artifacts.
- Six AARs.
- A test suite that wasn't there.
- A refactored, type-checked pipeline.
- A formal optimization model.
- A public writeup that lets the project travel.

That's a portfolio. And it's all extension of work you've already done.
