"""The whole chain: a coach reports a dual, the rankings change.

Each earlier test file pins one link — the adapter's shape, the merge's
precedence, the published invariants. This one runs the chain a coach actually
triggers, because the failure that would matter most is the one where every
individual piece works and the dual still does not reach the table.

Deliberately built on a synthetic four-team league rather than real data, so the
expected numbers can be reasoned about by hand.
"""
import json
import os

import pytest

import build_seeding_packet
import generate_site as gs
import merge_entered_data as merge
from entered_shape import compile_meet

from conftest import _line, _sets

SCHOOLS = {
    101: "Alpha",
    102: "Bravo",
    103: "Charlie",
    104: "Delta",
}
YEAR = 2027
GENDER = 2


def make_dual(dual_id, home, away, date, home_wins, base_line_id):
    """A full 8-flight card where the home team wins `home_wins` of them."""
    lines = []
    order = [("Singles", f) for f in (1, 2, 3, 4)] + [("Doubles", f) for f in (1, 2, 3, 4)]
    for i, (match_type, flight) in enumerate(order):
        won = i < home_wins
        sets = _sets((6, 3), (6, 4)) if won else _sets((3, 6), (4, 6))
        lines.append(_line(base_line_id + i, match_type, flight, won, sets))
    return {
        "dual_id": dual_id, "year": YEAR, "gender_id": GENDER, "is_jv": False,
        "played_on": date, "is_postseason": False, "event_name": None,
        "status": "confirmed",
        "home": {"school_id": home, "name": SCHOOLS[home]},
        "away": {"school_id": away, "name": SCHOOLS[away]},
        "lines": lines,
    }


@pytest.fixture
def season(tmp_path, monkeypatch):
    """A four-team league in a temporary tree, wired into every module."""
    data = tmp_path / "data"
    (data / str(YEAR)).mkdir(parents=True)
    (tmp_path / "data_jv").mkdir()
    (tmp_path / "entered" / str(YEAR)).mkdir(parents=True)

    monkeypatch.setattr(merge, "DATA_DIR", str(data))
    monkeypatch.setattr(merge, "JV_DATA_DIR", str(tmp_path / "data_jv"))
    monkeypatch.setattr(merge, "BUNDLE_DIR", str(tmp_path / "entered"))

    master = tmp_path / "master_school_list.csv"
    master.write_text(
        "id,name,city,state,Classification,League\n" +
        "".join(f"{sid},{name},Town,OR,5A,5A-9 Test\n" for sid, name in SCHOOLS.items()))
    return {"root": tmp_path, "data": data, "master": master}


def write_bundle(season, duals):
    path = season["root"] / "entered" / str(YEAR) / "entered_meets.json"
    path.write_text(json.dumps({"year": YEAR, "meets": [compile_meet(d) for d in duals]}))


def build(season):
    """Run the real ranking build over the temporary tree."""
    return gs.build_rankings(str(season["data"]), str(season["master"]))


def entry_for(rankings, school_id):
    for e in rankings:
        if e["school_id"] == school_id and e["year"] == YEAR:
            return e
    return None


# ---------------------------------------------------------------------------


def test_a_reported_dual_reaches_the_rankings(season):
    """The headline path: nothing scraped, one coach reports, the table fills in."""
    write_bundle(season, [
        make_dual(800_000_001, 101, 102, f"{YEAR}-04-07", 6, 700_001_000),
        make_dual(800_000_002, 101, 103, f"{YEAR}-04-14", 5, 700_002_000),
        make_dual(800_000_003, 103, 102, f"{YEAR}-04-21", 7, 700_003_000),
        make_dual(800_000_004, 104, 101, f"{YEAR}-04-28", 2, 700_004_000),
    ])
    merge.merge_year(YEAR)
    rankings, _, _, _ = build(season)

    alpha = entry_for(rankings, 101)
    assert alpha is not None, "the reporting team never reached the rankings"
    # Alpha won three duals (6-2, 5-3, and 6-2 away at Delta) and lost none.
    assert alpha["record"] == "3-0-0"
    assert alpha["total_flights_played"] == 24
    assert alpha["total_flights_won"] == 17
    assert alpha["rank"] == 1

    bravo = entry_for(rankings, 102)
    assert bravo["record"] == "0-2-0"
    # Every dual is counted from both sides — Alpha's 6-2 is Bravo's 2-6.
    assert bravo["total_flights_won"] == 2 + 1


