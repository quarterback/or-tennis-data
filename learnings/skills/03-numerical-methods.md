# 03 — Numerical Methods & Algorithm Debugging

**One-line:** Caught and fixed a singular-matrix bug in the Massey solver,
implemented stable iterative fixed-point computations, and used dampening
+ caps to keep ratings well-behaved.

---

## The Massey bug — a textbook numerical-methods catch

**Symptom:** On 2026 girls Massey rankings, Jesuit (9-0, consensus #1
everywhere else) sat at Massey #117 of 127, while Vale, Stayton, Century,
Hillsboro, and Glencoe occupied #1–5.

**The chain of failures:**

1. The match graph was disconnected (one small-school cluster never
   played outside itself).
2. The Laplacian-style matrix `M` was constructed with row sums of zero,
   then the last row was replaced with a sum-to-zero constraint.
3. On a connected graph that constraint lifts the rank by one, making
   `M` non-singular.
4. On a disconnected graph it doesn't — `M` is still rank-deficient.
5. `np.linalg.solve(M, p)` raised `LinAlgError`.
6. The `except` branch set every rating to 0.0.
7. `ratings_to_ranks` did a stable descending sort.
8. **Stable sort on all-equal keys preserves insertion order** —
   which came from `teams = sorted(match_graph.keys())`, i.e., school_id.
9. Jesuit's school_id 124879 happens to sit 117th in that order.

**The fix** (`scripts/computer_rankings.py:115–117`):

```python
# Use lstsq so a disconnected match graph (singular M) still yields a
# minimum-norm solution instead of collapsing to all-zero ratings.
r, *_ = np.linalg.lstsq(M, p, rcond=None)
```

`lstsq` returns the minimum-norm least-squares solution even when `M` is
singular. Each connected component gets its own self-consistent ratings
centered near zero by the sum-to-zero row.

**Why this is good debugging:** you didn't stop at "Massey is wrong" —
you traced the failure path all the way to "stable sort on all-equal
keys preserves insertion order = school_id." That's the kind of root-
cause depth that matters.

## Other numerical-methods work

### Iterative fixed-point with explicit convergence guard

`generate_site.py:1190–1227` (QWS): Jacobi-style iteration of
`power_index_qws`, breaking on `max |Δ| < QWS_CONVERGE_EPS` (0.01) or
`QWS_MAX_ITER` (5). Records `qws_iterations` per team for debuggability.
Converges in ~3 iterations on live data.

### Margin-dampened Elo

`scripts/computer_rankings.py:30–46`: `np.log1p(abs(margin))` dampens
blowouts so a 7-0 doesn't move ratings 7× as much as a 5-3. Tie handling
is tri-state (`a_won` can be `None` for true ties).

### Massey margin cap

`scripts/computer_rankings.py:87`: `cap=6` bounds the influence of any
single result. Prevents one lopsided meet from dominating.

### PageRank with normalization + early exit

`scripts/computer_rankings.py:122–163`: power iteration, damping=0.85,
column-normalized transition matrix, early exit on
`np.allclose(r, r_new, atol=1e-8)`. Tie handling splits authority 0.5/0.5
— and you noticed the meet is walked from both sides, so the halves sum
to 1 across both perspectives.

## Resume bullets specific to this skill

- *Diagnosed a silent ranking failure in a Massey/Laplacian solver caused
  by a disconnected match graph; replaced `np.linalg.solve` with
  `np.linalg.lstsq` to obtain minimum-norm solutions per connected
  component, restoring correct ratings for hundreds of teams.*
- *Implemented iterative fixed-point computations with explicit
  convergence guards for an ITA-style quality-weighted rating system,
  reaching stable solutions in ~3 iterations on production data.*

## Where to grow

- Sparse linear algebra (`scipy.sparse`) — the Massey/Colley matrices are
  sparse and the dense numpy approach won't scale past a few thousand
  teams.
- Spectral methods for ranking (eigenvector centrality variants).
- Cross-validation as a numerical-stability test: re-run with one team
  held out, see how much ratings shift.
