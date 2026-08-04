"""Guards on the published rankings.

The Power Index is tuned across five AAR documents and the numbers on the site
are the product of that tuning. Nothing in this repository checked it, so any
edit to `generate_site.py` — including the ones the reporting system needs — was
a change to every published number on faith.

These tests read the committed `public/data/processed_rankings.json` as the
reference. Regenerate it with `python generate_site.py` and re-read the diff when
one of them fails; a failure means the published numbers moved, which is
sometimes correct and never accidental.
"""
import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RANKINGS = os.path.join(ROOT, "public", "data", "processed_rankings.json")


@pytest.fixture(scope="module")
def rankings():
    if not os.path.exists(RANKINGS):
        pytest.skip("processed_rankings.json has not been generated")
    with open(RANKINGS, encoding="utf-8") as f:
        return json.load(f)


def test_entries_are_uniquely_keyed(rankings):
    keys = [(e["year"], e["gender"], e["school_id"]) for e in rankings]
    assert len(keys) == len(set(keys)), "a team appears twice in one season"


def test_ranked_teams_are_emitted_in_rank_order(rankings):
    """Array order is load-bearing for the site's default table sort."""
    by_season = {}
    for e in rankings:
        by_season.setdefault((e["year"], e["gender"]), []).append(e)
    for season, entries in by_season.items():
        ranks = [e["rank"] for e in entries if e["rank"] is not None]
        assert ranks == sorted(ranks), f"{season} is not in rank order"
        assert ranks == list(range(1, len(ranks) + 1)), f"{season} has a gap or duplicate rank"


def test_unranked_teams_have_every_rank_field_null(rankings):
    """MIN_RANKED_MATCHES: under three duals a team is NR, not rank 1."""
    fields = ("rank", "class_rank", "league_rank")
    for e in rankings:
        if e["rank"] is None:
            for f in fields:
                assert e.get(f) is None, f"{e['school_name']} is NR but has {f}"


def test_rank_and_league_rank_are_consistent(rankings):
    """A team above a league-mate in the state table cannot be below it in the league.

    This is the invariant the stale-league_rank fix in the 2026-04-26 changelog
    restored; nothing was pinning it.
    """
    groups = {}
    for e in rankings:
        if e["rank"] is None or e.get("league_rank") is None:
            continue
        groups.setdefault((e["year"], e["gender"], e["league"]), []).append(e)

    for key, entries in groups.items():
        entries.sort(key=lambda e: e["rank"])
        league_ranks = [e["league_rank"] for e in entries]
        assert league_ranks == sorted(league_ranks), (
            f"{key}: state rank and league rank disagree — {league_ranks}"
        )


def test_records_agree_with_match_counts(rankings):
    for e in rankings:
        wins, losses, ties = e["wins"], e["losses"], e["ties"]
        assert e["record"] == f"{wins}-{losses}-{ties}"
        assert e["league_wins"] + e["league_losses"] + e["league_ties"] <= wins + losses + ties


def test_power_index_components_are_in_range(rankings):
    for e in rankings:
        assert 0.0 <= e["apr"] <= 1.0, f"{e['school_name']} APR {e['apr']}"
        assert 0.0 <= e["power_index"] <= 1.0
        if e.get("game_share") is not None:
            assert 0.0 <= e["game_share"] <= 1.0


def test_flight_breakdown_covers_the_full_card(rankings):
    """All eight Oregon flights are represented, 4S and 4D included."""
    expected = {"S1", "S2", "S3", "S4", "D1", "D2", "D3", "D4"}
    for e in rankings:
        fb = e.get("flight_breakdown")
        if fb:
            assert set(fb) == expected, f"{e['school_name']}: {sorted(fb)}"


@pytest.mark.parametrize("season", [(2026, "Boys"), (2026, "Girls")])
def test_current_season_has_a_populated_table(rankings, season):
    year, gender = season
    entries = [e for e in rankings if e["year"] == year and e["gender"] == gender]
    assert len(entries) > 50, f"{season} looks truncated: {len(entries)} teams"
    assert entries[0]["rank"] == 1
