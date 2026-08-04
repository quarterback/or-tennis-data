#!/usr/bin/env python3
"""Export coach-entered duals from Postgres into a TR-shaped bundle.

The only script in this repository that talks to the reporting database.
Everything downstream — `merge_entered_data.py`, `generate_site.py`,
`build_lineup_data.py` — works from the bundle this writes, so the rest of the
pipeline stays a pure function of files on disk.

    python export_entered_meets.py --year 2027
    -> entered/2027/entered_meets.json

Reads DATABASE_URL (a read-only role is sufficient and preferred in CI). Exits 0
with an empty bundle when the variable is unset, so a build without database
access still produces a site from the scrape alone.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from collections import defaultdict

from entered_shape import compile_meet

ROOT = os.path.dirname(os.path.abspath(__file__))
BUNDLE_DIR = os.path.join(ROOT, "entered")
MASTER_CSV = os.path.join(ROOT, "master_school_list.csv")

# A dual reaches the site once the home coach files it. Away-team confirmation
# raises confidence, it does not gate publication — waiting on a coach who never
# signs in would silently drop the other team's season. A contested dual is
# published too, flagged: freezing disputes out of the maths would reward
# disputing anything you lost.
EXPORTED_STATUSES = ("reported", "confirmed", "contested")


def load_school_names() -> dict[int, str]:
    import csv
    names = {}
    if not os.path.exists(MASTER_CSV):
        return names
    with open(MASTER_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                names[int(row["id"])] = (row.get("name") or "").strip()
            except (KeyError, ValueError):
                continue
    return names


def fetch_duals(conn, year: int) -> list[dict]:
    """Assemble normalized dual dicts (see entered_shape's module docstring)."""
    names = load_school_names()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, gender_id, is_jv, played_on, home_school_id, away_school_id,
                   is_postseason, event_name, status
              FROM dual
             WHERE year = %s AND status = ANY(%s)
             ORDER BY played_on, id
            """,
            (year, list(EXPORTED_STATUSES)),
        )
        duals = {}
        order = []
        for (did, gender_id, is_jv, played_on, home_id, away_id,
             postseason, event_name, status) in cur.fetchall():
            duals[did] = {
                "dual_id": did,
                "year": year,
                "gender_id": gender_id,
                "is_jv": is_jv,
                "played_on": played_on.isoformat(),
                "is_postseason": postseason,
                "event_name": event_name,
                "status": status,
                "home": {"school_id": home_id, "name": names.get(home_id, "")},
                "away": {"school_id": away_id, "name": names.get(away_id, "")},
                "lines": [],
            }
            order.append(did)

        if not duals:
            return []

        dual_ids = list(duals)

        cur.execute(
            """
            SELECT id, dual_id, match_type, flight, home_won, finish
              FROM dual_line
             WHERE dual_id = ANY(%s)
             ORDER BY dual_id, match_type, flight
            """,
            (dual_ids,),
        )
        lines = {}
        for lid, did, match_type, flight, home_won, finish in cur.fetchall():
            line = {
                "line_id": lid, "match_type": match_type, "flight": flight,
                "home_won": home_won, "finish": finish,
                "home_players": [], "away_players": [], "sets": [],
            }
            lines[lid] = line
            duals[did]["lines"].append(line)

        if not lines:
            return [duals[d] for d in order if duals[d]["lines"]]

        line_ids = list(lines)

        cur.execute(
            """
            SELECT lp.dual_line_id, lp.side, lp.position,
                   rp.id, rp.tr_player_id, rp.first_name, rp.last_name, rp.grade
              FROM line_player lp
              JOIN roster_player rp ON rp.id = lp.roster_player_id
             WHERE lp.dual_line_id = ANY(%s)
             ORDER BY lp.dual_line_id, lp.side, lp.position
            """,
            (line_ids,),
        )
        for lid, side, _pos, pid, tr_pid, first, last, grade in cur.fetchall():
            lines[lid][f"{side}_players"].append({
                # Prefer the TennisReporting id when the coach has linked this
                # player to one. That is what keeps an entered 2027 season joined
                # to the same player's scraped 2026 season for the ladder and
                # all-state, instead of creating a second person.
                "id": tr_pid if tr_pid else pid,
                "first_name": first, "last_name": last, "grade": grade,
            })

        cur.execute(
            """
            SELECT dual_line_id, set_number, home_games, away_games, tie_points
              FROM line_set
             WHERE dual_line_id = ANY(%s)
             ORDER BY dual_line_id, set_number
            """,
            (line_ids,),
        )
        for lid, number, home_games, away_games, tie in cur.fetchall():
            lines[lid]["sets"].append({
                "number": number, "home": home_games,
                "away": away_games, "tie": tie,
            })

    return [duals[d] for d in order if duals[d]["lines"]]


def write_bundle(year: int, meets: list[dict], out_dir: str | None = None) -> str:
    out_dir = out_dir or os.path.join(BUNDLE_DIR, str(year))
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entered_meets.json")
    bundle = {
        "year": year,
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "count": len(meets),
        "meets": meets,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2)
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--out", help="output directory (default entered/<year>)")
    args = ap.parse_args(argv)

    url = os.environ.get("DATABASE_URL_RO") or os.environ.get("DATABASE_URL")
    if not url:
        print("No DATABASE_URL set — writing an empty bundle. "
              "The site will build from the scrape alone.")
        path = write_bundle(args.year, [], args.out)
        print(f"Wrote {path}")
        return 0

    try:
        import psycopg
    except ImportError:
        print("psycopg is not installed (pip install 'psycopg[binary]')", file=sys.stderr)
        return 1

    with psycopg.connect(url) as conn:
        duals = fetch_duals(conn, args.year)

    meets = [compile_meet(d) for d in duals]
    path = write_bundle(args.year, meets, args.out)

    by_status = defaultdict(int)
    for m in meets:
        by_status[m.get("status")] += 1
    summary = ", ".join(f"{v} {k}" for k, v in sorted(by_status.items())) or "none"
    print(f"Wrote {path}: {len(meets)} duals ({summary})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
