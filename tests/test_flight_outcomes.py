"""Short cards, forfeits, retirements and ties.

Oregon plays four singles and four doubles, but a dual does not always fill all
eight: a team can be short of players, or two coaches can agree to play a
subset. Those are ordinary results, not errors, and each has to score
differently:

  * **played / retired** — a contested flight with a winner.
  * **default** — one team had nobody. The side that showed up wins the flight;
    the side that could not field a player is charged with losing it; neither
    banks any games.
  * **not played** — nobody contested it. It counts for no one and leaves the
    flight denominator, which is what makes a six-flight dual score correctly.

And a 4-4 dual is a real Oregon result: sets, then games, then it stands as a tie.
"""
import generate_site as gs
from entered_shape import compile_meet, flight_score, tiebreak_winner
from scoreline import result_letter, scoreline, tiebreak

from conftest import AWAY_ID, HOME_ID, _line, _sets


def dual(lines, **kw):
    base = {
        "dual_id": 800_000_777, "year": 2027, "gender_id": 2, "is_jv": False,
        "played_on": "2027-04-14", "is_postseason": False, "event_name": None,
        "status": "confirmed",
        "home": {"school_id": HOME_ID, "name": "Stayton"},
        "away": {"school_id": AWAY_ID, "name": "Valley Catholic School"},
        "lines": lines,
    }
    base.update(kw)
    return base


def default_line(line_id, match_type, flight, home_wins):
    """A defaulted flight: only the side that fielded a player has one."""
    ln = _line(line_id, match_type, flight, home_wins, [])
    ln["finish"] = "default"
    ln["home_players" if not home_wins else "away_players"] = []
    return ln


# ---------------------------------------------------------------------------
# Short cards
# ---------------------------------------------------------------------------

def test_a_six_flight_dual_scores_over_six_flights():
    lines = [_line(700_000_500 + i, mt, f, True, _sets((6, 2), (6, 3)))
             for i, (mt, f) in enumerate([("Singles", 1), ("Singles", 2), ("Singles", 3),
                                          ("Doubles", 1), ("Doubles", 2), ("Doubles", 3)])]
    lines[5]["home_won"] = False
    lines[5]["sets"] = _sets((2, 6), (3, 6))

    stats = gs.calculate_fws_per_match({"meets": [compile_meet(dual(lines))]}, HOME_ID)
    assert stats["total_flights_played"] == 6
    assert stats["total_flights_won"] == 5
    # The positions that were never contested carry no record either way.
    # (build_rankings turns a zero-played counter into a null for display.)
    assert stats["flight_breakdown"]["S4"] == {"wins": 0, "played": 0}
    assert stats["flight_breakdown"]["D4"] == {"wins": 0, "played": 0}


def test_an_uncontested_flight_counts_for_neither_team():
    """The difference between "not played" and "defaulted", in one assertion."""
    played = [_line(700_000_600 + i, "Singles", i + 1, True, _sets((6, 1), (6, 1)))
              for i in range(3)]
    meet = compile_meet(dual(played))

    home = gs.calculate_fws_per_match({"meets": [meet]}, HOME_ID)
    away = gs.calculate_fws_per_match({"meets": [meet]}, AWAY_ID)
    assert home["total_flights_played"] == away["total_flights_played"] == 3
    assert home["total_flights_won"] == 3
    assert away["total_flights_won"] == 0


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

def test_a_default_is_a_flight_won_and_a_flight_lost():
    lines = [_line(700_000_700 + i, "Singles", i + 1, True, _sets((6, 1), (6, 1)))
             for i in range(3)]
    lines.append(default_line(700_000_710, "Singles", 4, home_wins=True))
    meet = compile_meet(dual(lines))

    home = gs.calculate_fws_per_match({"meets": [meet]}, HOME_ID)
    away = gs.calculate_fws_per_match({"meets": [meet]}, AWAY_ID)

    assert home["total_flights_won"] == 4, "the team that showed up banks the flight"
    assert home["total_flights_played"] == 4
    # The team that could not field a player is charged with having lost it,
    # rather than quietly dropping the position from its denominator.
    assert away["total_flights_played"] == 4
    assert away["total_flights_won"] == 0


