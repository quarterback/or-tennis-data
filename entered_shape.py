#!/usr/bin/env python3
"""Render coach-entered duals in TennisReporting meet shape.

This is the adapter at the centre of the reporting system. Coaches enter duals
into Postgres; this module turns one of those duals into the exact dict shape
that `generate_site.py` and `build_lineup_data.py` already consume, so the
ranking pipeline never learns that a second data source exists.

Pure functions only — no database, no filesystem, no network. `export_entered_meets.py`
supplies the rows and `merge_entered_data.py` places the output; both are testable
against this module without either of those.

The input is a normalized "dual dict":

    {
      "dual_id": 800000042, "year": 2027, "gender_id": 2, "is_jv": False,
      "played_on": "2027-04-14", "is_postseason": False, "event_name": None,
      "status": "confirmed",
      "home": {"school_id": 74614, "name": "Stayton"},
      "away": {"school_id": 124656, "name": "Valley Catholic School"},
      "lines": [
        {"line_id": 700000001, "match_type": "Singles", "flight": 1,
         "home_won": True, "finish": None,
         "home_players": [{"id": 900000001, "first_name": "A", "last_name": "B",
                           "grade": "11"}],
         "away_players": [...],
         "sets": [{"number": 1, "home": 6, "away": 3, "tie": None}, ...]},
        ...
      ]
    }
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Reserved ID ranges. Must match the sequence starts in db/schema.sql.
#
# Every observed TennisReporting id sits far below these: schools top out around
# 7.07M, players 200k, meets 225k, match lines 1.6M, matchTeams 3.2M. Starting
# at 600M leaves no room for ambiguity about which system minted an id, which is
# what makes the merge idempotent — it can recognise and replace its own output.
# ---------------------------------------------------------------------------
RESERVED_MATCHTEAM_MIN = 600_000_000
RESERVED_LINE_MIN = 700_000_000
RESERVED_MEET_MIN = 800_000_000
RESERVED_PLAYER_MIN = 900_000_000


def match_team_id(line_id: int, side: str) -> int:
    """Deterministic matchTeam id for one side of a line.

    Derived rather than stored: the same line always yields the same pair, so a
    recompiled meet is byte-identical to the last one.
    """
    if line_id < RESERVED_LINE_MIN:
        raise ValueError(f"line id {line_id} is outside the reserved range")
    offset = (line_id - RESERVED_LINE_MIN) * 2 + (0 if side == "home" else 1)
    mt = RESERVED_MATCHTEAM_MIN + offset
    if mt >= RESERVED_LINE_MIN:
        # Would need ~50M entered lines in one database to reach this; a season
        # is roughly 30k. Fail loudly rather than silently colliding.
        raise ValueError("matchTeam id space exhausted")
    return mt


def is_reserved_meet(meet: dict) -> bool:
    """True when this meet was produced by us rather than scraped."""
    try:
        return int(meet.get("id") or 0) >= RESERVED_MEET_MIN
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Titles
#
# `is_dual_match` (generate_site.py:336) rejects a meet whose title contains
# "State Championship", "District", or "Event" together with a ".". Those are
# TennisReporting's individual-tournament meets, and a compiled dual that trips
# the filter contributes nothing to the record, FWS, head-to-head or league
# standings. So the title is load-bearing, and it never carries the event name —
# a district team playoff is still a dual and still has to count.
# ---------------------------------------------------------------------------

def title_is_dual_safe(title: str) -> bool:
    if "State Championship" in title:
        return False
    if "District" in title:
        return False
    if "Event" in title and "." in title:
        return False
    return True


def dual_title(home_name: str, away_name: str) -> str:
    title = f"{away_name} at {home_name}"
    if title_is_dual_safe(title):
        return title
    # A school name collided with the tournament filter. Fall back to a title
    # that cannot, and accept the loss of readability over the loss of the dual.
    return "Dual match"


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def flight_score(lines: list[dict]) -> tuple[int, int]:
    """(home flights won, away flights won). Unplayed lines count for neither."""
    home = sum(1 for ln in lines if ln.get("home_won") is True)
    away = sum(1 for ln in lines if ln.get("home_won") is False)
    return home, away


def _sets_and_games(lines: list[dict]) -> tuple[int, int, int, int]:
    """(home sets, away sets, home games, away games) across every line."""
    hs = aw = hg = ag = 0
    for ln in lines:
        for s in ln.get("sets") or []:
            h, a = s.get("home"), s.get("away")
            if not isinstance(h, int) or not isinstance(a, int):
                continue
            hg += h
            ag += a
            if h > a:
                hs += 1
            elif a > h:
                aw += 1
    return hs, aw, hg, ag


def tiebreak_winner(dual: dict) -> int | None:
    """Oregon's dual tiebreaker when flight scores are level: sets, then games.

    Returned as a school id for the meet's `winnerSchoolId`, which is what
    `get_meet_result` (generate_site.py:401) falls back to on a tie. Returns None
    when even games are level — a genuine tie, which the pipeline records as one.
    """
    hs, aws, hg, ag = _sets_and_games(dual["lines"])
    if hs != aws:
        return dual["home"]["school_id"] if hs > aws else dual["away"]["school_id"]
    if hg != ag:
        return dual["home"]["school_id"] if hg > ag else dual["away"]["school_id"]
    return None


# ---------------------------------------------------------------------------
# Compilation
# ---------------------------------------------------------------------------

def _logo(school_id: int) -> str:
    return f"school_{school_id}.png"


def _player(p: dict, school: dict, gender_id: int, position: int) -> dict:
    return {
        "id": int(p["id"]),
        "firstName": p.get("first_name") or "",
        "lastName": p.get("last_name") or "",
        "grade": str(p.get("grade") or ""),
        "genderId": gender_id,
        "schoolId": school["school_id"],
        "updatedAt": None,
        "graduatedDate": None,
        "school": {"name": school["name"], "logo": _logo(school["school_id"])},
        "matchTeamPlayer": {"position": position},
    }


def _line(ln: dict, dual: dict) -> dict:
    """One flight, in TR match shape."""
    line_id = int(ln["line_id"])
    home_mt = match_team_id(line_id, "home")
    away_mt = match_team_id(line_id, "away")
    gender_id = dual["gender_id"]
    home_won = ln.get("home_won")

    # Set scores are keyed by matchTeam id as a STRING, alongside "number" and
    # "tie" (the losing side's tiebreak points). That asymmetry — string keys in
    # `sets`, integer ids in `matchTeams` — is TennisReporting's, and both
    # `score_str` in build_lineup_data.py and the game-share accounting in
    # generate_site.py read it that way.
    #
    # A third set entered as a 10-point match tiebreak needs no special casing:
    # the game-share code detects it as set 3 with a value >= 10 and scores it as
    # one decision rather than seventeen games.
    sets = []
    for s in sorted(ln.get("sets") or [], key=lambda x: x.get("number") or 0):
        sets.append({
            str(home_mt): s.get("home"),
            str(away_mt): s.get("away"),
            "number": s.get("number"),
            "tie": s.get("tie"),
        })

    home_team = {
        "id": home_mt,
        "isWinner": home_won is True,
        "players": [
            _player(p, dual["home"], gender_id, i + 1)
            for i, p in enumerate(ln.get("home_players") or [])
        ],
    }
    away_team = {
        "id": away_mt,
        "isWinner": home_won is False,
        "players": [
            _player(p, dual["away"], gender_id, i + 1)
            for i, p in enumerate(ln.get("away_players") or [])
        ],
    }

    winner_team_id = None
    if home_won is True:
        winner_team_id = home_mt
    elif home_won is False:
        winner_team_id = away_mt

    return {
        "id": line_id,
        "flight": str(ln["flight"]),
        "matchType": ln["match_type"],
        "finish": ln.get("finish"),
        "winnerTeamId": winner_team_id,
        "genderId": gender_id,
        "isNotVarsity": bool(dual.get("is_jv")),
        "sets": sets,
        "matchTeams": [home_team, away_team],
    }


def compile_meet(dual: dict) -> dict:
    """Render one entered dual as a TennisReporting meet."""
    home, away = dual["home"], dual["away"]
    home_flights, away_flights = flight_score(dual["lines"])

    home_side = {
        "id": home["school_id"], "name": home["name"],
        "logo": _logo(home["school_id"]), "score": home_flights,
        "winnerSchoolId": None,
    }
    away_side = {
        "id": away["school_id"], "name": away["name"],
        "logo": _logo(away["school_id"]), "score": away_flights,
        "winnerSchoolId": None,
    }

    # `is_dual_match` requires exactly one winner and one loser. On a level
    # flight score the placement is arbitrary and `winnerSchoolId` carries the
    # real answer, which is precisely the path get_meet_result takes.
    winner_school_id = None
    if home_flights > away_flights:
        winners, losers = [home_side], [away_side]
    elif away_flights > home_flights:
        winners, losers = [away_side], [home_side]
    else:
        winner_school_id = tiebreak_winner(dual)
        if winner_school_id == away["school_id"]:
            winners, losers = [away_side], [home_side]
        else:
            winners, losers = [home_side], [away_side]

    lines = sorted(
        dual["lines"],
        key=lambda ln: (ln["match_type"] != "Singles", int(ln["flight"])),
    )

    return {
        "id": int(dual["dual_id"]),
        "title": dual_title(home["name"], away["name"]),
        # Downstream slices this to ten characters for the date. Scraped values
        # are UTC and some land after local midnight — one 2026 meet played on
        # 5/11 is stamped 2026-05-12T01:36:09Z. Noon UTC keeps an entered date
        # reading correctly no matter which way a consumer rounds.
        "meetDateTime": f"{dual['played_on']}T12:00:00.000Z",
        "postSeason": bool(dual.get("is_postseason")),
        "approveMeet": True,
        "eventId": None,
        "winnerSchoolId": winner_school_id,
        "coach": None,
        "meetRecap": None,
        "schools": {"winners": winners, "losers": losers},
        "matches": {
            "Singles": [_line(ln, dual) for ln in lines if ln["match_type"] == "Singles"],
            "Doubles": [_line(ln, dual) for ln in lines if ln["match_type"] == "Doubles"],
        },
        # Additive provenance. Nothing downstream reads these today; they make a
        # compiled meet self-describing in the committed JSON and give the
        # seeding packet something to label a contested result with.
        "source": "entered",
        "status": dual.get("status"),
        "contested": dual.get("status") == "contested",
        "eventName": dual.get("event_name"),
        "level": "jv" if dual.get("is_jv") else "varsity",
    }
