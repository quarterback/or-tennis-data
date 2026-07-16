#!/usr/bin/env python3
"""Build the derived data that powers the Lineups section (public/lineups.html).

For every team-season we already have scraped meet JSON in data/<year>/. Each
meet records, per court (flight), which players played and who won. From that we
derive two things the Lineups tools need:

  1. A per-player POSITION MATRIX — how many times each rostered player appeared
     at each flight (1S-4S singles, 1D-3D doubles) across the season. This is the
     anti-stacking audit: you can see at a glance whether a strong player was
     quietly dropped to a low court.

  2. A data-derived LADDER ("letter order") — players ordered by the strength of
     the court they usually played (a 1S regular sits above a 3S regular). Coaches
     verify this and submit a final locked ladder through the Netlify function;
     that submission lives in Netlify Blobs, NOT here.

Outputs (served statically, fetched by the page):
    public/data/lineups/index.json                      — team picker index
    public/data/lineups/<year>/<gender><school_id>.json — per-team detail

No coach-entered data is read or written here; this is purely a transform of the
scraped match data, regenerated whenever the data refresh runs.
"""
from __future__ import annotations

import csv
import glob
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
OUT_DIR = os.path.join(ROOT, "public", "data", "lineups")
MASTER_CSV = os.path.join(ROOT, "master_school_list.csv")

GENDER_NAME = {1: "Boys", 2: "Girls"}
SINGLES_FLIGHTS = ["S1", "S2", "S3", "S4"]
DOUBLES_FLIGHTS = ["D1", "D2", "D3"]
ALL_SLOTS = SINGLES_FLIGHTS + DOUBLES_FLIGHTS