def test_a_default_contributes_no_games():
    """A forfeit is not a 12-0 win — it has no score at all."""
    lines = [_line(700_000_800, "Singles", 1, True, _sets((6, 0), (6, 0)))]
    baseline = gs.calculate_fws_per_match({"meets": [compile_meet(dual(lines))]}, HOME_ID)

    lines.append(default_line(700_000_801, "Singles", 2, home_wins=True))
    withdefault = gs.calculate_fws_per_match({"meets": [compile_meet(dual(lines))]}, HOME_ID)

    assert withdefault["games_won"] == baseline["games_won"]
    assert withdefault["games_played"] == baseline["games_played"]
    assert withdefault["total_flights_won"] == baseline["total_flights_won"] + 1


def test_a_default_still_reads_as_a_dual():
    lines = [_line(700_000_900 + i, "Singles", i + 1, True, _sets((6, 1), (6, 1)))
             for i in range(3)]
    lines.append(default_line(700_000_910, "Doubles", 1, home_wins=False))
    meet = compile_meet(dual(lines))
    assert gs.is_dual_match(meet)
    assert gs.get_meet_result(meet, HOME_ID) == "win"
    assert flight_score(lines) == (3, 1)


# ---------------------------------------------------------------------------
# Retirements
# ---------------------------------------------------------------------------

def test_a_retirement_keeps_the_score_it_stopped_at():
    """The winner is stated, not derived — the leader can be the one who quit."""
    ln = _line(700_001_000, "Singles", 1, False, _sets((6, 2), (3, 1)))
    ln["finish"] = "retired"
    meet = compile_meet(dual([ln]))

    line = meet["matches"]["Singles"][0]
    assert line["finish"] == "retired"
    # Home led on sets but retired, so away takes the flight.
    assert line["matchTeams"][1]["isWinner"] is True
    assert gs.calculate_fws_per_match({"meets": [meet]}, HOME_ID)["total_flights_won"] == 0
    # The games actually played still count toward game share.
    assert gs.calculate_fws_per_match({"meets": [meet]}, HOME_ID)["games_won"] == 9


# ---------------------------------------------------------------------------
# Ties
# ---------------------------------------------------------------------------

def eight_flights(home_wins, sets_for_home, sets_for_away):
    order = [("Singles", f) for f in (1, 2, 3, 4)] + [("Doubles", f) for f in (1, 2, 3, 4)]
    out = []
    for i, (mt, f) in enumerate(order):
        won = i < home_wins
        out.append(_line(700_002_000 + i, mt, f, won,
                         sets_for_home if won else sets_for_away))
    return out


def test_four_all_is_broken_on_sets():
    lines = eight_flights(4, _sets((6, 4), (6, 4)), _sets((4, 6), (6, 3), (4, 6)))
    d = dual(lines)
    assert flight_score(lines) == (4, 4)
    # Home wins its four in straight sets (8); away wins its four but concedes a
    # set each time (8 to away, 4 to home) — 12 to 8 on sets.
    assert tiebreak_winner(d) == HOME_ID
    meet = compile_meet(d)
    assert gs.get_meet_result(meet, HOME_ID) == "win"
    # The record says tie — see test_the_tiebreak_loser_records_a_tie_not_a_loss.
    assert gs.get_meet_result(meet, AWAY_ID) == "tie"
    # Head to head is the other question, and there it is a loss.
    assert gs.get_meet_result(meet, AWAY_ID, for_h2h=True) == "loss"


def test_level_on_sets_is_broken_on_games():
    lines = eight_flights(4, _sets((6, 0), (6, 0)), _sets((4, 6), (4, 6)))
    d = dual(lines)
    assert flight_score(lines) == (4, 4)
    # Both sides win eight sets; home won its by more.
    assert tiebreak_winner(d) == HOME_ID


def test_a_true_tie_stands():
    """4-4, level on sets and level on games, is a tie in the regular season.

    The system does not invent a winner. `get_meet_result` returns 'tie' for
    both sides and the record carries a T.
    """
    lines = eight_flights(4, _sets((6, 4), (6, 4)), _sets((4, 6), (4, 6)))
    d = dual(lines)
    assert flight_score(lines) == (4, 4)
    assert tiebreak_winner(d) is None

    meet = compile_meet(d)
    assert meet["winnerSchoolId"] is None
    assert gs.get_meet_result(meet, HOME_ID) == "tie"
    assert gs.get_meet_result(meet, AWAY_ID) == "tie"
    assert gs.get_dual_match_record([meet], HOME_ID) == (0, 0, 1)
    assert gs.get_dual_match_record([meet], AWAY_ID) == (0, 0, 1)


