#!/usr/bin/env python3
"""Seed the reporting database from data already on disk.

A coach opening the reporting tool for the first time should find their team,
their name, and most of their returning roster already there. Typing a roster
from scratch in March is the point where a volunteer coach stops using a system,
so everything that can be derived from the scrape is derived:

  * `team_season` for every school in master_school_list.csv, both genders.
  * `coach` from the `coaches[]` block each scraped school file carries — real
    school-domain addresses, already scoped to school and gender. That doubles as
    the auth allowlist: mailing a sign-in link to the address TennisReporting has
    on file for a team is the claim check.
  * `team_claim` for those coaches, so the first sign-in already owns the team.
  * `roster_player` from last season's appearances, with `tr_player_id` set so an
    entered 2027 season stays joined to the same player's scraped 2026 season.

Idempotent — safe to re-run as rosters and staff change.

    python scripts/seed_reporting_db.py --year 2027 --from-season 2026
    python scripts/seed_reporting_db.py --year 2027 --dry-run
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

DATA_DIR = os.path.join(ROOT, "data")
MASTER_CSV = os.path.join(ROOT, "master_school_list.csv")

GENDERS = (1, 2)
GENDER_NAME = {1: "Boys", 2: "Girls"}

# Only carry a player forward if they are returning. A senior in the source
# season has graduated by the target season.
GRADUATING_GRADE = "12"


def load_master() -> list[dict]:
    rows = []
    with open(MASTER_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                rows.append({
                    "school_id": int(row["id"]),
                    "name": (row.get("name") or "").strip(),
                    "classification": (row.get("Classification") or "").strip(),
                    "league": (row.get("League") or "").strip(),
                })
            except (KeyError, ValueError):
                continue
    return rows


def _bump_grade(grade: str) -> str:
    try:
        return str(int(grade) + 1)
    except (TypeError, ValueError):
        return ""


def scan_season(season: int) -> tuple[dict, dict]:
    """Return (coaches, rosters) keyed by (school_id, gender_id).

    A player is attributed by the `schoolId` on their own player object, which is
    how build_lineup_data.py pulls a team's appearances out of both duals and
    multi-team events without any cross-file de-duplication.
    """
    coaches: dict[tuple[int, int], dict] = {}
    rosters: dict[tuple[int, int], dict[int, dict]] = {}

    for path in sorted(glob.glob(os.path.join(DATA_DIR, str(season), "school_*_gender_*.json"))):
        parts = os.path.splitext(os.path.basename(path))[0].split("_")
        try:
            school_id, gender_id = int(parts[1]), int(parts[3])
        except (IndexError, ValueError):
            continue
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)

        for c in doc.get("coaches") or []:
            email = (c.get("email") or "").strip().lower()
            if not email or "@" not in email:
                continue
            if c.get("genderId") not in (None, gender_id):
                continue
            coaches[(school_id, gender_id)] = {
                "email": email,
                "name": " ".join(x for x in [(c.get("firstName") or "").strip(),
                                             (c.get("lastName") or "").strip()] if x),
                "phone": (c.get("phone") or "").strip(),
            }

        team = rosters.setdefault((school_id, gender_id), {})
        for meet in doc.get("meets") or []:
            for match_type in ("Singles", "Doubles"):
                for line in (meet.get("matches") or {}).get(match_type, []) or []:
                    for mt in line.get("matchTeams") or []:
                        for p in mt.get("players") or []:
                            if p.get("schoolId") != school_id:
                                continue
                            pid = p.get("id")
                            if pid is None:
                                continue
                            team.setdefault(pid, {
                                "tr_player_id": pid,
                                "first_name": (p.get("firstName") or "").strip(),
                                "last_name": (p.get("lastName") or "").strip(),
                                "grade": str(p.get("grade") or "").strip(),
                            })
    return coaches, rosters


def seed(conn, year: int, source_season: int, carry_roster: bool, dry_run: bool) -> dict:
    master = load_master()
    coaches, rosters = scan_season(source_season)
    stats = {"teams": 0, "coaches": 0, "claims": 0, "players": 0, "skipped_seniors": 0}

    cur = conn.cursor()
    for school in master:
        for gender_id in GENDERS:
            key = (school["school_id"], gender_id)
            stats["teams"] += 1
            if dry_run:
                continue

            cur.execute(
                """
                INSERT INTO team_season (year, school_id, gender_id, is_jv, school_name,
                                         league, classification)
                VALUES (%s, %s, %s, FALSE, %s, %s, %s)
                ON CONFLICT (year, school_id, gender_id, is_jv) DO UPDATE
                   SET school_name = EXCLUDED.school_name,
                       league = EXCLUDED.league,
                       classification = EXCLUDED.classification
                RETURNING id
                """,
                (year, school["school_id"], gender_id, school["name"],
                 school["league"], school["classification"]),
            )
            team_season_id = cur.fetchone()[0]

            coach = coaches.get(key)
            if coach:
                cur.execute(
                    """
                    INSERT INTO coach (email, name, phone, seeded_from_scrape)
                    VALUES (%s, %s, %s, TRUE)
                    ON CONFLICT (lower(email)) DO UPDATE
                       SET name = coalesce(nullif(EXCLUDED.name, ''), coach.name)
                    RETURNING id, (xmax = 0) AS inserted
                    """,
                    (coach["email"], coach["name"], coach["phone"]),
                )
                coach_id, inserted = cur.fetchone()
                if inserted:
                    stats["coaches"] += 1
                cur.execute(
                    """
                    INSERT INTO team_claim (coach_id, team_season_id, role)
                    VALUES (%s, %s, 'head')
                    ON CONFLICT (coach_id, team_season_id) DO NOTHING
                    """,
                    (coach_id, team_season_id),
                )
                stats["claims"] += cur.rowcount

            if not carry_roster:
                continue

            for player in (rosters.get(key) or {}).values():
                if player["grade"] == GRADUATING_GRADE and year > source_season:
                    stats["skipped_seniors"] += 1
                    continue
                grade = _bump_grade(player["grade"]) if year > source_season else player["grade"]
                cur.execute(
                    """
                    INSERT INTO roster_player (team_season_id, first_name, last_name,
                                               grade, tr_player_id)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (team_season_id, lower(first_name), lower(last_name))
                    DO UPDATE SET tr_player_id =
                        coalesce(roster_player.tr_player_id, EXCLUDED.tr_player_id)
                    """,
                    (team_season_id, player["first_name"], player["last_name"],
                     grade, player["tr_player_id"]),
                )
                stats["players"] += 1

    if not dry_run:
        conn.commit()
    return stats


def ensure_schema(conn) -> bool:
    """Create the tables if they are not there yet.

    Applying db/schema.sql used to be a separate step needing psql on the
    command line, which is a real obstacle for someone who has never run a
    database before — and forgetting it produces a confusing "relation does not
    exist" rather than an obvious "you skipped a step". Every statement in the
    schema is CREATE … IF NOT EXISTS, so running it against an existing
    database changes nothing.

    Returns True if the schema was applied.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.team_season') IS NOT NULL")
        if cur.fetchone()[0]:
            return False

    schema = os.path.join(ROOT, "db", "schema.sql")
    if not os.path.exists(schema):
        raise SystemExit(f"tables are missing and {schema} is not there to create them")
    print(f"First run against this database — applying db/schema.sql…")
    with open(schema, encoding="utf-8") as fh:
        sql = fh.read()
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--year", type=int, required=True, help="season to seed")
    ap.add_argument("--from-season", type=int, help="season to read rosters and coaches from "
                                                    "(default: the year before --year)")
    ap.add_argument("--no-roster", action="store_true",
                    help="seed teams and coaches only")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    source = args.from_season or (args.year - 1)

    if args.dry_run:
        coaches, rosters = scan_season(source)
        master = load_master()
        players = sum(len(v) for v in rosters.values())
        print(f"Would seed {len(master) * len(GENDERS)} team-seasons for {args.year}")
        print(f"  {len(coaches)} coach emails and {players} players found in {source}")
        return 0

    url = os.environ.get("DATABASE_URL") or os.environ.get("NETLIFY_DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set.\n"
              "Copy the connection string from your database provider and:\n"
              "  export DATABASE_URL='postgresql://…'", file=sys.stderr)
        return 1
    try:
        import psycopg
    except ImportError:
        print("psycopg is not installed (pip install 'psycopg[binary]')", file=sys.stderr)
        return 1

    with psycopg.connect(url) as conn:
        ensure_schema(conn)
        stats = seed(conn, args.year, source, not args.no_roster, False)

    print(f"Seeded {args.year} from {source}: "
          f"{stats['teams']} team-seasons, {stats['coaches']} new coaches, "
          f"{stats['claims']} claims, {stats['players']} players "
          f"({stats['skipped_seniors']} graduating seniors skipped)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