def load_master():
    """school_id -> {name, classification, league}."""
    out = {}
    if not os.path.exists(MASTER_CSV):
        return out
    with open(MASTER_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                sid = int(row["id"])
            except (KeyError, ValueError):
                continue
            out[sid] = {
                "name": row.get("name", "").strip(),
                "classification": row.get("Classification", "").strip(),
                "league": row.get("League", "").strip(),
            }
    return out


def player_name(p):
    fn = (p.get("firstName") or "").strip()
    ln = (p.get("lastName") or "").strip()
    return (fn + " " + ln).strip() or "Unknown"


def slot_for(line):
    """Return e.g. 'S1' / 'D3' from a match line, or None if unrecognized."""
    mt = (line.get("matchType") or "").strip()
    try:
        flight = int(str(line.get("flight")).strip())
    except (TypeError, ValueError):
        return None
    if mt == "Singles" and 1 <= flight <= 4:
        return "S%d" % flight
    if mt == "Doubles" and 1 <= flight <= 3:
        return "D%d" % flight
    return None


def build_team(path, school_id, gender):
    """Aggregate one team-season file into a detail dict, or None if empty."""
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return None

    school = doc.get("school") or {}
    # players[pid] = {name, grade, slots{slot:count}, matches[...]}
    players = {}
    meet_count = 0

    for meet in doc.get("meets") or []:
        matches = meet.get("matches") or {}
        if not matches:
            continue
        post = bool(meet.get("postSeason"))
        date = (meet.get("meetDateTime") or "")[:10]
        title = (meet.get("title") or "").strip()
        touched = False

        for kind in ("Singles", "Doubles"):
            for line in matches.get(kind) or []:
                slot = slot_for(line)
                if not slot:
                    continue
                teams = line.get("matchTeams") or []
                # Identify which side is ours (players whose schoolId == this file).
                for t in teams:
                    tps = t.get("players") or []
                    ours = [p for p in tps if p.get("schoolId") == school_id]
                    if not ours:
                        continue
                    won = bool(t.get("isWinner"))
                    # opponent = the other side's player name(s)
                    opp_names = []
                    for ot in teams:
                        if ot is t:
                            continue
                        for op in ot.get("players") or []:
                            opp_names.append(player_name(op))
                    opp = " / ".join(opp_names) if opp_names else ""
                    for p in ours:
                        pid = str(p.get("id"))
                        rec = players.get(pid)
                        if rec is None:
                            rec = players[pid] = {
                                "name": player_name(p),
                                "grade": (p.get("grade") or "").strip(),
                                "slots": {s: 0 for s in ALL_SLOTS},
                                "matches": [],
                            }
                        rec["slots"][slot] += 1
                        rec["matches"].append(
                            {
                                "slot": slot,
                                "date": date,
                                "opp": opp,
                                "won": won,
                                "post": post,
                                "meet": title,
                            }
                        )
                        touched = True
        if touched:
            meet_count += 1

    if not players:
        return None

    # Derived ladder: order by strongest court usually played.
    # Weight is the average singles flight number (1 = best). Players with singles
    # appearances rank above doubles-only players; doubles-only sort by avg
    # doubles flight, and appear after the singles ladder.
    def ladder_key(item):
        pid, rec = item
        slots = rec["slots"]
        s_total = sum(slots[s] for s in SINGLES_FLIGHTS)
        d_total = sum(slots[s] for s in DOUBLES_FLIGHTS)
        if s_total:
            avg = sum(int(s[1]) * slots[s] for s in SINGLES_FLIGHTS) / s_total
            return (0, avg, -s_total)
        avg = sum(int(s[1]) * slots[s] for s in DOUBLES_FLIGHTS) / d_total if d_total else 9
        return (1, avg, -d_total)

    ordered = sorted(players.items(), key=ladder_key)
    for rank, (pid, rec) in enumerate(ordered, start=1):
        rec["derived_rank"] = rank
        # Primary position = the slot the player appeared at most (ties -> strongest).
        best = max(
            ALL_SLOTS,
            key=lambda s: (rec["slots"][s], -ALL_SLOTS.index(s)),
        )
        rec["primary"] = best if rec["slots"][best] else None
        rec["total"] = sum(rec["slots"].values())
        # Win/loss record per position and overall (courts don't tie: not-won = loss).
        rec_slots = {s: [0, 0] for s in ALL_SLOTS}
        for m in rec["matches"]:
            rec_slots[m["slot"]][0 if m["won"] else 1] += 1
        rec["rec_slots"] = {s: wl for s, wl in rec_slots.items() if wl[0] or wl[1]}
        rec["rec"] = [
            sum(wl[0] for wl in rec_slots.values()),
            sum(wl[1] for wl in rec_slots.values()),
        ]

    meta = load_master().get(
        school_id,
        {"name": school.get("name", ""), "classification": "", "league": ""},
    )
    name = meta["name"] or school.get("name", "") or "School %d" % school_id
    rec = doc.get("overallRecord") or {}

    return {
        "school_id": school_id,
        "gender": GENDER_NAME.get(gender, str(gender)),
        "name": name,
        "classification": meta["classification"],
        "league": meta["league"],
        "record": {
            "win": rec.get("win", 0),
            "loss": rec.get("loss", 0),
            "tie": rec.get("tie", 0),
        },
        "meets_counted": meet_count,
        # ordered list keeps ladder order stable for the client
        "ladder": [
            {
                "pid": pid,
                "name": r["name"],
                "grade": r["grade"],
                "primary": r["primary"],
                "total": r["total"],
                "slots": r["slots"],
                "rec": r["rec"],
                "rec_slots": r["rec_slots"],
                "derived_rank": r["derived_rank"],
                "matches": r["matches"],
            }
            for pid, r in ordered
        ],
    }


def main(years=None):
    master = load_master()  # noqa: F841 (loaded per team; warm the file check)
    if not os.path.isdir(DATA_DIR):
        print("no data/ dir at %s" % DATA_DIR, file=sys.stderr)
        return 1

    all_years = sorted(
        d for d in os.listdir(DATA_DIR) if d.isdigit() and os.path.isdir(os.path.join(DATA_DIR, d))
    )
    if years:
        all_years = [y for y in all_years if y in set(years)]

    os.makedirs(OUT_DIR, exist_ok=True)
    index = {"generated_years": all_years, "teams": {}}
    total_written = 0

    for year in all_years:
        year_dir = os.path.join(DATA_DIR, year)
        year_out = os.path.join(OUT_DIR, year)
        os.makedirs(year_out, exist_ok=True)
        entries = []
        for path in sorted(glob.glob(os.path.join(year_dir, "school_*_gender_*.json"))):
            base = os.path.basename(path)
            try:
                _, sid_s, _, gen_s = base.replace(".json", "").split("_")
                school_id = int(sid_s)
                gender = int(gen_s)
            except ValueError:
                continue
            detail = build_team(path, school_id, gender)
            if not detail:
                continue
            key = "%d%d" % (gender, school_id)  # e.g. 2124656 -> girls Valley Catholic
            with open(os.path.join(year_out, key + ".json"), "w", encoding="utf-8") as f:
                json.dump(detail, f, separators=(",", ":"))
            total_written += 1
            entries.append(
                {
                    "key": key,
                    "school_id": school_id,
                    "gender": detail["gender"],
                    "name": detail["name"],
                    "classification": detail["classification"],
                    "league": detail["league"],
                    "players": len(detail["ladder"]),
                    "meets": detail["meets_counted"],
                }
            )
        entries.sort(key=lambda e: (e["classification"], e["name"], e["gender"]))
        index["teams"][year] = entries
        print("  %s: %d teams" % (year, len(entries)))

    with open(os.path.join(OUT_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, separators=(",", ":"))
    print("lineup data: wrote %d team files across %d years" % (total_written, len(all_years)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or None))