def test_the_tiebreak_loser_records_a_tie_not_a_loss():
    """A 4-4 is never a defeat, however the tiebreaker lands.

    The winner banks a win; the other team keeps a tie, which win percentage
    counts as half — the NHL overtime-loss convention. Wins and losses therefore
    do not balance across the two teams, on purpose.
    """
    lines = eight_flights(4, _sets((6, 4), (6, 4)), _sets((4, 6), (6, 3), (4, 6)))
    meet = compile_meet(dual(lines))

    assert gs.get_meet_result(meet, HOME_ID) == "win"
    assert gs.get_meet_result(meet, AWAY_ID) == "tie"
    assert gs.get_dual_match_record([meet], HOME_ID) == (1, 0, 0)
    assert gs.get_dual_match_record([meet], AWAY_ID) == (0, 0, 1)


def test_a_tiebreak_loss_is_worth_half_a_win():
    """The reason the distinction matters: it feeds seeding through wp."""
    won = eight_flights(5, _sets((6, 4), (6, 4)), _sets((4, 6), (4, 6)))
    level = eight_flights(4, _sets((6, 4), (6, 4)), _sets((4, 6), (6, 3), (4, 6)))

    # Two duals for the away team: one clear loss, one lost tiebreaker.
    meets = [compile_meet(dual(won, dual_id=800_000_001)),
             compile_meet(dual(level, dual_id=800_000_002, played_on="2027-04-21"))]
    wins, losses, ties = gs.get_dual_match_record(meets, AWAY_ID)
    assert (wins, losses, ties) == (0, 1, 1)

    wp = (wins + ties * 0.5) / (wins + losses + ties)
    assert wp == 0.25, "a lost tiebreaker must be worth half a win, not zero"


# ---------------------------------------------------------------------------
# How the score is written down
# ---------------------------------------------------------------------------

def test_a_decided_dual_reads_as_the_flight_score():
    lines = eight_flights(5, _sets((6, 4), (6, 4)), _sets((4, 6), (4, 6)))
    meet = compile_meet(dual(lines))
    assert scoreline(meet, HOME_ID) == "5-3"
    assert scoreline(meet, AWAY_ID) == "3-5"


def test_a_tiebreak_on_sets_reads_like_a_shootout():
    lines = eight_flights(4, _sets((6, 4), (6, 4)), _sets((4, 6), (6, 3), (4, 6)))
    meet = compile_meet(dual(lines))
    # Home wins four in straight sets (8); away wins four in three sets each,
    # conceding one every time (12 to away, 4 to home).
    assert tiebreak(meet, HOME_ID) == ("sets", 12, 8)
    assert scoreline(meet, HOME_ID) == "4-4 (12-8)"
    assert scoreline(meet, AWAY_ID) == "4-4 (8-12)"


def test_a_tiebreak_on_games_reads_the_same_way():
    lines = eight_flights(4, _sets((6, 0), (6, 0)), _sets((4, 6), (4, 6)))
    meet = compile_meet(dual(lines))
    basis, mine, theirs = tiebreak(meet, HOME_ID)
    assert basis == "games", "sets are level here, so games decide"
    assert mine > theirs
    assert scoreline(meet, HOME_ID) == f"4-4 ({mine}-{theirs})"


def test_a_standing_tie_has_no_parenthetical():
    lines = eight_flights(4, _sets((6, 4), (6, 4)), _sets((4, 6), (4, 6)))
    meet = compile_meet(dual(lines))
    assert tiebreak(meet, HOME_ID) is None
    assert scoreline(meet, HOME_ID) == "4-4"
    assert result_letter(meet, HOME_ID) == "T"


def test_the_record_letter_and_the_head_to_head_disagree_on_purpose():
    lines = eight_flights(4, _sets((6, 4), (6, 4)), _sets((4, 6), (6, 3), (4, 6)))
    meet = compile_meet(dual(lines))
    assert result_letter(meet, HOME_ID) == "W"
    assert result_letter(meet, AWAY_ID) == "T"          # the record
    assert gs.get_meet_result(meet, AWAY_ID, for_h2h=True) == "loss"   # the meeting
