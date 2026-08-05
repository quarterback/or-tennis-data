"""Source precedence inside `dedupe_meets`.

`merge_entered_data.py` removes the scraped twin before the file is ever
written, so this rule should never fire in practice. It exists as the second of
two independent guards: if the removal misses — a date further out than the
tolerance, a school pair that changed id — the worst case must be "the scraped
copy loses" rather than "the dual counts twice".
"""
import generate_site as gs

from conftest import AWAY_ID, HOME_ID


def meet(meet_id, *, flights, source=None, score=(5, 3), date="2027-04-14"):
    lines = [{
        "id": 1000 + i, "flight": str(i + 1), "matchType": "Singles",
        "matchTeams": [{"id": 1, "isWinner": True, "players": []},
                       {"id": 2, "isWinner": False, "players": []}],
        "sets": [],
    } for i in range(flights)]
    m = {
        "id": meet_id,
        "title": "Away at Home",
        "meetDateTime": f"{date}T12:00:00.000Z",
        "schools": {
            "winners": [{"id": HOME_ID, "name": "Home", "score": score[0]}],
            "losers": [{"id": AWAY_ID, "name": "Away", "score": score[1]}],
        },
        "matches": {"Singles": lines, "Doubles": []},
    }
    if source:
        m["source"] = source
    return m


def test_entered_beats_scraped_regardless_of_order():
    scraped = meet(1, flights=3)
    entered = meet(800_000_001, flights=8, source="entered")

    for pair in ([scraped, entered], [entered, scraped]):
        kept = gs.dedupe_meets(list(pair))
        assert len(kept) == 1
        assert kept[0]["source"] == "entered"


def test_entered_wins_even_with_fewer_flights():
    """A six-flight entered dual still overrides an eight-flight scrape.

    The coach is the authority on their own dual, and a short card is legal —
    ranking by flight count would let a stale scrape outrank the coach.
    """
    scraped = meet(1, flights=8)
    entered = meet(800_000_001, flights=6, source="entered")

    kept = gs.dedupe_meets([scraped, entered])
    assert len(kept) == 1
    assert kept[0]["source"] == "entered"


def test_scrape_versus_scrape_is_unchanged():
    """The pre-existing rule — most completed flights wins — still applies."""
    thin = meet(1, flights=3)
    full = meet(2, flights=8)

    kept = gs.dedupe_meets([thin, full])
    assert len(kept) == 1
    assert kept[0]["id"] == 2

    # And the id tiebreak on an equal flight count.
    kept = gs.dedupe_meets([meet(9, flights=6), meet(4, flights=6)])
    assert len(kept) == 1
    assert kept[0]["id"] == 4


def test_different_dates_are_different_duals():
    a = meet(1, flights=8, date="2027-04-14")
    b = meet(800_000_001, flights=8, source="entered", date="2027-04-21")
    assert len(gs.dedupe_meets([a, b])) == 2


def test_multi_team_meets_are_left_alone():
    """Only two-team duals are deduped; events pass through untouched."""
    event = meet(1, flights=8)
    event["schools"]["losers"].append({"id": 99999, "name": "Third", "score": 1})
    assert len(gs.dedupe_meets([event, dict(event, id=2)])) == 2
