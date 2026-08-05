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
from scoreline import result_letter, scoreline, tiebreak
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


# How close two teams' league win percentages have to be before head-to-head is
# allowed to reorder them. Matches the playoff simulator's threshold.
LEAGUE_H2H_BAND = 0.1

# The fewest league matches a team may have played and still be eligible to be
# named champion, expressed against the league's median.
CHAMPION_MIN_FLOOR = 3


def _league_played(team: dict) -> int:
    return ((team.get("league_wins") or 0) + (team.get("league_losses") or 0)
            + (team.get("league_ties") or 0))


def _champion_bar(members: list[dict]) -> int:
    """Half the league's median, with a floor.

    A 1-0-0 is not a better league season than 10-1-0, but win percentage says
    it is — and this decides an automatic bid, so it cannot. The bar travels
    between a twelve-team district and a five-team one instead of being a fixed
    number, and it is switched off entirely until somebody clears it, so an
    early-season league is not left with no champion at all.
    """
    counts = sorted(_league_played(t) for t in members)
    if not counts:
        return 0
    mid = len(counts) // 2
    median = counts[mid] if len(counts) % 2 else (counts[mid - 1] + counts[mid]) / 2
    return max(CHAMPION_MIN_FLOOR, int(median // 2))


def derive_champion(members: list[dict], duals_by_pair: dict) -> dict | None:
    """The league champion, using the league tiebreakers the site already has.

    Oregon does not publish league champions, so this has to be derived — but
    the rule is not a new one. It mirrors `loadTeamsForSelection` in the playoff
    simulator (inside generate_site.py's generated page), which is where the
    site already decides who tops a league and pre-checks them as the automatic
    bid:

      1. Sort by league win percentage, then Power Index.
      2. Repeatedly swap adjacent teams whose league win percentages are within
         0.1 of each other when the lower one won the head-to-head, until the
         order settles.
      3. The team on top is the champion.

    If the two ever disagreed the owner would find a board and a simulator
    naming different champions, so they follow the same steps. One deliberate
    difference: the simulator reads head-to-head from `h2h_nearby`, which only
    carries nearby opponents, while this has every dual — so where the simulator
    simply cannot see a pair, this is the better-informed answer.

    Head-to-head here is the strict question, where losing a 4-4 tiebreaker is a
    loss.

    Returns None when no member played a league match.
    """
    scored = [(t, _league_win_pct(t)) for t in members]
    scored = [(t, p) for t, p in scored if p is not None]
    if not scored:
        return None

    # Teams too far short of the league's usual match count cannot be champion
    # on a percentage nobody else had the chance to run up.
    bar = _champion_bar([t for t, _ in scored])
    eligible = [(t, p) for t, p in scored if _league_played(t) >= bar]
    if eligible:
        scored = eligible

    order = [t for t, _ in sorted(
        scored, key=lambda x: (x[1], x[0].get("power_index") or 0), reverse=True)]
    pct = {t["school_id"]: p for t, p in scored}

    def beat(a, b):
        """Did `a` win the head-to-head against `b`?"""
        letters = duals_by_pair.get((a["school_id"], b["school_id"]), [])
        return sum(1 for x in letters if x == "W") > sum(1 for x in letters if x == "L")

    swaps = []
    changed = True
    guard = 0
    while changed and guard < 50:
        changed = False
        guard += 1
        for i in range(len(order) - 1):
            a, b = order[i], order[i + 1]
            if abs(pct[a["school_id"]] - pct[b["school_id"]]) > LEAGUE_H2H_BAND:
                continue
            if beat(b, a):
                order[i], order[i + 1] = b, a
                swaps.append((b["school_name"], a["school_name"]))
                changed = True

    top = order[0]
    level = [t["school_name"] for t in order[1:]
             if pct[t["school_id"]] == pct[top["school_id"]]]
    if any(top["school_name"] == w for w, _ in swaps):
        basis = "league record, head to head"
    elif level:
        basis = "league record, Power Index"
    else:
        basis = "league record"
    return {"team": top, "basis": basis, "tied_with": level}


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
                # A 4-4 decided on sets is the tennis equivalent of a shootout:
                # the dual is a tie, and the parenthetical says who took the
                # tiebreaker. Null when nothing decided it, which is every
                # scraped tie — the feed records no winner for those.
                "tiebreak": (lambda tb: {"basis": tb[0], "ours": tb[1], "theirs": tb[2]}
                             if tb else None)(tiebreak(d["meet"], sid)),
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
