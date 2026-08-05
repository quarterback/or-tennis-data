#!/usr/bin/env python3
"""Build the evaluation data for the state team-tournament selection committee.

The committee's job is to fill a field: each league champion takes an automatic
bid, and the committee picks the rest at large, then seeds the whole thing. It
does not need the site to make that decision — it needs to be able to *read* the
season. Who did each team beat. How good were they. Who did they lose to. How
deep is the roster across all eight positions.

Emits one file per classification and gender:

    public/data/committee/<year>/<classification>-<gender>.json

Each carries every team in the classification with a full résumé: every dual
with the opponent's rank attached, the record split by the quality of opponent,
the best win and worst loss, the flight-by-flight profile, and the ladder.

Automatic qualifiers are NOT derived. A league championship is a real-world
designation and the system does not guess at one — they are read from
`league_champions.csv`, which an administrator maintains. Leagues with nobody
designated are reported as undesignated so the gap is visible rather than
silently filled.

    python build_committee_data.py --year 2026
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import defaultdict

import generate_site as gs
from scoreline import result_letter, scoreline
from season_duals import load_year

ROOT = os.path.dirname(os.path.abspath(__file__))
RANKINGS = os.path.join(ROOT, "public", "data", "processed_rankings.json")
LINEUPS_DIR = os.path.join(ROOT, "public", "data", "lineups")
CHAMPIONS_CSV = os.path.join(ROOT, "league_champions.csv")
OUT_ROOT = os.path.join(ROOT, "public", "data", "committee")

GENDER_ID = {"Boys": 1, "Girls": 2}
SLOTS = ["S1", "S2", "S3", "S4", "D1", "D2", "D3", "D4"]

# The state team tournament field, per classification. Every league or special
# district takes an automatic bid; the committee picks the remainder at large.
#
#   6A      12 teams, 7 leagues          -> 7 automatic, 5 at large
#   5A       8 teams, 4 leagues          -> 4 automatic, 4 at large
#   4A-1A    8 teams, 5 special districts-> 5 automatic, 3 at large
#
# (docs/team-championship-proposal-v2.md still shows an earlier 16-team draft;
# these are the sizes that were actually settled on.)
FIELD_SIZE = {"6A": 12, "5A": 8, "4A/3A/2A/1A": 8}


def load_champions() -> dict:
    """(year, classification, gender, league) -> {school_id, note}.

    Hand-entered overrides only. Nobody publishes Oregon's league champions —
    they are not documented anywhere — so this file exists for the cases where
    someone actually knows (a league tournament, a coaches' vote) and wants to
    correct what the standings imply.
    """
    out = {}
    if not os.path.exists(CHAMPIONS_CSV):
        return out
    with open(CHAMPIONS_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                key = (int(row["year"]), row["classification"].strip(),
                       row["gender"].strip(), row["league"].strip())
                out[key] = {"school_id": int(row["school_id"]),
                            "note": (row.get("note") or "").strip()}
            except (KeyError, ValueError):
                continue
    return out


def _league_win_pct(team: dict) -> float | None:
    w = team.get("league_wins") or 0
    l = team.get("league_losses") or 0
    t = team.get("league_ties") or 0
    played = w + l + t
    if not played:
        return None
    # Same convention as the overall record: a tie is half a win, which is what
    # a 4-4 is worth.
    return (w + t * 0.5) / played


def derive_champion(members: list[dict], duals_by_pair: dict) -> dict | None:
    """The league champion, by league win percentage.

    Oregon does not publish league champions, so the best available answer is
    the team that won its league. Ties on win percentage go to head-to-head
    between the tied teams, then to Power Index — and a tie broken by the head
    to head uses the head-to-head answer, where losing a 4-4 tiebreaker IS a
    loss.

    Returns None when no member played a league match.
    """
    scored = [(t, _league_win_pct(t)) for t in members]
    scored = [(t, p) for t, p in scored if p is not None]
    if not scored:
        return None

    best = max(p for _, p in scored)
    contenders = [t for t, p in scored if p == best]
    if len(contenders) == 1:
        return {"team": contenders[0], "basis": "league record", "tied_with": []}

    # Head to head among the tied teams only.
    def h2h_points(team):
        pts = 0
        for other in contenders:
            if other is team:
                continue
            for letter in duals_by_pair.get(
                    (team["school_id"], other["school_id"]), []):
                pts += 1 if letter == "W" else (-1 if letter == "L" else 0)
        return pts

    ranked = sorted(
        contenders,
        key=lambda t: (h2h_points(t), t.get("power_index") or 0),
        reverse=True)
    top = ranked[0]
    basis = ("league record, head to head"
             if h2h_points(top) != h2h_points(ranked[1]) else
             "league record, Power Index")
    return {
        "team": top,
        "basis": basis,
        "tied_with": [t["school_name"] for t in contenders if t is not top],
    }


def load_ladder(year, gender_id, school_id):
    path = os.path.join(LINEUPS_DIR, str(year), f"{gender_id}{school_id}.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    return [
        {"name": p["name"], "grade": p.get("grade") or "",
         "primary": p.get("primary"), "record": p.get("rec")}
        for p in (doc.get("ladder") or [])[:10]
    ]


def build(year: int, classification: str, gender: str, entries: list[dict],
          duals: list[dict], champions: dict) -> dict | None:
    gender_id = GENDER_ID[gender]
    teams = [e for e in entries
             if e["classification"] == classification and e["gender"] == gender]
    if len(teams) < 2:
        return None
    teams.sort(key=lambda e: (e["class_rank"] is None,
                              e["class_rank"] if e["class_rank"] is not None else 999))

    field = FIELD_SIZE.get(classification, 8)
    leagues = sorted({t["league"] for t in teams if t.get("league")})
    class_rank = {t["school_id"]: t["class_rank"] for t in teams}
    by_id = {t["school_id"]: t for t in teams}

    # Every dual involving one of our teams, indexed by school.
    per_team = defaultdict(list)
    duals_by_pair = defaultdict(list)
    for d in duals:
        if d["gender_id"] != gender_id:
            continue
        for side, other in (("winner", "loser"), ("loser", "winner")):
            sid = d[side]["id"]
            if sid in by_id:
                per_team[sid].append((d, d[other]["id"]))
                duals_by_pair[(sid, d[other]["id"])].append(
                    {"win": "W", "loss": "L", "tie": "T"}.get(
                        gs.get_meet_result(d["meet"], sid, for_h2h=True), "T"))

    # Champions: an administrator's designation if there is one, otherwise the
    # team that won the league. Nobody publishes Oregon's league champions, so
    # deriving is the only way the board has automatic bids at all — but the
    # basis is carried through to the page so a committee can see it was
    # inferred from the standings rather than reported by anyone.
    champion_by_league = {}
    for league in leagues:
        override = champions.get((year, classification, gender, league))
        if override and override["school_id"] in by_id:
            champion_by_league[league] = {
                "schoolId": override["school_id"],
                "name": by_id[override["school_id"]]["school_name"],
                "basis": override["note"] or "entered by an administrator",
                "derived": False,
                "tiedWith": [],
            }
            continue
        members = [t for t in teams if t.get("league") == league]
        got = derive_champion(members, duals_by_pair)
        if got:
            champion_by_league[league] = {
                "schoolId": got["team"]["school_id"],
                "name": got["team"]["school_name"],
                "basis": got["basis"],
                "derived": True,
                "tiedWith": got["tied_with"],
            }

    champion_ids = {c["schoolId"] for c in champion_by_league.values()}

    out_teams = []
    for t in teams:
        sid = t["school_id"]
        results = []
        bands = {"field": [0, 0, 0], "next": [0, 0, 0], "rest": [0, 0, 0], "outside": [0, 0, 0]}
        best_win = worst_loss = None

        for d, opp_id in sorted(per_team.get(sid, []), key=lambda x: x[0]["date"], reverse=True):
            meet = d["meet"]
            letter = result_letter(meet, sid)
            # The record and the head-to-head disagree on a lost tiebreaker, and
            # a committee needs both: the record says the dual was level, the
            # head-to-head says who won the meeting.
            h2h = gs.get_meet_result(meet, sid, for_h2h=True)
            opp = by_id.get(opp_id)
            opp_rank = class_rank.get(opp_id)

            if opp is None:
                bucket = "outside"           # a team from another classification
            elif opp_rank is None:
                bucket = "rest"
            elif opp_rank <= field:
                bucket = "field"
            elif opp_rank <= field * 2:
                bucket = "next"
            else:
                bucket = "rest"
            idx = {"W": 0, "L": 1, "T": 2}.get(letter)
            if idx is not None:
                bands[bucket][idx] += 1

            row = {
                "date": d["date"],
                "opponentId": opp_id,
                "opponent": (opp or {}).get("school_name")
                            or d["winner" if d["winner"]["id"] == opp_id else "loser"]["name"],
                "opponentClassRank": opp_rank,
                "opponentClassification": (opp or {}).get("classification"),
                "opponentPowerIndex": (opp or {}).get("power_index"),
                "scoreline": scoreline(meet, sid),
                "result": letter,
                "h2h": {"win": "W", "loss": "L", "tie": "T"}.get(h2h, ""),
                "league": bool(opp and opp.get("league") == t.get("league")),
                "postseason": d["postseason"],
                "source": d["source"],
                "tied": d["tied"],
            }
            results.append(row)

            if letter == "W" and opp_rank is not None:
                if best_win is None or opp_rank < best_win["opponentClassRank"]:
                    best_win = row
            if letter == "L" and opp_rank is not None:
                if worst_loss is None or opp_rank > worst_loss["opponentClassRank"]:
                    worst_loss = row

        champ = champion_by_league.get(t.get("league"))
        is_champ = bool(champ and champ["schoolId"] == sid)
        out_teams.append({
            "schoolId": sid,
            "name": t["school_name"],
            "city": t.get("city"),
            "league": t.get("league"),
            "classRank": t.get("class_rank"),
            "stateRank": t.get("rank"),
            "leagueRank": t.get("league_rank"),
            "record": t.get("record"),
            "wins": t.get("wins"), "losses": t.get("losses"), "ties": t.get("ties"),
            "leagueRecord": t.get("league_record"),
            "powerIndex": t.get("power_index"),
            "apr": t.get("apr"),
            "owp": t.get("owp"),
            "oowp": t.get("oowp"),
            "fqi": t.get("fqi"),
            "ogs": t.get("ogs"),
            "gameShare": t.get("game_share"),
            "flightBreakdown": t.get("flight_breakdown") or {},
            "flightsWon": t.get("total_flights_won"),
            "flightsPlayed": t.get("total_flights_played"),
            "matchesPlayed": t.get("matches_played"),
            "autoBid": is_champ,
            "autoBidBasis": champ["basis"] if is_champ else "",
            "autoBidDerived": bool(is_champ and champ["derived"]),
            "autoBidTiedWith": champ["tiedWith"] if is_champ else [],
            "bands": bands,
            "bestWin": best_win,
            "worstLoss": worst_loss,
            "results": results,
            "ladder": load_ladder(year, gender_id, sid),
        })

    return {
        "year": year,
        "classification": classification,
        "gender": gender,
        "fieldSize": field,
        "leagues": leagues,
        "autoBids": len(leagues),
        "atLargeBids": max(0, field - len(leagues)),
        "champions": champion_by_league,
        # Leagues where nobody played a league match, so not even the standings
        # can suggest a champion.
        "undesignated": [lg for lg in leagues if lg not in champion_by_league],
        "derivedChampions": sorted(
            lg for lg, c in champion_by_league.items() if c["derived"]),
        "teams": out_teams,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--year", type=int, required=True)
    args = ap.parse_args(argv)

    with open(RANKINGS, encoding="utf-8") as f:
        entries = [e for e in json.load(f) if int(e["year"]) == args.year]
    if not entries:
        print(f"No ranking entries for {args.year}.")
        return 0

    duals = load_year(args.year)
    champions = load_champions()

    out_dir = os.path.join(OUT_ROOT, str(args.year))
    os.makedirs(out_dir, exist_ok=True)

    built = []
    for classification in sorted({e["classification"] for e in entries if e.get("classification")}):
        for gender in ("Boys", "Girls"):
            data = build(args.year, classification, gender, entries, duals, champions)
            if not data:
                continue
            slug = classification.replace("/", "").replace(" ", "").lower()
            name = f"{slug}-{gender.lower()}.json"
            with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
                json.dump(data, f, separators=(",", ":"))
            built.append({
                "classification": classification, "gender": gender, "file": name,
                "teams": len(data["teams"]), "fieldSize": data["fieldSize"],
                "autoBids": data["autoBids"], "atLargeBids": data["atLargeBids"],
                "undesignated": len(data["undesignated"]),
            })

    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"year": args.year, "fields": built}, f, separators=(",", ":"))

    missing = sum(b["undesignated"] for b in built)
    print(f"committee {args.year}: {len(built)} fields written to {out_dir}"
          + (f" — {missing} leagues have no champion designated" if missing else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
