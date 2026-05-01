#!/usr/bin/env python3
"""
Identify seed candidates for a special district tournament.

Eligibility (singles, mirrored for doubles):
  - Played at least one match at 1S, OR
  - Played at 2S AND is undefeated overall, OR
  - Played at 2S AND beat at least one player who has played 1S

Run:
    python3 scripts/seed_candidates.py --year 2026 --district "Special District 1" --gender 2
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MASTER_CSV = REPO / "master_school_list.csv"
DATA_DIR = REPO / "data"


def load_district_schools(district: str) -> dict[str, dict]:
    schools = {}
    with open(MASTER_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["League"].strip() == district:
                schools[row["id"]] = row
    return schools


def player_key(player: dict) -> tuple:
    return (player["id"], player["firstName"], player["lastName"], player["schoolId"])


def doubles_team_key(players: list[dict]) -> tuple:
    return tuple(sorted(p["id"] for p in players))


def doubles_team_label(players: list[dict], school_lookup: dict) -> str:
    names = sorted(f"{p['firstName']} {p['lastName']}" for p in players)
    school_id = str(players[0]["schoolId"]) if players else ""
    school = school_lookup.get(school_id, {}).get("name", f"school {school_id}")
    return f"{' / '.join(names)} ({school})"


@dataclass
class PlayerStats:
    name: str
    school: str
    school_id: str
    flights_played: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    flights_won: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    wins_over: list[tuple] = field(default_factory=list)   # (opponent_key, opponent_label, flight)
    losses_to: list[tuple] = field(default_factory=list)
    matches: int = 0
    wins: int = 0


@dataclass
class TeamStats:
    label: str
    school: str
    school_id: str
    flights_played: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    flights_won: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    wins_over: list[tuple] = field(default_factory=list)
    losses_to: list[tuple] = field(default_factory=list)
    matches: int = 0
    wins: int = 0


def collect_match_data(year: int, gender: int, district_school_ids: set[str]):
    """Walk every match in the year, dedupe by match id, and return raw matches.

    Includes any match touched by a district school (so SD1 vs non-SD1 matches
    still count toward an SD1 player's record/quality of wins)."""
    seen_match_ids: set[int] = set()
    singles: list[dict] = []
    doubles: list[dict] = []

    year_dir = DATA_DIR / str(year)
    if not year_dir.exists():
        raise SystemExit(f"No data directory for year {year}: {year_dir}")

    for school_id in district_school_ids:
        path = year_dir / f"school_{school_id}_gender_{gender}.json"
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for meet in data.get("meets", []):
            matches = meet.get("matches") or {}
            for kind, bucket in (("Singles", singles), ("Doubles", doubles)):
                for m in matches.get(kind, []) or []:
                    if m.get("isNotVarsity"):
                        continue
                    if m.get("id") in seen_match_ids:
                        continue
                    if m.get("winnerTeamId") is None:
                        continue
                    seen_match_ids.add(m["id"])
                    bucket.append(m)
    return singles, doubles


def process_singles(matches: list[dict], school_lookup: dict, district_school_ids: set[str]):
    players: dict[tuple, PlayerStats] = {}
    flight_to_played: dict[tuple, set[str]] = defaultdict(set)

    for m in matches:
        flight = str(m.get("flight"))
        teams = m.get("matchTeams", [])
        if len(teams) != 2:
            continue
        winner_team_id = m.get("winnerTeamId")

        team_players = []
        for t in teams:
            if not t.get("players"):
                team_players.append(None)
                continue
            p = t["players"][0]
            team_players.append((t["id"], p))

        if any(tp is None for tp in team_players):
            continue

        for idx, (team_id, p) in enumerate(team_players):
            key = player_key(p)
            stats = players.get(key)
            if stats is None:
                school_id = str(p["schoolId"])
                stats = PlayerStats(
                    name=f"{p['firstName']} {p['lastName']}",
                    school=school_lookup.get(school_id, {}).get("name", f"school {school_id}"),
                    school_id=school_id,
                )
                players[key] = stats
            stats.flights_played[flight] += 1
            stats.matches += 1
            flight_to_played[key].add(flight)
            won = team_id == winner_team_id
            if won:
                stats.flights_won[flight] += 1
                stats.wins += 1
                opp_team_id, opp_p = team_players[1 - idx]
                opp_key = player_key(opp_p)
                opp_school = school_lookup.get(str(opp_p["schoolId"]), {}).get("name", "")
                opp_label = f"{opp_p['firstName']} {opp_p['lastName']} ({opp_school})"
                stats.wins_over.append((opp_key, opp_label, flight))
            else:
                opp_team_id, opp_p = team_players[1 - idx]
                opp_key = player_key(opp_p)
                opp_school = school_lookup.get(str(opp_p["schoolId"]), {}).get("name", "")
                opp_label = f"{opp_p['firstName']} {opp_p['lastName']} ({opp_school})"
                stats.losses_to.append((opp_key, opp_label, flight))

    has_played_1s = {k for k, fs in flight_to_played.items() if "1" in fs}
    return players, has_played_1s


def process_doubles(matches: list[dict], school_lookup: dict, district_school_ids: set[str]):
    teams: dict[tuple, TeamStats] = {}
    flight_to_played: dict[tuple, set[str]] = defaultdict(set)

    for m in matches:
        flight = str(m.get("flight"))
        match_teams = m.get("matchTeams", [])
        if len(match_teams) != 2:
            continue
        winner_team_id = m.get("winnerTeamId")

        side_keys: list[tuple] = []
        side_labels: list[str] = []
        for t in match_teams:
            if not t.get("players") or len(t["players"]) < 2:
                side_keys.append(None)
                side_labels.append(None)
                continue
            tk = doubles_team_key(t["players"])
            side_keys.append(tk)
            side_labels.append(doubles_team_label(t["players"], school_lookup))

        if any(s is None for s in side_keys):
            continue

        for idx, t in enumerate(match_teams):
            tk = side_keys[idx]
            stats = teams.get(tk)
            if stats is None:
                school_id = str(t["players"][0]["schoolId"])
                stats = TeamStats(
                    label=side_labels[idx],
                    school=school_lookup.get(school_id, {}).get("name", f"school {school_id}"),
                    school_id=school_id,
                )
                teams[tk] = stats
            stats.flights_played[flight] += 1
            stats.matches += 1
            flight_to_played[tk].add(flight)
            won = t["id"] == winner_team_id
            opp_idx = 1 - idx
            opp_label = side_labels[opp_idx]
            opp_key = side_keys[opp_idx]
            if won:
                stats.flights_won[flight] += 1
                stats.wins += 1
                stats.wins_over.append((opp_key, opp_label, flight))
            else:
                stats.losses_to.append((opp_key, opp_label, flight))

    has_played_1d = {k for k, fs in flight_to_played.items() if "1" in fs}
    return teams, has_played_1d


def render_h2h_matrix(entities: list, label_fn, get_h2h_results) -> str:
    """Render an N x N head-to-head matrix among given entities."""
    if not entities:
        return ""
    short_labels = [label_fn(e, i) for i, e in enumerate(entities)]
    width = max(len(s) for s in short_labels) + 1

    out = []
    out.append("")
    out.append("Head-to-head among Tier A candidates (rows = player, cols = opponent):")
    out.append("  Cell shows W-L (only matches within this group are counted).")
    out.append("")
    header = " " * (width + 4) + "  ".join(f"{i+1:>3}" for i in range(len(entities)))
    out.append(header)
    for i, e in enumerate(entities):
        row = f"  {i+1:>2}. {short_labels[i]:<{width}}"
        for j, other in enumerate(entities):
            if i == j:
                cell = "  - "
            else:
                w, l = get_h2h_results(e, other)
                if w == 0 and l == 0:
                    cell = "  . "
                else:
                    cell = f"{w}-{l:<2}"
            row += f"{cell:>5}"
        out.append(row)
    return "\n".join(out)


def render_singles(players: dict, has_played_1s: set, district_school_ids: set[str]) -> str:
    out = []
    in_district = {k: v for k, v in players.items() if v.school_id in district_school_ids}

    primary_1s = []
    primary_2s_undefeated = []
    primary_2s_quality_win = []
    other_2s = []

    for key, p in in_district.items():
        played_1s = key in has_played_1s
        played_2s = "2" in p.flights_played
        is_undefeated = p.wins == p.matches and p.matches > 0
        beat_1s_player = any(opp_key in has_played_1s for opp_key, *_ in p.wins_over)

        s1_played = p.flights_played.get("1", 0)
        s2_played = p.flights_played.get("2", 0)
        s1_won = p.flights_won.get("1", 0)
        s2_won = p.flights_won.get("2", 0)
        record_str = f"{p.wins}-{p.matches - p.wins}"
        flight_str = f"1S {s1_won}-{s1_played - s1_won}, 2S {s2_won}-{s2_played - s2_won}"

        row = {
            "player": p.name,
            "school": p.school,
            "record": record_str,
            "flight_breakdown": flight_str,
            "wins_over_1s_players": [
                lbl for opp_key, lbl, fl in p.wins_over if opp_key in has_played_1s
            ],
            "losses_to_1s_players": [
                lbl for opp_key, lbl, fl in p.losses_to if opp_key in has_played_1s
            ],
        }

        if played_1s:
            primary_1s.append((p, row))
        elif played_2s and is_undefeated:
            primary_2s_undefeated.append((p, row))
        elif played_2s and beat_1s_player:
            primary_2s_quality_win.append((p, row))
        elif played_2s:
            other_2s.append((p, row))

    def _sort_key(item):
        p, row = item
        wp = p.wins / p.matches if p.matches else 0
        s1_played = p.flights_played.get("1", 0)
        s1_won = p.flights_won.get("1", 0)
        s1_wp = s1_won / s1_played if s1_played else 0
        return (-s1_played, -s1_wp, -wp, -p.matches)

    primary_1s.sort(key=_sort_key)
    primary_2s_undefeated.sort(key=lambda i: (-i[0].matches, -i[0].wins))
    primary_2s_quality_win.sort(key=lambda i: (-len(i[1]["wins_over_1s_players"]), -i[0].wins))

    out.append("=" * 100)
    out.append("SINGLES SEED CANDIDATES")
    out.append("=" * 100)
    out.append("")
    out.append(f"-- Tier A: Played 1S ({len(primary_1s)} players) --")
    for p, row in primary_1s:
        out.append(f"  {row['player']:30s}  {row['school']:30s}  overall {row['record']:6s}  ({row['flight_breakdown']})")
        for w in row["wins_over_1s_players"][:6]:
            out.append(f"      W vs {w}")
        for l in row["losses_to_1s_players"][:6]:
            out.append(f"      L to {l}")
    out.append("")
    out.append(f"-- Tier B: Primary 2S, undefeated ({len(primary_2s_undefeated)}) --")
    for p, row in primary_2s_undefeated:
        out.append(f"  {row['player']:30s}  {row['school']:30s}  overall {row['record']:6s}  ({row['flight_breakdown']})")
    out.append("")
    out.append(f"-- Tier C: Primary 2S with a win over a 1S-caliber player ({len(primary_2s_quality_win)}) --")
    for p, row in primary_2s_quality_win:
        out.append(f"  {row['player']:30s}  {row['school']:30s}  overall {row['record']:6s}  ({row['flight_breakdown']})")
        for w in row["wins_over_1s_players"]:
            out.append(f"      W vs {w}")
    out.append("")
    out.append(f"(Reference) {len(other_2s)} other 2S players in district who don't meet the criteria.")

    # H2H matrix among tier A candidates (cap at 12 for readability)
    tier_a_keys = []
    tier_a_objs = []
    key_to_player = {}
    for k, v in players.items():
        key_to_player[k] = v
    for p, _ in primary_1s[:12]:
        for k, vv in players.items():
            if vv is p:
                tier_a_keys.append(k)
                tier_a_objs.append(p)
                break

    def label_fn(p, i):
        return f"{p.name} ({p.school[:18]})"

    def h2h(p_self, p_opp):
        # Find self's wins/losses vs opp by matching opponent player ids
        # We don't have direct keys on PlayerStats, so use opponent label match isn't reliable;
        # we recorded opp_key in wins_over/losses_to so use that.
        # Find p_opp's key:
        opp_key = next((kk for kk, vv in players.items() if vv is p_opp), None)
        if opp_key is None:
            return 0, 0
        w = sum(1 for k, _, _ in p_self.wins_over if k == opp_key)
        l = sum(1 for k, _, _ in p_self.losses_to if k == opp_key)
        return w, l

    out.append(render_h2h_matrix(tier_a_objs, label_fn, h2h))
    return "\n".join(out)


def render_doubles(teams: dict, has_played_1d: set, district_school_ids: set[str]) -> str:
    out = []
    in_district = {k: v for k, v in teams.items() if v.school_id in district_school_ids}

    primary_1d = []
    primary_2d_undefeated = []
    primary_2d_quality_win = []
    other_2d = []

    for key, t in in_district.items():
        played_1d = key in has_played_1d
        played_2d = "2" in t.flights_played
        is_undefeated = t.wins == t.matches and t.matches > 0
        beat_1d_team = any(opp_key in has_played_1d for opp_key, *_ in t.wins_over)

        d1_played = t.flights_played.get("1", 0)
        d2_played = t.flights_played.get("2", 0)
        d1_won = t.flights_won.get("1", 0)
        d2_won = t.flights_won.get("2", 0)
        record_str = f"{t.wins}-{t.matches - t.wins}"
        flight_str = f"1D {d1_won}-{d1_played - d1_won}, 2D {d2_won}-{d2_played - d2_won}"

        row = {
            "team": t.label,
            "record": record_str,
            "flight_breakdown": flight_str,
            "wins_over_1d_teams": [
                lbl for opp_key, lbl, fl in t.wins_over if opp_key in has_played_1d
            ],
            "losses_to_1d_teams": [
                lbl for opp_key, lbl, fl in t.losses_to if opp_key in has_played_1d
            ],
        }

        if played_1d:
            primary_1d.append((t, row))
        elif played_2d and is_undefeated:
            primary_2d_undefeated.append((t, row))
        elif played_2d and beat_1d_team:
            primary_2d_quality_win.append((t, row))
        elif played_2d:
            other_2d.append((t, row))

    def _sort_key(item):
        t, row = item
        wp = t.wins / t.matches if t.matches else 0
        d1_played = t.flights_played.get("1", 0)
        d1_won = t.flights_won.get("1", 0)
        d1_wp = d1_won / d1_played if d1_played else 0
        return (-d1_played, -d1_wp, -wp, -t.matches)

    primary_1d.sort(key=_sort_key)
    primary_2d_undefeated.sort(key=lambda i: (-i[0].matches, -i[0].wins))
    primary_2d_quality_win.sort(key=lambda i: (-len(i[1]["wins_over_1d_teams"]), -i[0].wins))

    out.append("=" * 100)
    out.append("DOUBLES SEED CANDIDATES")
    out.append("=" * 100)
    out.append("")
    out.append(f"-- Tier A: Played 1D ({len(primary_1d)} teams) --")
    for t, row in primary_1d:
        out.append(f"  {row['team']:60s}  overall {row['record']:6s}  ({row['flight_breakdown']})")
        for w in row["wins_over_1d_teams"][:6]:
            out.append(f"      W vs {w}")
        for l in row["losses_to_1d_teams"][:6]:
            out.append(f"      L to {l}")
    out.append("")
    out.append(f"-- Tier B: Primary 2D, undefeated ({len(primary_2d_undefeated)}) --")
    for t, row in primary_2d_undefeated:
        out.append(f"  {row['team']:60s}  overall {row['record']:6s}  ({row['flight_breakdown']})")
    out.append("")
    out.append(f"-- Tier C: Primary 2D with a win over a 1D-caliber team ({len(primary_2d_quality_win)}) --")
    for t, row in primary_2d_quality_win:
        out.append(f"  {row['team']:60s}  overall {row['record']:6s}  ({row['flight_breakdown']})")
        for w in row["wins_over_1d_teams"]:
            out.append(f"      W vs {w}")
    out.append("")
    out.append(f"(Reference) {len(other_2d)} other 2D teams in district who don't meet the criteria.")

    # H2H matrix among tier A doubles teams (cap at 12)
    tier_a_objs = [t for t, _ in primary_1d[:12]]

    def label_fn(t, i):
        return f"{t.label[:60]}"

    def h2h(t_self, t_opp):
        opp_key = next((kk for kk, vv in teams.items() if vv is t_opp), None)
        if opp_key is None:
            return 0, 0
        w = sum(1 for k, _, _ in t_self.wins_over if k == opp_key)
        l = sum(1 for k, _, _ in t_self.losses_to if k == opp_key)
        return w, l

    out.append(render_h2h_matrix(tier_a_objs, label_fn, h2h))
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--district", default="Special District 1")
    parser.add_argument("--gender", type=int, choices=[1, 2], default=2,
                        help="1 = boys, 2 = girls")
    args = parser.parse_args()

    district_schools = load_district_schools(args.district)
    if not district_schools:
        raise SystemExit(f"No schools found in '{args.district}'")
    district_school_ids = set(district_schools.keys())
    school_lookup = district_schools

    # Also pull non-district school names for opponent labels
    with open(MASTER_CSV, newline="", encoding="utf-8") as f:
        all_schools = {row["id"]: row for row in csv.DictReader(f)}

    singles, doubles = collect_match_data(args.year, args.gender, district_school_ids)

    # Use full lookup for labels
    players, has_played_1s = process_singles(singles, all_schools, district_school_ids)
    teams, has_played_1d = process_doubles(doubles, all_schools, district_school_ids)

    gender_label = {1: "Boys", 2: "Girls"}[args.gender]
    print(f"\n### {args.district} — {gender_label} {args.year} — Seed Candidate Analysis ###")
    print(f"Schools in district: {', '.join(sorted(s['name'] for s in district_schools.values()))}")
    print(f"Total singles matches considered: {len(singles)}")
    print(f"Total doubles matches considered: {len(doubles)}")
    print()

    print(render_singles(players, has_played_1s, district_school_ids))
    print()
    print(render_doubles(teams, has_played_1d, district_school_ids))


if __name__ == "__main__":
    main()