def test_the_pipeline_is_a_no_op_without_entered_data(season):
    """A build with an empty database must not invent a season."""
    merge.merge_year(YEAR)
    rankings, _, _, _ = build(season)
    assert [e for e in rankings if e["year"] == YEAR] == []


def test_an_entered_dual_overrides_the_scraped_record(season):
    """The whole point: the coach's version is what the rankings use."""
    # The scrape has Alpha losing 3-5. It is a six-flight card, the shape most of
    # the 2026 scrape arrived in.
    scraped = {
        "id": 222_000, "title": "Bravo at Alpha",
        "meetDateTime": f"{YEAR}-04-07T23:45:00.000Z",
        "postSeason": False,
        "schools": {"winners": [{"id": 102, "name": "Bravo", "score": 5}],
                    "losers": [{"id": 101, "name": "Alpha", "score": 3}]},
        "matches": {"Singles": [], "Doubles": []},
    }
    for school_id in (101, 102):
        path = season["data"] / str(YEAR) / f"school_{school_id}_gender_{GENDER}.json"
        path.write_text(json.dumps({
            "school": {"id": school_id, "name": SCHOOLS[school_id]},
            "coaches": [], "overallRecord": {"win": 0, "loss": 1, "tie": 0},
            "meets": [scraped],
        }))

    rankings, _, _, _ = build(season)
    assert entry_for(rankings, 101)["record"] == "0-1-0", "scrape should stand alone"

    # Now the coach reports the same dual, the other way round, and a day earlier
    # than the UTC timestamp the scrape carried.
    write_bundle(season, [make_dual(800_000_001, 101, 102, f"{YEAR}-04-07", 6, 700_001_000)])
    stats = merge.merge_year(YEAR)
    assert stats["scraped_replaced"] == 2

    rankings, _, _, _ = build(season)
    alpha = entry_for(rankings, 101)
    assert alpha["record"] == "1-0-0", "the coach's result did not override the scrape"
    assert alpha["total_flights_played"] == 8, "the six-flight scrape is still being counted"


def test_a_dual_is_never_counted_twice(season):
    """The failure that would corrupt silently rather than loudly."""
    write_bundle(season, [make_dual(800_000_001, 101, 102, f"{YEAR}-04-07", 6, 700_001_000)])
    merge.merge_year(YEAR)
    merge.merge_year(YEAR)          # a re-run must not accumulate
    rankings, _, _, _ = build(season)

    alpha = entry_for(rankings, 101)
    assert alpha["record"] == "1-0-0"
    assert alpha["total_flights_played"] == 8


def test_the_seeding_packet_renders_the_reported_season(season, monkeypatch, tmp_path):
    """The export a committee prints, built from the same merged season."""
    write_bundle(season, [
        make_dual(800_000_001, 101, 102, f"{YEAR}-04-07", 6, 700_001_000),
        make_dual(800_000_002, 103, 104, f"{YEAR}-04-07", 5, 700_002_000),
    ])
    merge.merge_year(YEAR)
    rankings, _, _, _ = build(season)

    out = tmp_path / "seeding"
    ranked = tmp_path / "processed_rankings.json"
    ranked.write_text(json.dumps(rankings))
    monkeypatch.setattr(build_seeding_packet, "RANKINGS", str(ranked))
    monkeypatch.setattr(build_seeding_packet, "DATA_DIR", str(season["data"]))
    monkeypatch.setattr(build_seeding_packet, "OUT_ROOT", str(out))
    monkeypatch.setattr(build_seeding_packet, "LINEUPS_DIR", str(tmp_path / "no-lineups"))

    assert build_seeding_packet.main(["--year", str(YEAR)]) == 0

    page = (out / str(YEAR) / "5a-9-test-girls.html").read_text()
    assert "Alpha" in page and "Delta" in page
    assert "<b>2</b> league duals on file" in page
    # Every dual came from a coach, and the packet has to say so.
    assert "2 reported by coaches, 0 imported" in page
    assert "Scorecards" in page
