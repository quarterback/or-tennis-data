#!/usr/bin/env python3
"""How a dual's score is written down.

One implementation, used by the scoreboard, the seeding packet and the committee
tool, so a result never reads one way on one page and another way on the next.

A dual is normally just the flight score: **5-3**.

A dual level at 4-4 is reported the way a penalty shootout is — the score that
stood, then the tiebreak that separated them, in parentheses:

    4-4 (9-8)      decided on sets
    4-4 (90-89)    level on sets, decided on games
    4-4            level on both; it stands as a tie

Oregon's tiebreaker is total sets won, then total games won. If neither
separates the teams it is a tie in the regular season, and coaches are not
obliged to break one at all.

Works on TennisReporting meet dicts, so it is indifferent to whether a dual was
reported by a coach or imported.
"""
from __future__ import annotations


def _flight_scores(meet: dict) -> dict:
    out = {}
    for side in ("winners", "losers"):
        for s in (meet.get("schools") or {}).get(side) or []:
            out[s.get("id")] = s.get("score")
    return out


def opponent_id(meet: dict, school_id: int):
    for sid in _flight_scores(meet):
        if sid != school_id:
            return sid
    return None


def sets_and_games(meet: dict, school_id: int) -> tuple[int, int, int, int]:
    """(our sets, their sets, our games, their games) across every flight.

    Attribution is by the `schoolId` carried on each player, the same way
    `build_lineup_data.py` pulls a team's appearances out of a meet. A flight
    with no players on our side — a default we conceded — contributes nothing,
    which is correct: there was no play.
    """
    my_sets = opp_sets = my_games = opp_games = 0

    for match_type in ("Singles", "Doubles"):
        for line in (meet.get("matches") or {}).get(match_type, []) or []:
            teams = line.get("matchTeams") or []
            if len(teams) != 2:
                continue
            my_tid = opp_tid = None
            for team in teams:
                is_ours = any(p.get("schoolId") == school_id for p in team.get("players") or [])
                if is_ours:
                    my_tid = team.get("id")
                else:
                    opp_tid = team.get("id")
            if my_tid is None or opp_tid is None:
                continue

            for s in line.get("sets") or []:
                mine = s.get(str(my_tid), s.get(my_tid))
                theirs = s.get(str(opp_tid), s.get(opp_tid))
                if not isinstance(mine, int) or not isinstance(theirs, int):
                    continue
                my_games += mine
                opp_games += theirs
                if mine > theirs:
                    my_sets += 1
                elif theirs > mine:
                    opp_sets += 1

    return my_sets, opp_sets, my_games, opp_games


def tiebreak(meet: dict, school_id: int) -> tuple[str, int, int] | None:
    """(basis, ours, theirs) for a dual that a tiebreaker actually decided.

    basis is 'sets' or 'games'. Returns None unless the flight score was level
    AND a winner was recorded — a level dual with no `winnerSchoolId` is a tie,
    whatever the set totals happen to say, and reporting a parenthetical next to
    it would assert a decision nobody made.

    That distinction is not hypothetical: TennisReporting files one side under
    `winners` even for duals it left undecided, so trusting that placement
    produces "3-3 (5-6)" — a winner with fewer sets.
    """
    scores = _flight_scores(meet)
    mine = scores.get(school_id)
    theirs = next((v for k, v in scores.items() if k != school_id), None)
    if mine is None or theirs is None or mine != theirs:
        return None
    if meet.get("winnerSchoolId") is None:
        return None

    my_sets, opp_sets, my_games, opp_games = sets_and_games(meet, school_id)
    won = meet.get("winnerSchoolId") == school_id

    if my_sets != opp_sets:
        basis, mine_v, theirs_v = "sets", my_sets, opp_sets
    elif my_games != opp_games:
        basis, mine_v, theirs_v = "games", my_games, opp_games
    else:
        return None

    # Only report the tiebreak when it explains the recorded winner. Imported
    # duals sometimes carry a winner whose set totals we cannot reproduce —
    # partial flight data, or a decision made on figures the feed did not give
    # us — and printing "3-3 (5-6)" next to the team that won reads as a bug in
    # the page rather than a gap in the source. The winner still stands; we just
    # do not narrate a reason we cannot support.
    if (mine_v > theirs_v) != won:
        return None
    return (basis, mine_v, theirs_v)


def scoreline(meet: dict, school_id: int) -> str:
    """The dual's score from this school's side, e.g. '5-3' or '4-4 (9-8)'."""
    scores = _flight_scores(meet)
    mine = scores.get(school_id)
    theirs = next((v for k, v in scores.items() if k != school_id), None)
    if mine is None or theirs is None:
        return ""

    base = f"{mine}-{theirs}"
    tb = tiebreak(meet, school_id)
    return f"{base} ({tb[1]}-{tb[2]})" if tb else base


def result_letter(meet: dict, school_id: int) -> str:
    """'W', 'L' or 'T' as it belongs on this school's RECORD.

    A team that loses a 4-4 tiebreaker keeps a T here — the dual was level on the
    court and win percentage counts it as half. Head-to-head asks a different
    question and is answered by `generate_site.get_meet_result(..., for_h2h=True)`.
    """
    scores = _flight_scores(meet)
    mine = scores.get(school_id)
    theirs = next((v for k, v in scores.items() if k != school_id), None)
    if mine is None or theirs is None:
        return ""
    if mine > theirs:
        return "W"
    if mine < theirs:
        return "L"
    return "W" if meet.get("winnerSchoolId") == school_id else "T"
