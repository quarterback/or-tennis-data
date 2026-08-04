"""Shared fixtures for the reporting tests.

The repository root is on the path so tests can import the top-level scripts
(`generate_site`, `entered_shape`, …) the way the build does.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _line(line_id, match_type, flight, home_won, sets, home=None, away=None):
    return {
        "line_id": line_id,
        "match_type": match_type,
        "flight": flight,
        "home_won": home_won,
        "finish": None,
        "home_players": home if home is not None else [
            {"id": 900_000_000 + line_id % 1000, "first_name": "Home",
             "last_name": f"Player{flight}{match_type[0]}", "grade": "11"},
        ],
        "away_players": away if away is not None else [
            {"id": 900_100_000 + line_id % 1000, "first_name": "Away",
             "last_name": f"Player{flight}{match_type[0]}", "grade": "10"},
        ],
        "sets": sets,
    }


def _sets(a, b, c=None):
    """Straight-sets helper: `_sets((6, 3), (6, 4))`."""
    out = [{"number": i + 1, "home": s[0], "away": s[1], "tie": None}
           for i, s in enumerate([a, b] + ([c] if c else []))]
    return out


HOME_ID = 74614      # Stayton
AWAY_ID = 124656     # Valley Catholic School


@pytest.fixture
def full_card_dual():
    """A complete 4S+4D dual won 5-3 by the home team.

    Singles 1-3 and Doubles 1-2 to the home side; Singles 4 and Doubles 3-4 to
    the away side.
    """
    wins = {
        ("Singles", 1): True, ("Singles", 2): True,
        ("Singles", 3): True, ("Singles", 4): False,
        ("Doubles", 1): True, ("Doubles", 2): True,
        ("Doubles", 3): False, ("Doubles", 4): False,
    }
    lines = []
    for i, ((match_type, flight), home_won) in enumerate(wins.items()):
        score = _sets((6, 3), (6, 4)) if home_won else _sets((3, 6), (4, 6))
        doubles = match_type == "Doubles"
        home_players = [
            {"id": 900_000_100 + i * 2, "first_name": "H", "last_name": f"One{i}", "grade": "12"},
        ]
        away_players = [
            {"id": 900_000_200 + i * 2, "first_name": "A", "last_name": f"One{i}", "grade": "11"},
        ]
        if doubles:
            home_players.append(
                {"id": 900_000_101 + i * 2, "first_name": "H", "last_name": f"Two{i}", "grade": "10"})
            away_players.append(
                {"id": 900_000_201 + i * 2, "first_name": "A", "last_name": f"Two{i}", "grade": "9"})
        lines.append(_line(700_000_000 + i, match_type, flight, home_won, score,
                           home=home_players, away=away_players))

    return {
        "dual_id": 800_000_042,
        "year": 2027,
        "gender_id": 2,
        "is_jv": False,
        "played_on": "2027-04-14",
        "is_postseason": False,
        "event_name": None,
        "status": "confirmed",
        "home": {"school_id": HOME_ID, "name": "Stayton"},
        "away": {"school_id": AWAY_ID, "name": "Valley Catholic School"},
        "lines": lines,
    }


@pytest.fixture
def tied_dual(full_card_dual):
    """4-4 on flights, home ahead on sets — the winnerSchoolId path.

    Home wins its four flights in straight sets (8 sets). Away wins two in
    straight sets and grinds out two in three, conceding a set each time, so away
    takes 8 sets to home's 10. Oregon's tiebreaker is sets, then games, so home
    wins the dual without winning more flights.
    """
    dual = dict(full_card_dual)
    plan = [
        ("Singles", 1, True, _sets((6, 3), (6, 4))),
        ("Singles", 2, True, _sets((6, 2), (6, 1))),
        ("Singles", 3, False, _sets((3, 6), (4, 6))),
        ("Singles", 4, False, _sets((2, 6), (1, 6))),
        ("Doubles", 1, True, _sets((6, 4), (7, 5))),
        ("Doubles", 2, True, _sets((6, 0), (6, 2))),
        # Home takes a set in each of these but loses the flight.
        ("Doubles", 3, False, _sets((6, 4), (4, 6), (5, 7))),
        ("Doubles", 4, False, _sets((7, 5), (3, 6), (4, 6))),
    ]
    lines = []
    for i, (match_type, flight, home_won, sets) in enumerate(plan):
        lines.append(_line(700_000_100 + i, match_type, flight, home_won, sets))
    dual["lines"] = lines
    return dual
