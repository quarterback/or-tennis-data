#!/usr/bin/env python3
"""One reader for a season's duals, shared by everything that needs them.

`data/<year>/school_<id>_gender_<g>.json` holds each dual twice — once in each
school's file — and after the merge step some of those duals are coach-reported
and some imported. Three separate consumers now need "the season's duals, each
one once, best version": the scoreboard, the committee evaluation data, and the
seeding packet. This is that function, so they cannot drift apart on which copy
of a dual they believe.

Precedence matches `dedupe_meets` in generate_site.py: same date and same
unordered pair of schools is the same dual; a coach-reported version beats an
imported one; among equals, more recorded flights wins.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict

from scoreline import result_letter, scoreline, tiebreak

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")

SLOT_LABEL = {"S1": "1S", "S2": "2S", "S3": "3S", "S4": "4S",
              "D1": "1D", "D2": "2D", "D3": "3D", "D4": "4D"}
GENDERS = {1: "Boys", 2: "Girls"}


def two_team(meet: dict) -> tuple[int, int] | None:
    schools = meet.get("schools") or {}
    winners = schools.get("winners") or []
    losers = schools.get("losers") or []
    if len(winners) != 1 or len(losers) != 1:
        return None
    a, b = winners[0].get("id"), losers[0].get("id")
    return None if a is None or b is None else (a, b)


def _side(meet: dict, school_id: int) -> dict:
    for key in ("winners", "losers"):
        for s in (meet.get("schools") or {}).get(key) or []:
            if s.get("id") == school_id:
                return s
    return {}


def load_year(year: int, gender_id: int | None = None, data_dir: str | None = None) -> list[dict]:
    """Every dual of a season, deduplicated, newest first.

    Each entry carries the raw meet under `meet` so a caller that wants the box
    score has it, plus the fields every caller needs.
    """
    base = data_dir or DATA_DIR
    year_dir = os.path.join(base, str(year))
    if not os.path.isdir(year_dir):
        return []

    best: dict[tuple, dict] = {}
    for name in sorted(os.listdir(year_dir)):
        if not (name.startswith("school_") and name.endswith(".json")):
            continue
        parts = os.path.splitext(name)[0].split("_")
        try:
            file_gender = int(parts[3])
        except (IndexError, ValueError):
            continue
        if gender_id is not None and file_gender != gender_id:
            continue

        with open(os.path.join(year_dir, name), encoding="utf-8") as f:
            doc = json.load(f)

        for meet in doc.get("meets") or []:
            pair = two_team(meet)
            if not pair:
                continue
            date = (meet.get("meetDateTime") or "")[:10]
            if not date:
                continue
            key = (date, min(pair), max(pair), file_gender)
            flights = sum(len(v or []) for v in (meet.get("matches") or {}).values())
            rank = (1 if meet.get("source") == "entered" else 0, flights)
            if key not in best or rank > best[key]["_rank"]:
                best[key] = {"meet": meet, "_rank": rank, "gender_id": file_gender}

    out = []
    for (date, lo, hi, gid), holder in best.items():
        meet = holder["meet"]
        winners = (meet.get("schools") or {}).get("winners") or []
        losers = (meet.get("schools") or {}).get("losers") or []
        # `winners`/`losers` say who took the dual, which is not the same as who
        # hosted. The home team is not recorded in the feed, so nothing here
        # claims to know it — the scoreboard reads "A vs B", never "A at B".
        a, b = winners[0], losers[0]
        # TennisReporting files one side under `winners` even for a dual it left
        # undecided, so that placement is not evidence of anything when the
        # flight score is level. The winner is the higher score, or whoever the
        # tiebreaker named — and otherwise nobody.
        level = a.get("score") == b.get("score")
        if not level:
            winner_id = a.get("id") if (a.get("score") or 0) > (b.get("score") or 0) else b.get("id")
        else:
            winner_id = meet.get("winnerSchoolId")

        out.append({
            "date": date,
            "gender_id": gid,
            "gender": GENDERS.get(gid, ""),
            "meet_id": meet.get("id"),
            "title": meet.get("title") or "",
            "postseason": bool(meet.get("postSeason")),
            "source": meet.get("source") or "imported",
            "contested": bool(meet.get("contested")),
            # `winner`/`loser` are the two sides as filed; `winner_id` is the
            # only statement about who actually won, and it is None for a tie.
            "winner": {"id": a.get("id"), "name": a.get("name"), "score": a.get("score")},
            "loser": {"id": b.get("id"), "name": b.get("name"), "score": b.get("score")},
            "level": level,
            "winner_id": winner_id,
            "tied": winner_id is None,
            "tiebreak": tiebreak(meet, a.get("id")),
            "scoreline": scoreline(meet, a.get("id")),
            "meet": meet,
        })
    out.sort(key=lambda d: (d["date"], str(d["winner"]["name"])), reverse=True)
    return out


def box_score(meet: dict, home_id: int, away_id: int) -> list[dict]:
    """Every flight of a dual, in card order, from the home side's perspective."""
    rows = []
    order = [("Singles", f) for f in (1, 2, 3, 4)] + [("Doubles", f) for f in (1, 2, 3, 4)]
    for match_type, flight in order:
        line = next(
            (m for m in (meet.get("matches") or {}).get(match_type, []) or []
             if str(m.get("flight")) == str(flight)), None)
        if line is None:
            continue
        slot = f"{match_type[0]}{flight}"

        teams = line.get("matchTeams") or []
        home_team = away_team = None
        for team in teams:
            players = team.get("players") or []
            if any(p.get("schoolId") == home_id for p in players):
                home_team = team
            elif any(p.get("schoolId") == away_id for p in players):
                away_team = team
        # A defaulted flight has players on one side only; the empty side is
        # whichever team is left over.
        leftovers = [t for t in teams if t is not home_team and t is not away_team]
        if home_team is None and leftovers:
            home_team = leftovers.pop(0)
        if away_team is None and leftovers:
            away_team = leftovers.pop(0)

        def names(team):
            return [f"{(p.get('firstName') or '').strip()} {(p.get('lastName') or '').strip()}".strip()
                    for p in (team or {}).get("players") or []]

        sets = []
        if home_team and away_team:
            hid, aid = home_team.get("id"), away_team.get("id")
            for s in sorted(line.get("sets") or [], key=lambda x: x.get("number") or 0):
                h = s.get(str(hid), s.get(hid))
                a = s.get(str(aid), s.get(aid))
                if isinstance(h, int) and isinstance(a, int):
                    sets.append({"home": h, "away": a, "tie": s.get("tie")})

        rows.append({
            "slot": slot,
            "label": SLOT_LABEL[slot],
            "home_players": names(home_team),
            "away_players": names(away_team),
            "sets": sets,
            "home_won": bool(home_team and home_team.get("isWinner")),
            "away_won": bool(away_team and away_team.get("isWinner")),
            "finish": line.get("finish"),
        })
    return rows


def by_date(duals: list[dict]) -> dict[str, list[dict]]:
    out = defaultdict(list)
    for d in duals:
        out[d["date"]].append(d)
    return out
