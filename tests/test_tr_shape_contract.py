"""The adapter's contract with the functions that actually consume its output.

This is the highest-value test in the reporting system. `entered_shape` claims a
compiled dual is indistinguishable from a scraped one; the only honest way to
check that is to hand its output to the real downstream functions rather than to
a description of them. Every assertion here imports the production code.

If a change to generate_site.py breaks the shape, this fails — which is exactly
what should happen, because the alternative is a season of coach-entered duals
silently contributing nothing to the rankings.
"""
import build_lineup_data
import generate_site as gs
from entered_shape import (
    RESERVED_LINE_MIN,
    RESERVED_MATCHTEAM_MIN,
    RESERVED_MEET_MIN,
    RESERVED_PLAYER_MIN,
    compile_meet,
    dual_title,
    match_team_id,
    title_is_dual_safe,
)

from conftest import AWAY_ID, HOME_ID


def test_compiled_meet_is_recognised_as_a_dual(full_card_dual):
    # If this fails the dual contributes to nothing: not the record, not FWS,
    # not head-to-head, not league standings.
    assert gs.is_dual_match(compile_meet(full_card_dual))


def test_meet_result_matches_the_flight_score(full_card_dual):
    meet = compile_meet(full_card_dual)
    assert gs.get_meet_result(meet, HOME_ID) == "win"
    assert gs.get_meet_result(meet, AWAY_ID) == "loss"


def test_tie_resolves_through_winner_school_id(tied_dual):
    meet = compile_meet(tied_dual)
    winners = meet["schools"]["winners"][0]
    losers = meet["schools"]["losers"][0]
    assert winners["score"] == losers["score"] == 4
    # get_meet_result falls back to winnerSchoolId when flight scores are level.
    assert meet["winnerSchoolId"] == HOME_ID
    assert gs.get_meet_result(meet, HOME_ID) == "win"
    assert gs.get_meet_result(meet, AWAY_ID) == "loss"


def test_extract_match_results_sees_every_flight(full_card_dual):
    meet = compile_meet(full_card_dual)
    results = gs.extract_match_results(meet, HOME_ID)
    assert len(results) == 8, "all eight flights must be attributable by schoolId"

    opponents = {r[0] for r in results}
    assert opponents == {AWAY_ID}

    # Weights come from FLIGHT_WEIGHTS keyed on (matchType, flight-as-string).
    weights = {(r[1], r[2]): r[4] for r in results}
    assert weights[("Singles", "1")] == 1.00
    assert weights[("Singles", "4")] == 0.10
    assert weights[("Doubles", "1")] == 1.00
    assert weights[("Doubles", "4")] == 0.10

    won = {(r[1], r[2]) for r in results if r[3]}
    assert won == {("Singles", "1"), ("Singles", "2"), ("Singles", "3"),
                   ("Doubles", "1"), ("Doubles", "2")}


def test_dual_record_counts_the_meet(full_card_dual):
    meets = [compile_meet(full_card_dual)]
    assert gs.get_dual_match_record(meets, HOME_ID) == (1, 0, 0)
    assert gs.get_dual_match_record(meets, AWAY_ID) == (0, 1, 0)


def test_fws_and_game_share_are_computed(full_card_dual):
    """The Power Index inputs must be non-trivial, not silently zeroed."""
    doc = {"meets": [compile_meet(full_card_dual)]}
    stats = gs.calculate_fws_per_match(doc, HOME_ID)

    assert stats["total_flights_played"] == 8
    assert stats["total_flights_won"] == 5
    # Home won five flights in straight sets and lost three the same way, so the
    # game share should sit meaningfully above half.
    assert stats["games_played"] > 0
    assert 0.5 < stats["game_share"] < 0.7
    assert stats["flight_breakdown"]["D4"] is not None


def test_super_tiebreak_counts_as_one_decision(full_card_dual):
    """A third-set 10-point tiebreak must not read as seventeen games.

    generate_site.py detects this as set 3 with a value >= 10; the adapter has to
    emit it plainly for that to fire.
    """
    dual = dict(full_card_dual)
    lines = [dict(ln) for ln in full_card_dual["lines"]]
    lines[0] = dict(lines[0])
    lines[0]["sets"] = [
        {"number": 1, "home": 6, "away": 3, "tie": None},
        {"number": 2, "home": 4, "away": 6, "tie": None},
        {"number": 3, "home": 10, "away": 7, "tie": None},
    ]
    dual["lines"] = lines

    stats = gs.calculate_fws_per_match({"meets": [compile_meet(dual)]}, HOME_ID)
    baseline = gs.calculate_fws_per_match({"meets": [compile_meet(full_card_dual)]}, HOME_ID)
    # Straight-sets line (12 home games) replaced by 6+4+1: strictly fewer.
    assert stats["games_won"] < baseline["games_won"]
    # And nowhere near the +17 a raw tiebreak count would add.
    assert stats["games_played"] - baseline["games_played"] < 5


