"""The merge that puts entered duals over the scrape.

The failure this file exists to prevent is a dual surviving twice — once scraped,
once entered — which inflates a record and silently corrupts every metric
downstream of it. The other half is the reverse: a build with no entered data
must leave `data/` byte-identical, because that is what makes the whole system
safe to ship before anyone has typed anything.
"""
import json
import os

import pytest

import merge_entered_data as merge
from entered_shape import compile_meet

from conftest import AWAY_ID, HOME_ID


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Redirect the merger at a temporary data/, data_jv/ and entered/."""
    data = tmp_path / "data"
    data_jv = tmp_path / "data_jv"
    bundle = tmp_path / "entered"
    for d in (data, data_jv, bundle):
        d.mkdir()
    monkeypatch.setattr(merge, "DATA_DIR", str(data))
    monkeypatch.setattr(merge, "JV_DATA_DIR", str(data_jv))
    monkeypatch.setattr(merge, "BUNDLE_DIR", str(bundle))
    return tmp_path


def write_bundle(workspace, year, duals):
    d = workspace / "entered" / str(year)
    d.mkdir(parents=True, exist_ok=True)
    meets = [compile_meet(x) for x in duals]
    (d / "entered_meets.json").write_text(json.dumps({"year": year, "meets": meets}))
    return meets


def scraped_meet(meet_id, date, home_id, away_id, home_score, away_score, flights=3):
    """A minimal scraped dual, in the shape fetch_data.py stores."""
    lines = []
    for i in range(flights):
        lines.append({
            "id": 1_500_000 + meet_id * 10 + i,
            "flight": str(i + 1), "matchType": "Singles",
            "winnerTeamId": 3_100_000 + i, "genderId": 2, "isNotVarsity": False,
            "sets": [{str(3_100_000 + i): 6, str(3_200_000 + i): 3,
                      "number": 1, "tie": None}],
            "matchTeams": [
                {"id": 3_100_000 + i, "isWinner": True, "players": [
                    {"id": 170_000 + i, "firstName": "S", "lastName": f"H{i}",
                     "grade": "11", "genderId": 2, "schoolId": home_id,
                     "school": {"name": "Home", "logo": ""},
                     "matchTeamPlayer": {"position": 1}}]},
                {"id": 3_200_000 + i, "isWinner": False, "players": [
                    {"id": 180_000 + i, "firstName": "S", "lastName": f"A{i}",
                     "grade": "11", "genderId": 2, "schoolId": away_id,
                     "school": {"name": "Away", "logo": ""},
                     "matchTeamPlayer": {"position": 1}}]},
            ],
        })
    hi = {"id": home_id, "name": "Home", "logo": "", "score": home_score}
    ai = {"id": away_id, "name": "Away", "logo": "", "score": away_score}
    winners, losers = ([hi], [ai]) if home_score >= away_score else ([ai], [hi])
    return {
        "id": meet_id, "title": "Away at Home",
        "meetDateTime": f"{date}T23:30:00.000Z",
        "postSeason": False, "approveMeet": True, "eventId": None,
        "winnerSchoolId": None, "coach": None, "meetRecap": None,
        "schools": {"winners": winners, "losers": losers},
        "matches": {"Singles": lines, "Doubles": []},
    }


def write_school(workspace, year, school_id, gender, meets, base="data"):
    d = workspace / base / str(year)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"school_{school_id}_gender_{gender}.json"
    path.write_text(json.dumps({
        "school": {"id": school_id, "name": "Test"},
        "coaches": [],
        "overallRecord": {"win": 1, "loss": 0, "tie": 0},
        "meets": meets,
    }, indent=2))
    return path


def read(path):
    return json.loads(path.read_text())


# ---------------------------------------------------------------------------


def test_no_bundle_leaves_data_untouched(workspace):
    path = write_school(workspace, 2027, HOME_ID, 2,
                        [scraped_meet(1, "2027-04-14", HOME_ID, AWAY_ID, 5, 3)])
    before = path.read_bytes()
    stats = merge.merge_year(2027)
    assert stats["files_written"] == 0
    assert path.read_bytes() == before


def test_entered_dual_replaces_the_scraped_twin(workspace, full_card_dual):
    write_bundle(workspace, 2027, [full_card_dual])
    home = write_school(workspace, 2027, HOME_ID, 2,
                        [scraped_meet(1, "2027-04-14", HOME_ID, AWAY_ID, 4, 2)])
    away = write_school(workspace, 2027, AWAY_ID, 2,
                        [scraped_meet(1, "2027-04-14", HOME_ID, AWAY_ID, 4, 2)])

    stats = merge.merge_year(2027)
    assert stats["scraped_replaced"] == 2  # once in each school's file

    for path in (home, away):
        meets = read(path)["meets"]
        assert len(meets) == 1, "the scraped copy must be gone, not appended to"
        assert meets[0]["source"] == "entered"
        assert meets[0]["schools"]["winners"][0]["score"] == 5


def test_utc_date_skew_still_matches(workspace, full_card_dual):
    """A scraped dual stamped the following day is the same dual."""
    write_bundle(workspace, 2027, [full_card_dual])
    # Played 4/14 local, scraped as 4/15 because the meet ran past midnight UTC.
    path = write_school(workspace, 2027, HOME_ID, 2,
                        [scraped_meet(1, "2027-04-15", HOME_ID, AWAY_ID, 4, 2)])

    stats = merge.merge_year(2027)
    assert stats["date_skew_matches"] >= 1
    assert len(read(path)["meets"]) == 1


def test_unrelated_dual_survives(workspace, full_card_dual):
    """Only the matching dual is replaced — the rest of the season stays."""
    write_bundle(workspace, 2027, [full_card_dual])
    other = scraped_meet(2, "2027-04-21", HOME_ID, 99999, 6, 2)
    path = write_school(workspace, 2027, HOME_ID, 2,
                        [scraped_meet(1, "2027-04-14", HOME_ID, AWAY_ID, 4, 2), other])

    merge.merge_year(2027)
    meets = read(path)["meets"]
    assert len(meets) == 2
    assert {m["id"] for m in meets} == {2, full_card_dual["dual_id"]}


def test_merging_twice_is_idempotent(workspace, full_card_dual):
    write_bundle(workspace, 2027, [full_card_dual])
    path = write_school(workspace, 2027, HOME_ID, 2,
                        [scraped_meet(1, "2027-04-14", HOME_ID, AWAY_ID, 4, 2)])

    merge.merge_year(2027)
    first = path.read_bytes()
    merge.merge_year(2027)
    assert path.read_bytes() == first


def test_a_removed_dual_is_not_left_behind(workspace, full_card_dual):
    """Voiding a dual in the database removes it from the files on the next run."""
    write_bundle(workspace, 2027, [full_card_dual])
    path = write_school(workspace, 2027, HOME_ID, 2, [])
    merge.merge_year(2027)
    assert len(read(path)["meets"]) == 1

    write_bundle(workspace, 2027, [])          # dual voided
    merge.merge_year(2027)
    assert read(path)["meets"] == []


def test_file_is_created_for_a_school_with_no_scrape(workspace, full_card_dual):
    write_bundle(workspace, 2027, [full_card_dual])
    stats = merge.merge_year(2027)
    assert stats["files_created"] == 2
    path = workspace / "data" / "2027" / f"school_{HOME_ID}_gender_2.json"
    assert path.exists()
    assert read(path)["school"]["name"] == "Stayton"


def test_overall_record_is_recomputed(workspace, full_card_dual):
    write_bundle(workspace, 2027, [full_card_dual])
    home = write_school(workspace, 2027, HOME_ID, 2,
                        [scraped_meet(1, "2027-04-14", HOME_ID, AWAY_ID, 2, 6)])
    away = write_school(workspace, 2027, AWAY_ID, 2,
                        [scraped_meet(1, "2027-04-14", HOME_ID, AWAY_ID, 2, 6)])

    merge.merge_year(2027)
    # The scrape had home losing; the entered dual has home winning 5-3, and the
    # header record has to follow the match log rather than contradict it.
    assert read(home)["overallRecord"] == {"win": 1, "loss": 0, "tie": 0}
    assert read(away)["overallRecord"] == {"win": 0, "loss": 1, "tie": 0}


def test_jv_never_lands_in_the_varsity_directory(workspace, full_card_dual):
    """build_rankings globs school_*_gender_*.json — JV in data/ would rank."""
    jv = dict(full_card_dual)
    jv["is_jv"] = True
    write_bundle(workspace, 2027, [jv])

    stats = merge.merge_year(2027)
    assert stats["jv_meets"] == 1

    assert not (workspace / "data" / "2027").exists() or \
        list((workspace / "data" / "2027").glob("*.json")) == []
    assert (workspace / "data_jv" / "2027" /
            f"school_{HOME_ID}_gender_2.json").exists()


def test_dry_run_writes_nothing(workspace, full_card_dual):
    write_bundle(workspace, 2027, [full_card_dual])
    path = write_school(workspace, 2027, HOME_ID, 2,
                        [scraped_meet(1, "2027-04-14", HOME_ID, AWAY_ID, 4, 2)])
    before = path.read_bytes()

    stats = merge.merge_year(2027, dry_run=True)
    assert stats["files_written"] == 2
    assert path.read_bytes() == before


def test_duplicate_duals_raise_rather_than_corrupt(workspace, full_card_dual, monkeypatch):
    """If key removal ever misses, fail the build instead of double-counting."""
    write_bundle(workspace, 2027, [full_card_dual])
    write_school(workspace, 2027, HOME_ID, 2,
                 [scraped_meet(1, "2027-04-14", HOME_ID, AWAY_ID, 4, 2)])
    # Simulate the removal failing by shrinking the tolerance below zero.
    monkeypatch.setattr(merge, "DATE_TOLERANCE_DAYS", -1)
    with pytest.raises(AssertionError, match="share"):
        merge.merge_year(2027)
