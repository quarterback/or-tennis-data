"""SD1 girls tennis seeding report (top 8 singles, top 8 doubles).

Aggregates 2026 girls dual-match results between Special District 1 schools.
Singles: counts wins/losses by flight (1 vs 2). Doubles: counts wins/losses
by flight per partner pairing. Players with 1st-flight matches are highlighted
for top-8 seeding consideration; 2nd-flight only candidates are listed
separately so coaches can elevate stellar 2nd-flight cases.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict

SD1_SCHOOLS = {
    124983: "Blanchet",
    124895: "Catlin Gabel",
    74906: "Corbett",
    124884: "OES",
    75619: "Riverdale",
    7070618: "Riverside",
    75720: "Scappoose",
    75818: "St Helens",
    75860: "Tillamook",
    7070593: "Trinity Academy",
    124656: "Valley Catholic",
    124802: "Westside Christian",
}

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "2026")


def load_sd1_meets():
    seen = set()
    meets = []
    for sid in SD1_SCHOOLS:
        path = os.path.join(DATA_DIR, f"school_{sid}_gender_2.json")
        if not os.path.exists(path):
            continue
        with open(path) as f:
            d = json.load(f)
        for m in d.get("meets", []) or []:
            schools = (m.get("schools") or {})
            ids = [s["id"] for s in (schools.get("winners") or []) + (schools.get("losers") or [])]
            if len(ids) != 2 or not all(i in SD1_SCHOOLS for i in ids):
                continue
            if m["id"] in seen:
                continue
            seen.add(m["id"])
            meets.append(m)
    return meets


def player_key(p):
    return (p["id"], f"{p['firstName']} {p['lastName']}", p.get("schoolId"), p.get("grade"))


def aggregate(meets):
    # singles[player_id] = {'name','school','grade','flights':{flight: {'w':n,'l':n}}, 'opponents':[(date, opp_name, opp_school, flight, result)]}
    singles = defaultdict(lambda: {
        "name": None, "school": None, "grade": None,
        "flights": defaultdict(lambda: {"w": 0, "l": 0}),
        "log": [],
    })
    # doubles by team-pair (frozenset of 2 player ids on same school):
    doubles = defaultdict(lambda: {
        "players": None, "school": None,
        "flights": defaultdict(lambda: {"w": 0, "l": 0}),
        "log": [],
    })

    for meet in meets:
        date = meet.get("meetDateTime", "")[:10]
        for m in (meet.get("matches") or {}).get("Singles", []) or []:
            if m.get("isNotVarsity"):
                continue
            flight = str(m.get("flight"))
            teams = m.get("matchTeams") or []
            if len(teams) != 2:
                continue
            for t in teams:
                players = t.get("players") or []
                if len(players) != 1:
                    continue
                p = players[0]
                pid = p["id"]
                singles[pid]["name"] = f"{p['firstName']} {p['lastName']}"
                singles[pid]["school"] = SD1_SCHOOLS.get(p.get("schoolId"), p.get("school", {}).get("name"))
                singles[pid]["grade"] = p.get("grade")
                won = t.get("isWinner")
                # find opponent
                other = [tt for tt in teams if tt is not t][0]
                opp_players = other.get("players") or []
                opp = opp_players[0] if opp_players else {}
                opp_name = f"{opp.get('firstName','?')} {opp.get('lastName','?')}"
                opp_school = SD1_SCHOOLS.get(opp.get("schoolId"), "?")
                if won is True:
                    singles[pid]["flights"][flight]["w"] += 1
                    singles[pid]["log"].append((date, "W", flight, opp_name, opp_school))
                elif won is False:
                    singles[pid]["flights"][flight]["l"] += 1
                    singles[pid]["log"].append((date, "L", flight, opp_name, opp_school))

        for m in (meet.get("matches") or {}).get("Doubles", []) or []:
            if m.get("isNotVarsity"):
                continue
            flight = str(m.get("flight"))
            teams = m.get("matchTeams") or []
            if len(teams) != 2:
                continue
            for t in teams:
                players = t.get("players") or []
                if len(players) != 2:
                    continue
                pids = tuple(sorted([p["id"] for p in players]))
                key = pids
                names = [f"{p['firstName']} {p['lastName']}" for p in sorted(players, key=lambda x: x["id"])]
                school_id = players[0].get("schoolId")
                doubles[key]["players"] = names
                doubles[key]["school"] = SD1_SCHOOLS.get(school_id, "?")
                won = t.get("isWinner")
                other = [tt for tt in teams if tt is not t][0]
                opp_players = other.get("players") or []
                opp_names = " / ".join(f"{p.get('firstName','?')} {p.get('lastName','?')}" for p in opp_players)
                opp_school = SD1_SCHOOLS.get(opp_players[0].get("schoolId") if opp_players else None, "?")
                if won is True:
                    doubles[key]["flights"][flight]["w"] += 1
                    doubles[key]["log"].append((date, "W", flight, opp_names, opp_school))
                elif won is False:
                    doubles[key]["flights"][flight]["l"] += 1
                    doubles[key]["log"].append((date, "L", flight, opp_names, opp_school))

    return singles, doubles


def totals(flights):
    w = sum(f["w"] for f in flights.values())
    l = sum(f["l"] for f in flights.values())
    return w, l


def f1_record(flights):
    f = flights.get("1", {"w": 0, "l": 0})
    return f["w"], f["l"]


def f2_record(flights):
    f = flights.get("2", {"w": 0, "l": 0})
    return f["w"], f["l"]


def winpct(w, l):
    n = w + l
    return (w / n) if n else 0.0


def rank_singles(singles):
    """Tier 1 = anyone with >=1 flight-1 match. Tier 2 = flight-2 only.
    Within tier: sort by flight-1 win pct (then wins), then total win pct.
    """
    rows = []
    for pid, info in singles.items():
        w1, l1 = f1_record(info["flights"])
        w2, l2 = f2_record(info["flights"])
        tw, tl = totals(info["flights"])
        tier = 1 if (w1 + l1) > 0 else 2
        rows.append({
            "pid": pid,
            "name": info["name"],
            "school": info["school"],
            "grade": info["grade"],
            "f1_w": w1, "f1_l": l1,
            "f2_w": w2, "f2_l": l2,
            "tot_w": tw, "tot_l": tl,
            "tier": tier,
            "log": sorted(info["log"]),
        })

    def sort_key(r):
        # Primary: tier (F1 players first). Then F1 wins desc (volume of proven
        # play at the top spot), then F1 losses asc, then total record.
        totn = r["tot_w"] + r["tot_l"]
        totpct = r["tot_w"] / totn if totn else 0
        return (
            r["tier"],
            -r["f1_w"],
            r["f1_l"],
            -totpct,
            -r["tot_w"],
        )

    rows.sort(key=sort_key)
    return rows


def rank_doubles(doubles):
    rows = []
    for key, info in doubles.items():
        w1, l1 = f1_record(info["flights"])
        w2, l2 = f2_record(info["flights"])
        tw, tl = totals(info["flights"])
        # eligibility: need 2+ league matches with same partner
        total_matches = tw + tl
        tier = 1 if (w1 + l1) > 0 else 2
        rows.append({
            "key": key,
            "players": info["players"],
            "school": info["school"],
            "f1_w": w1, "f1_l": l1,
            "f2_w": w2, "f2_l": l2,
            "tot_w": tw, "tot_l": tl,
            "total_matches": total_matches,
            "eligible": total_matches >= 2,
            "tier": tier,
            "log": sorted(info["log"]),
        })

    def sort_key(r):
        totn = r["tot_w"] + r["tot_l"]
        totpct = r["tot_w"] / totn if totn else 0
        return (
            0 if r["eligible"] else 1,
            r["tier"],
            -r["f1_w"],
            r["f1_l"],
            -totpct,
            -r["tot_w"],
        )

    rows.sort(key=sort_key)
    return rows


def fmt_singles_row(r, idx):
    f1 = f"{r['f1_w']}-{r['f1_l']}"
    f2 = f"{r['f2_w']}-{r['f2_l']}"
    tot = f"{r['tot_w']}-{r['tot_l']}"
    return (f"{idx:>3}. {r['name']:<24s} ({r['school']:<18s} gr {r['grade']:<2s}) "
            f"flight-1: {f1:>5s}   flight-2: {f2:>5s}   total: {tot}")


def fmt_doubles_row(r, idx):
    pair = " / ".join(r["players"])
    f1 = f"{r['f1_w']}-{r['f1_l']}"
    f2 = f"{r['f2_w']}-{r['f2_l']}"
    tot = f"{r['tot_w']}-{r['tot_l']}"
    elig = "" if r["eligible"] else " [INELIGIBLE: <2 matches together]"
    return (f"{idx:>3}. {pair:<48s} ({r['school']:<18s}) "
            f"flight-1: {f1:>5s}   flight-2: {f2:>5s}   total: {tot}{elig}")


def main():
    meets = load_sd1_meets()
    singles, doubles = aggregate(meets)
    s_rank = rank_singles(singles)
    d_rank = rank_doubles(doubles)

    print("=" * 92)
    print("SPECIAL DISTRICT 1 (4A/3A/2A/1A GIRLS) — 2026 SEEDING INPUTS")
    print(f"Source: {len(meets)} dual matches between SD1 schools (league play only)")
    print("=" * 92)

    print()
    print("TOP 8 SINGLES — flight-1 players first, then flight-2 only candidates")
    print("-" * 92)
    tier1 = [r for r in s_rank if r["tier"] == 1]
    tier2 = [r for r in s_rank if r["tier"] == 2]
    for i, r in enumerate(tier1[:12], 1):
        print(fmt_singles_row(r, i))
    print()
    print("Flight-2-only candidates (only seed in top-8 if particularly stellar):")
    for i, r in enumerate(tier2[:8], 1):
        print(fmt_singles_row(r, i))

    print()
    print("TOP 8 DOUBLES — flight-1 teams first, then flight-2 only candidates")
    print("(Eligibility per SD1 rules: 2+ league matches with the same partner)")
    print("-" * 92)
    elig_t1 = [r for r in d_rank if r["eligible"] and r["tier"] == 1]
    elig_t2 = [r for r in d_rank if r["eligible"] and r["tier"] == 2]
    for i, r in enumerate(elig_t1[:12], 1):
        print(fmt_doubles_row(r, i))
    print()
    print("Flight-2-only doubles teams (only seed in top-8 if particularly stellar):")
    for i, r in enumerate(elig_t2[:8], 1):
        print(fmt_doubles_row(r, i))

    # Detail logs for the top candidates
    # Head-to-head matrix for top 8 flight-1 singles
    print()
    print("=" * 92)
    print("HEAD-TO-HEAD — TOP 8 FLIGHT-1 SINGLES (any flight, league only)")
    print("=" * 92)
    top8 = tier1[:8]
    top8_ids = [r["pid"] for r in top8]
    h2h = {pid: {opid: "" for opid in top8_ids if opid != pid} for pid in top8_ids}
    for r in top8:
        for d, res, fl, opp_name, opp_school in r["log"]:
            for other in top8:
                if other["pid"] == r["pid"]:
                    continue
                if other["name"] == opp_name:
                    cur = h2h[r["pid"]][other["pid"]]
                    h2h[r["pid"]][other["pid"]] = (cur + " " + f"{res}(F{fl})").strip()
    # Print labeled rows
    short = [(r["name"].split()[0] + " " + r["name"].split()[-1][0] + ".") for r in top8]
    label_w = 22
    col_w = 12
    header = " " * label_w + "".join(f"{s[:col_w-1]:<{col_w}}" for s in short)
    print(header)
    for i, r in enumerate(top8):
        row = f"{r['name'][:label_w-1]:<{label_w}}"
        for j, other in enumerate(top8):
            if i == j:
                row += f"{'—':<{col_w}}"
            else:
                cell = h2h[r["pid"]][other["pid"]] or "."
                row += f"{cell[:col_w-1]:<{col_w}}"
        print(row)

    print()
    print("=" * 92)
    print("MATCH LOGS — TOP 8 FLIGHT-1 SINGLES")
    print("=" * 92)
    for i, r in enumerate(tier1[:8], 1):
        print(f"\n#{i} {r['name']} ({r['school']}, gr {r['grade']})")
        for d, res, fl, opp, opp_sch in r["log"]:
            print(f"   {d}  F{fl}  {res}  vs {opp} ({opp_sch})")

    print()
    print("=" * 92)
    print("MATCH LOGS — TOP 8 FLIGHT-1 DOUBLES")
    print("=" * 92)
    for i, r in enumerate(elig_t1[:8], 1):
        pair = " / ".join(r["players"])
        print(f"\n#{i} {pair} ({r['school']})")
        for d, res, fl, opp, opp_sch in r["log"]:
            print(f"   {d}  F{fl}  {res}  vs {opp} ({opp_sch})")


if __name__ == "__main__":
    main()