def test_lineup_builder_classifies_all_eight_flights(full_card_dual):
    meet = compile_meet(full_card_dual)
    slots = set()
    for match_type in ("Singles", "Doubles"):
        for line in meet["matches"][match_type]:
            slot = build_lineup_data.slot_for(line)
            assert slot is not None, f"{match_type} {line['flight']} not classified"
            slots.add(slot)
    assert slots == {"S1", "S2", "S3", "S4", "D1", "D2", "D3", "D4"}


def test_score_str_reads_the_set_keys(full_card_dual):
    """`sets` keys are matchTeam ids as strings — score_str depends on it."""
    meet = compile_meet(full_card_dual)
    line = meet["matches"]["Singles"][0]
    home_mt = line["matchTeams"][0]["id"]
    away_mt = line["matchTeams"][1]["id"]
    assert build_lineup_data.score_str(line["sets"], home_mt, away_mt) == "6-3, 6-4"
    assert build_lineup_data.score_str(line["sets"], away_mt, home_mt) == "3-6, 4-6"


def test_ids_land_in_the_reserved_ranges(full_card_dual):
    meet = compile_meet(full_card_dual)
    assert meet["id"] >= RESERVED_MEET_MIN
    for match_type in ("Singles", "Doubles"):
        for line in meet["matches"][match_type]:
            assert RESERVED_LINE_MIN <= line["id"] < RESERVED_MEET_MIN
            for team in line["matchTeams"]:
                assert RESERVED_MATCHTEAM_MIN <= team["id"] < RESERVED_LINE_MIN
                for player in team["players"]:
                    assert player["id"] >= RESERVED_PLAYER_MIN


def test_match_team_ids_are_unique_and_stable():
    ids = {match_team_id(RESERVED_LINE_MIN + i, side)
           for i in range(500) for side in ("home", "away")}
    assert len(ids) == 1000
    assert match_team_id(RESERVED_LINE_MIN + 7, "home") == \
        match_team_id(RESERVED_LINE_MIN + 7, "home")


def test_compilation_is_deterministic(full_card_dual):
    assert compile_meet(full_card_dual) == compile_meet(full_card_dual)


def test_tr_player_id_passes_through(full_card_dual):
    """A player linked to a scraped TR id keeps that identity, not a new one."""
    dual = dict(full_card_dual)
    lines = [dict(ln) for ln in full_card_dual["lines"]]
    lines[0] = dict(lines[0])
    lines[0]["home_players"] = [
        {"id": 171590, "first_name": "Joyce My", "last_name": "Nguyen", "grade": "12"},
    ]
    dual["lines"] = lines
    meet = compile_meet(dual)
    ids = [p["id"] for p in meet["matches"]["Singles"][0]["matchTeams"][0]["players"]]
    assert ids == [171590]


class TestTitles:
    """`is_dual_match` filters tournaments by title, so titles are load-bearing."""

    def test_normal_title_is_safe(self):
        assert dual_title("Stayton", "Valley Catholic School") == \
            "Valley Catholic School at Stayton"

    def test_filter_words_are_rejected(self):
        assert not title_is_dual_safe("District 1 Championship")
        assert not title_is_dual_safe("6A State Championship")
        assert not title_is_dual_safe("Event (SD-1/2). 4A")

    def test_a_colliding_school_name_falls_back(self):
        title = dual_title("District Christian", "Stayton")
        assert title_is_dual_safe(title)

    def test_postseason_dual_still_counts(self, full_card_dual):
        dual = dict(full_card_dual)
        dual["is_postseason"] = True
        dual["event_name"] = "Special District 1 District Tournament"
        meet = compile_meet(dual)
        assert meet["postSeason"] is True
        # The event name must never leak into the title — "District" there would
        # exclude a real dual from every ranking metric.
        assert gs.is_dual_match(meet)


def test_meet_date_is_stable_at_noon(full_card_dual):
    meet = compile_meet(full_card_dual)
    assert meet["meetDateTime"][:10] == "2027-04-14"
    assert meet["meetDateTime"] == "2027-04-14T12:00:00.000Z"


def test_short_card_is_accepted(full_card_dual):
    """Six-flight duals are legal; the FWS denominator adjusts for them."""
    dual = dict(full_card_dual)
    dual["lines"] = [ln for ln in full_card_dual["lines"] if ln["flight"] <= 3]
    meet = compile_meet(dual)
    assert gs.is_dual_match(meet)
    stats = gs.calculate_fws_per_match({"meets": [meet]}, HOME_ID)
    assert stats["total_flights_played"] == 6
