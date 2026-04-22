"""
Computer ranking algorithms for Oregon HS tennis.

Each function takes a match graph and returns {team_id: rating}.
Match graph: {team_id: [(opponent_id, won_bool, flight_margin), ...]}
"""

import numpy as np
from collections import defaultdict


def _teams_and_index(match_graph):
    """Return sorted team list and id->index mapping."""
    teams = sorted(match_graph.keys())
    idx = {t: i for i, t in enumerate(teams)}
    return teams, idx


def elo_rankings(match_graph, match_list):
    """
    Elo ratings. Process matches chronologically.
    match_list: [(date, team_a, team_b, a_won, flight_margin), ...] sorted by date.
    """
    ratings = defaultdict(lambda: 1500.0)
    K = 32

    for date, team_a, team_b, a_won, margin in match_list:
        ra, rb = ratings[team_a], ratings[team_b]
        ea = 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))
        eb = 1.0 - ea

        # Margin multiplier: log(1 + abs(margin)) dampens blowouts
        mult = np.log1p(abs(margin)) if margin != 0 else 1.0
        mult = max(mult, 1.0)

        sa = 1.0 if a_won else (0.5 if margin == 0 else 0.0)
        sb = 1.0 - sa

        ratings[team_a] += K * mult * (sa - ea)
        ratings[team_b] += K * mult * (sb - eb)

    return dict(ratings)


def colley_rankings(match_graph):
    """
    Colley Matrix: pure W/L, no margins.
    Solves (2I + C)r = 1 + (1/2)(w - l)
    """
    teams, idx = _teams_and_index(match_graph)
    n = len(teams)
    if n < 2:
        return {t: 0.5 for t in teams}

    C = np.zeros((n, n))
    b = np.ones(n)

    for team_id, matches in match_graph.items():
        i = idx[team_id]
        wins = sum(1 for _, won, _ in matches if won)
        losses = sum(1 for _, won, _ in matches if not won)
        total = len(matches)

        C[i][i] = 2 + total
        b[i] = 1 + 0.5 * (wins - losses)

        for opp_id, _, _ in matches:
            if opp_id in idx:
                j = idx[opp_id]
                C[i][j] -= 1

    try:
        r = np.linalg.solve(C, b)
    except np.linalg.LinAlgError:
        r = np.full(n, 0.5)

    return {teams[i]: float(r[i]) for i in range(n)}


def massey_rankings(match_graph, cap=6):
    """
    Massey ratings: least-squares on flight margins (capped).
    Solves M*r = p where margin equations relate team ratings.
    """
    teams, idx = _teams_and_index(match_graph)
    n = len(teams)
    if n < 2:
        return {t: 0.0 for t in teams}

    M = np.zeros((n, n))
    p = np.zeros(n)

    for team_id, matches in match_graph.items():
        i = idx[team_id]
        for opp_id, won, margin in matches:
            if opp_id not in idx:
                continue
            j = idx[opp_id]
            capped = max(-cap, min(cap, margin))
            M[i][i] += 1
            M[i][j] -= 1
            p[i] += capped

    # Replace last row with sum-to-zero constraint
    M[-1] = np.ones(n)
    p[-1] = 0

    # Use lstsq so a disconnected match graph (singular M) still yields a
    # minimum-norm solution instead of collapsing to all-zero ratings.
    r, *_ = np.linalg.lstsq(M, p, rcond=None)

    return {teams[i]: float(r[i]) for i in range(n)}


def pagerank_rankings(match_graph, damping=0.85, iterations=100):
    """
    PageRank on win/loss graph. Wins create links from loser to winner.
    """
    teams, idx = _teams_and_index(match_graph)
    n = len(teams)
    if n < 2:
        return {t: 1.0 / max(n, 1) for t in teams}

    # Build adjacency: loser distributes authority to winner
    # adj[i][j] = link from j to i (j distributes to i)
    adj = np.zeros((n, n))
    for team_id, matches in match_graph.items():
        i = idx[team_id]
        for opp_id, won, margin in matches:
            if opp_id not in idx:
                continue
            j = idx[opp_id]
            if won:
                adj[i][j] += 1  # winner (i) receives from loser (j)
            else:
                adj[j][i] += 1  # winner (j) receives from loser (i)

    # Normalize columns
    col_sums = adj.sum(axis=0)
    col_sums[col_sums == 0] = 1
    T = adj / col_sums

    # Power iteration
    r = np.ones(n) / n
    for _ in range(iterations):
        r_new = (1 - damping) / n + damping * T.dot(r)
        if np.allclose(r, r_new, atol=1e-8):
            break
        r = r_new

    return {teams[i]: float(r[i]) for i in range(n)}


def win_score_rankings(match_graph):
    """
    Win-Score: each win earns the opponent's win percentage. Simple, no iteration.
    """
    # First compute win percentages
    wp = {}
    for team_id, matches in match_graph.items():
        wins = sum(1 for _, won, _ in matches if won)
        total = len(matches)
        wp[team_id] = wins / total if total > 0 else 0.0

    # Score = sum of beaten opponents' win%
    scores = {}
    for team_id, matches in match_graph.items():
        score = 0.0
        for opp_id, won, _ in matches:
            if won and opp_id in wp:
                score += wp[opp_id]
        scores[team_id] = score

    return scores


def run_all(match_graph, match_list):
    """
    Run all 5 ranking algorithms.
    Returns dict of {system_name: {team_id: rating}}.
    """
    return {
        'Elo': elo_rankings(match_graph, match_list),
        'Colley': colley_rankings(match_graph),
        'Massey': massey_rankings(match_graph),
        'PageRank': pagerank_rankings(match_graph),
        'Win-Score': win_score_rankings(match_graph),
    }


def ratings_to_ranks(ratings):
    """Convert {team_id: rating} to {team_id: rank} (1 = best)."""
    sorted_teams = sorted(ratings.items(), key=lambda x: x[1], reverse=True)
    return {team_id: rank for rank, (team_id, _) in enumerate(sorted_teams, 1)}


def composite_ranks(all_ranks, team_ids):
    """
    Compute composite (average rank) and median rank across systems.
    Returns {team_id: {'composite': float, 'median': float, 'std': float, 'ranks': {sys: rank}}}
    """
    results = {}
    systems = list(all_ranks.keys())

    for tid in team_ids:
        ranks = []
        rank_by_sys = {}
        for sys_name in systems:
            r = all_ranks[sys_name].get(tid)
            if r is not None:
                ranks.append(r)
                rank_by_sys[sys_name] = r
        if ranks:
            results[tid] = {
                'composite': sum(ranks) / len(ranks),
                'median': float(np.median(ranks)),
                'std': float(np.std(ranks)),
                'ranks': rank_by_sys,
            }
    return results
