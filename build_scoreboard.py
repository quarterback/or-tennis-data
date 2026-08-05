#!/usr/bin/env python3
"""Build the scoreboard data: results by date, with a box score behind each one.

Every other sport's results page works the same way — a day's slate, each line a
final score, click through for the detail. Oregon tennis has never had one; the
dual results exist only as inputs to a ranking table. This makes them readable.

Emits, per season:

    public/data/scoreboard/<year>/index.json    dates, counts, team directory
    public/data/scoreboard/<year>/<date>.json   that day's duals, with box scores

Split by date so the page loads one day at a time rather than a season. A busy
Tuesday in May is about 40 KB.

    python build_scoreboard.py --year 2026
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict

from season_duals import box_score, by_date, load_year

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_ROOT = os.path.join(ROOT, "public", "data", "scoreboard")
MASTER_CSV = os.path.join(ROOT, "master_school_list.csv")


def load_school_meta() -> dict[int, dict]:
    meta = {}
    if not os.path.exists(MASTER_CSV):
        return meta
    with open(MASTER_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                meta[int(row["id"])] = {
                    "name": (row.get("name") or "").strip(),
                    "classification": (row.get("Classification") or "").strip(),
                    "league": (row.get("League") or "").strip(),
                }
            except (KeyError, ValueError):
                continue
    return meta


def build_year(year: int) -> dict:
    duals = load_year(year)
    if not duals:
        print(f"No duals for {year}.")
        return {"dates": 0, "duals": 0}

    meta = load_school_meta()
    out_dir = os.path.join(OUT_ROOT, str(year))
    os.makedirs(out_dir, exist_ok=True)

    grouped = by_date(duals)
    index_dates = []

    # Running record per (school, gender), advanced as the season is written out
    # in date order. A scoreboard that says "Jesuit (12-3)" is showing the record
    # as it stood after that match, not the team's final one — quoting the final
    # record next to an April result would be wrong by every game played since.
    tally = defaultdict(lambda: [0, 0, 0])

    def record_str(school_id, gender):
        w, l, t = tally[(school_id, gender)]
        return f"{w}-{l}" + (f"-{t}" if t else "")

    for date, days in sorted(grouped.items()):
        # Advance every team on this date before writing, so both sides of a
        # dual show the record including that dual — the way a box score does.
        for d in days:
            g = d["gender"]
            if d["tied"]:
                tally[(d["winner"]["id"], g)][2] += 1
                tally[(d["loser"]["id"], g)][2] += 1
            else:
                tally[(d["winner"]["id"], g)][0] += 1
                tally[(d["loser"]["id"], g)][1] += 1

        records = []
        for d in days:
            # The feed does not record who hosted, so the two sides are simply
            # "a" and "b" — the winner first. Nothing here invents a home team.
            a_id, b_id = d["winner"]["id"], d["loser"]["id"]
            a_meta = meta.get(a_id, {})
            b_meta = meta.get(b_id, {})
            records.append({
                "id": d["meet_id"],
                "gender": d["gender"],
                "postseason": d["postseason"],
                "source": d["source"],
                "contested": d["contested"],
                "level": d["level"],
                "winnerId": d["winner_id"],
                "tied": d["tied"],
                "scoreline": d["scoreline"],
                "tiebreak": (
                    {"basis": d["tiebreak"][0], "a": d["tiebreak"][1], "b": d["tiebreak"][2]}
                    if d["tiebreak"] else None),
                "a": {"id": a_id, "name": d["winner"]["name"], "score": d["winner"]["score"],
                      "classification": a_meta.get("classification", ""),
                      "league": a_meta.get("league", ""),
                      "record": record_str(a_id, d["gender"])},
                "b": {"id": b_id, "name": d["loser"]["name"], "score": d["loser"]["score"],
                      "classification": b_meta.get("classification", ""),
                      "league": b_meta.get("league", ""),
                      "record": record_str(b_id, d["gender"])},
                # Both sides in the same league is a conference match, which is
                # the one piece of context a reader wants that the names do not
                # already carry.
                "conference": bool(a_meta.get("league")
                                   and a_meta.get("league") == b_meta.get("league")),
                "flights": box_score(d["meet"], a_id, b_id),
            })

        records.sort(key=lambda r: (r["gender"], str(r["a"]["name"])))
        with open(os.path.join(out_dir, f"{date}.json"), "w", encoding="utf-8") as f:
            json.dump({"date": date, "duals": records}, f, separators=(",", ":"))

        counts = Counter(r["gender"] for r in records)
        index_dates.append({
            "date": date,
            "duals": len(records),
            "boys": counts.get("Boys", 0),
            "girls": counts.get("Girls", 0),
            "entered": sum(1 for r in records if r["source"] == "entered"),
        })

    index_dates.sort(key=lambda d: d["date"], reverse=True)

    teams = {}
    for d in duals:
        for side in ("winner", "loser"):
            sid = d[side]["id"]
            if sid not in teams:
                m = meta.get(sid, {})
                teams[sid] = {
                    "id": sid, "name": d[side]["name"],
                    "classification": m.get("classification", ""),
                    "league": m.get("league", ""),
                }

    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump({
            "year": year,
            "dates": index_dates,
            "teams": sorted(teams.values(), key=lambda t: str(t["name"])),
        }, f, separators=(",", ":"))

    entered = sum(d["entered"] for d in index_dates)
    print(f"scoreboard {year}: {len(duals)} duals across {len(index_dates)} dates "
          f"({entered} coach-reported), {len(teams)} teams")
    return {"dates": len(index_dates), "duals": len(duals)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--year", type=int, action="append", required=True,
                    help="season to build; repeat for several")
    args = ap.parse_args(argv)
    for year in args.year:
        build_year(year)
    return 0


if __name__ == "__main__":
    sys.exit(main())
