"""The two reading surfaces: the scoreboard and the selection board.

Both are derived views over the merged season, so what they need to get right is
faithfulness — a result must not read one way on the scoreboard and another on
the board, and neither may assert a decision the data does not support.
"""
import json

import pytest

import build_committee_data as committee
import season_duals
from entered_shape import compile_meet
from season_duals import box_score, load_year, two_team

from conftest import AWAY_ID, HOME_ID, _line, _sets


def dual(lines, **kw):
    base = {
        "dual_id": 800_000_321, "year": 2027, "gender_id": 2, "is_jv": False,
        "played_on": "2027-04-14", "is_postseason": False, "event_name": None,
        "status": "confirmed",
        "home": {"school_id": HOME_ID, "name": "Stayton"},
        "away": {"school_id": AWAY_ID, "name": "Valley Catholic School"},
        "lines": lines,
    }
    base.update(kw)
    return base


def full_card(home_wins):
    order = [("Singles", f) for f in (1, 2, 3, 4)] + [("Doubles", f) for f in (1, 2, 3, 4)]
    return [_line(700_003_000 + i, mt, f, i < home_wins,
                  _sets((6, 2), (6, 3)) if i < home_wins else _sets((2, 6), (3, 6)))
            for i, (mt, f) in enumerate(order)]


@pytest.fixture
def season(tmp_path, monkeypatch):
    """A one-dual season on disk, in both schools' files."""
    year_dir = tmp_path / "data" / "2027"
    year_dir.mkdir(parents=True)
    meet = compile_meet(dual(full_card(5)))
    for school_id, name in ((HOME_ID, "Stayton"), (AWAY_ID, "Valley Catholic School")):
        (year_dir / f"school_{school_id}_gender_2.json").write_text(json.dumps({
            "school": {"id": school_id, "name": name},
            "coaches": [], "overallRecord": {"win": 0, "loss": 0, "tie": 0},
            "meets": [meet],
        }))
    monkeypatch.setattr(season_duals, "DATA_DIR", str(tmp_path / "data"))
    return tmp_path


# ---------------------------------------------------------------------------
# The shared reader
# ---------------------------------------------------------------------------

def test_a_dual_in_both_files_is_read_once(season):
    duals = load_year(2027)
    assert len(duals) == 1, "the same dual appears in both schools' files"
    assert duals[0]["scoreline"] == "5-3"
    assert duals[0]["winner_id"] == HOME_ID
    assert duals[0]["tied"] is False


def test_a_level_dual_with_no_recorded_winner_is_a_tie(season):
    """TennisReporting files one side under `winners` regardless, so the
    scoreboard cannot read that placement as a result."""
    meet = compile_meet(dual(full_card(4)))
    assert meet["winnerSchoolId"] is None      # level on flights, sets and games
    assert two_team(meet) is not None

    year_dir = season / "data" / "2027"
    for school_id in (HOME_ID, AWAY_ID):
        path = year_dir / f"school_{school_id}_gender_2.json"
        doc = json.loads(path.read_text())
        doc["meets"] = [meet]
        path.write_text(json.dumps(doc))

    d = load_year(2027)[0]
    assert d["tied"] is True
    assert d["winner_id"] is None
    assert d["scoreline"] == "4-4", "no parenthetical for a decision nobody made"


def test_the_box_score_covers_the_whole_card(season):
    d = load_year(2027)[0]
    rows = box_score(d["meet"], HOME_ID, AWAY_ID)
    assert [r["label"] for r in rows] == ["1S", "2S", "3S", "4S", "1D", "2D", "3D", "4D"]
    assert rows[0]["home_players"] and rows[0]["away_players"]
    assert rows[0]["sets"] == [{"home": 6, "away": 2, "tie": None},
                               {"home": 6, "away": 3, "tie": None}]
    assert sum(r["home_won"] for r in rows) == 5


def test_the_box_score_shows_a_default_as_one_sided(season):
    line = _line(700_004_000, "Singles", 1, True, [])
    line["finish"] = "default"
    line["away_players"] = []
    d = dual([line])
    rows = box_score(compile_meet(d), HOME_ID, AWAY_ID)
    assert rows[0]["home_players"] and rows[0]["away_players"] == []
    assert rows[0]["home_won"] is True
    assert rows[0]["finish"] == "default"


# ---------------------------------------------------------------------------
# The selection board
# ---------------------------------------------------------------------------

def test_field_sizes_match_the_settled_format():
    """12 in 6A, 8 in 5A and 8 in 4A-1A — not the 16s in the older proposal."""
    assert committee.FIELD_SIZE["6A"] == 12
    assert committee.FIELD_SIZE["5A"] == 8
    assert committee.FIELD_SIZE["4A/3A/2A/1A"] == 8


def test_auto_bids_are_never_inferred(tmp_path, monkeypatch):
    """A league championship is designated by a person, or it is open."""
    monkeypatch.setattr(committee, "CHAMPIONS_CSV", str(tmp_path / "none.csv"))
    assert committee.load_champions() == {}

    csv_path = tmp_path / "champs.csv"
    csv_path.write_text(
        "year,classification,gender,league,school_id,school_name,note\n"
        f"2027,6A,Girls,6A-2 Metro,{HOME_ID},Stayton,league tournament\n")
    monkeypatch.setattr(committee, "CHAMPIONS_CSV", str(csv_path))
    champs = committee.load_champions()
    assert champs[(2027, "6A", "Girls", "6A-2 Metro")]["school_id"] == HOME_ID


def test_the_published_committee_data_is_coherent():
    """Guards on the real 2026 build, which is the demonstration dataset."""
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    index_path = os.path.join(root, "public", "data", "committee", "2026", "index.json")
    if not os.path.exists(index_path):
        pytest.skip("committee data has not been generated")

    with open(index_path, encoding="utf-8") as f:
        index = json.load(f)
    assert index["fields"], "no fields were built"

    for field in index["fields"]:
        path = os.path.join(root, "public", "data", "committee", "2026", field["file"])
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        # Automatic bids equal the number of leagues; the rest are at large.
        assert data["autoBids"] == len(data["leagues"])
        assert data["autoBids"] + data["atLargeBids"] == data["fieldSize"]

        for team in data["teams"]:
            counted = sum(sum(b) for b in team["bands"].values())
            assert counted == len(team["results"]), (
                f"{team['name']}: {counted} banded against {len(team['results'])} results")
            if team["bestWin"]:
                assert team["bestWin"]["result"] == "W"
            if team["worstLoss"]:
                assert team["worstLoss"]["result"] == "L"
