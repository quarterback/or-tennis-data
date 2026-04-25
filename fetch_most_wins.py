#!/usr/bin/env python3
"""
Fetch the Most Wins list for Oregon from TennisReporting and update
oregon_schools.csv with any newly discovered active schools.

API endpoint:
  https://api.v2.tennisreporting.com/report/most_wins
  ?genderId=1&isTeam=true&stateId=46&year=2026

Run before fetch_data.py so that new schools are included in the
daily data pull.
"""

import argparse
import csv
import os
import time
from datetime import datetime

import requests

# Try the current host first; api.v2.tennisreporting.com was retired around
# 2026-04-24 but is left in the list as a fallback in case it returns. If both
# hosts come back 4xx for every path, this script logs a warning and exits 0
# so the workflow proceeds with the existing oregon_schools.csv.
API_HOSTS = [
    "https://api.tennisreporting.com",
    "https://api.v2.tennisreporting.com",
]
# Candidate endpoint paths in priority order; the first one that returns
# a non-empty list wins.
MOST_WINS_PATHS = [
    "/report/most_wins",
    "/report/most-wins",
    "/most_wins",
]
OUTPUT_FILE = "oregon_schools.csv"
OREGON_STATE_ID = 46
REQUEST_DELAY = 1  # seconds between requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.tennisreporting.com/",
    "Origin": "https://www.tennisreporting.com",
}


def fetch_most_wins(gender_id: int, year: int, state_id: int = OREGON_STATE_ID) -> list[dict]:
    """
    Query the most-wins endpoint for a given gender and year.

    Returns a list of school records (dicts) or an empty list on failure.
    """
    params = {
        "genderId": gender_id,
        "isTeam": "true",
        "stateId": state_id,
        "year": year,
    }

    for host in API_HOSTS:
        for path in MOST_WINS_PATHS:
            url = f"{host}{path}"
            try:
                response = requests.get(url, headers=HEADERS, params=params, timeout=30)
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                data = response.json()
                if isinstance(data, list) and data:
                    print(f"  Endpoint {host}{path} returned {len(data)} records")
                    return data
            except requests.exceptions.HTTPError:
                continue
            except requests.RequestException as e:
                print(f"  Request error for {host}{path}: {e}")
                continue

    print(f"  Warning: no working endpoint found for genderId={gender_id}")
    return []


def extract_school_info(record: dict) -> dict | None:
    """
    Extract id/name/city/state from a most-wins API record.

    The API may use different key names across versions; this handles
    the common variants defensively.
    """
    school_id = (
        record.get("id")
        or record.get("schoolId")
        or record.get("school_id")
    )
    name = (
        record.get("name")
        or record.get("schoolName")
        or record.get("school_name")
        or ""
    ).strip()

    if not school_id or not name:
        return None

    # city may be a nested object or a plain string
    city_raw = record.get("city") or record.get("cityName") or ""
    if isinstance(city_raw, dict):
        city = city_raw.get("name", "")
    else:
        city = str(city_raw)

    return {
        "id": str(school_id),
        "name": name,
        "city": city,
        "state": "OR",
    }


def load_schools(csv_file: str) -> dict[str, dict]:
    """Load existing schools from CSV, keyed by string ID."""
    schools: dict[str, dict] = {}
    if not os.path.exists(csv_file):
        return schools
    with open(csv_file, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            schools[str(row["id"])] = row
    return schools


def save_schools(schools: dict[str, dict], csv_file: str) -> None:
    """Write all schools back to CSV, sorted by name."""
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "name", "city", "state"])
        writer.writeheader()
        for school in sorted(schools.values(), key=lambda x: x["name"]):
            writer.writerow(school)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch Most Wins to discover active Oregon schools"
    )
    parser.add_argument(
        "--year",
        type=int,
        default=datetime.now().year,
        help="Season year (default: current year)",
    )
    parser.add_argument(
        "--output",
        default=OUTPUT_FILE,
        help=f"School list CSV to update (default: {OUTPUT_FILE})",
    )
    args = parser.parse_args()

    existing = load_schools(args.output)
    new_count = 0

    for gender_id, label in [(1, "boys"), (2, "girls")]:
        print(f"Fetching {args.year} {label} most wins for Oregon...")
        records = fetch_most_wins(gender_id, args.year)

        for record in records:
            info = extract_school_info(record)
            if info is None:
                continue
            if info["id"] not in existing:
                existing[info["id"]] = info
                print(f"  + New school: {info['name']} (ID: {info['id']})")
                new_count += 1

        time.sleep(REQUEST_DELAY)

    if new_count > 0:
        save_schools(existing, args.output)
        print(f"\nAdded {new_count} new school(s) to {args.output}")
    else:
        print("\nNo new schools discovered.")


if __name__ == "__main__":
    main()
