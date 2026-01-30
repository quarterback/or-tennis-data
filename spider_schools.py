#!/usr/bin/env python3
"""
Spider script to discover Oregon schools by crawling match opponents.

Starting from a seed school, this script recursively fetches match data
and extracts opponent school IDs to build a complete list of schools
within a conference/region.
"""

import csv
import json
import time
import os
import argparse
from collections import deque
import requests

# Configuration
API_BASE_URL = "https://api.v2.tennisreporting.com/report/school"
OUTPUT_FILE = "oregon_schools.csv"
CACHE_DIR = "match_data"
REQUEST_DELAY = 1  # seconds between API requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

# Known seed schools (ID: Name)
SEED_SCHOOLS = {
    75585: "Redmond",        # 5A Intermountain
    7070586: "Caldera",      # 5A Intermountain
    74814: "Summit",         # 5A Intermountain
    75113: "Sam Barlow",     # 6A Mt Hood
}


def fetch_school_data(school_id: int, year: int, gender_id: int, use_cache: bool = True) -> dict | None:
    """
    Fetch school data from API or cache.

    Returns the JSON data or None if request failed.
    """
    # Check cache first
    cache_file = os.path.join(CACHE_DIR, f"school_{school_id}_year_{year}_gender_{gender_id}.json")

    if use_cache and os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)

    # Fetch from API
    url = f"{API_BASE_URL}/{school_id}"
    params = {
        "year": year,
        "genderId": gender_id,
        "isNotVarsity": 0,
    }

    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Cache the response
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        return data
    except requests.RequestException as e:
        print(f"    Error fetching school {school_id}: {e}")
        return None


def extract_schools_from_data(data: dict) -> dict[int, dict]:
    """
    Extract all schools (including opponents) from the match data.

    Returns a dict of {school_id: {name, city, state}} for all schools found.
    """
    schools = {}

    # Extract the main school info
    school_info = data.get("school", {})
    if school_info:
        school_id = school_info.get("id")
        if school_id:
            city_info = school_info.get("city", {})
            schools[school_id] = {
                "id": school_id,
                "name": school_info.get("name", "").strip(),
                "city": city_info.get("name", "") if isinstance(city_info, dict) else "",
                "state": city_info.get("state", {}).get("abbr", "") if isinstance(city_info, dict) else "",
            }

    # Extract opponents from meets
    meets = data.get("meets", [])
    for meet in meets:
        schools_data = meet.get("schools", {})

        # Get schools from winners and losers
        for school_list in [schools_data.get("winners", []), schools_data.get("losers", [])]:
            for school in school_list:
                school_id = school.get("id")
                if school_id and school_id not in schools:
                    schools[school_id] = {
                        "id": school_id,
                        "name": school.get("name", "").strip(),
                        "city": "",  # Not available from opponent data
                        "state": "",  # Will need to fetch full data to get this
                    }

    return schools


def spider_schools(seed_ids: list[int], year: int, gender_id: int,
                   max_depth: int = None, state_filter: str = "OR") -> dict[int, dict]:
    """
    Spider through schools starting from seed IDs.

    Args:
        seed_ids: List of school IDs to start from
        year: Year to fetch data for
        gender_id: 1 for boys, 2 for girls
        max_depth: Maximum crawl depth (None for unlimited)
        state_filter: Only include schools from this state (None for all)

    Returns:
        Dict of all discovered schools
    """
    discovered_schools = {}  # {school_id: {name, city, state}}
    visited = set()
    queue = deque([(sid, 0) for sid in seed_ids])  # (school_id, depth)

    print(f"Starting spider with {len(seed_ids)} seed school(s)...")
    print(f"Year: {year}, Gender: {'Boys' if gender_id == 1 else 'Girls'}")
    print("-" * 60)

    api_requests = 0

    while queue:
        school_id, depth = queue.popleft()

        if school_id in visited:
            continue

        if max_depth is not None and depth > max_depth:
            continue

        visited.add(school_id)

        # Show progress
        print(f"[Depth {depth}] Crawling school {school_id}...", end=" ")

        # Fetch school data
        data = fetch_school_data(school_id, year, gender_id)

        if data is None:
            print("FAILED")
            continue

        # Check if we needed to make an API request
        cache_file = os.path.join(CACHE_DIR, f"school_{school_id}_year_{year}_gender_{gender_id}.json")
        if not os.path.exists(cache_file):
            api_requests += 1
            time.sleep(REQUEST_DELAY)

        # Extract schools from the data
        schools = extract_schools_from_data(data)

        # Get the main school info
        main_school = schools.get(school_id, {})
        school_name = main_school.get("name", f"School {school_id}")
        school_state = main_school.get("state", "")

        # Filter by state if specified
        if state_filter and school_state and school_state != state_filter:
            print(f"{school_name} (SKIPPED - {school_state})")
            continue

        print(f"{school_name}")

        # Add discovered schools
        new_schools = 0
        for sid, info in schools.items():
            if sid not in discovered_schools:
                discovered_schools[sid] = info
                new_schools += 1

                # Add to queue for crawling
                if sid not in visited:
                    queue.append((sid, depth + 1))

        if new_schools > 0:
            print(f"    -> Found {new_schools} new school(s), {len(discovered_schools)} total")

    print("-" * 60)
    print(f"Spider complete!")
    print(f"  Schools visited: {len(visited)}")
    print(f"  Total schools discovered: {len(discovered_schools)}")
    print(f"  API requests made: {api_requests}")

    return discovered_schools


def enrich_school_data(schools: dict[int, dict], year: int, gender_id: int) -> dict[int, dict]:
    """
    Fetch full data for schools missing city/state info.
    """
    print("\nEnriching school data with city/state info...")

    to_enrich = [sid for sid, info in schools.items() if not info.get("city")]
    print(f"Schools needing enrichment: {len(to_enrich)}")

    for i, school_id in enumerate(to_enrich, 1):
        print(f"  [{i}/{len(to_enrich)}] Enriching {schools[school_id]['name']}...", end=" ")

        data = fetch_school_data(school_id, year, gender_id)
        if data:
            school_info = data.get("school", {})
            city_info = school_info.get("city", {})

            if isinstance(city_info, dict):
                schools[school_id]["city"] = city_info.get("name", "")
                state_info = city_info.get("state", {})
                schools[school_id]["state"] = state_info.get("abbr", "") if isinstance(state_info, dict) else ""

            print("OK")
        else:
            print("FAILED")

        time.sleep(REQUEST_DELAY)

    return schools


def save_schools_to_csv(schools: dict[int, dict], output_file: str, state_filter: str = None):
    """Save discovered schools to CSV, optionally filtering by state."""
    # Filter by state if specified
    if state_filter:
        schools = {sid: info for sid, info in schools.items()
                   if info.get("state") == state_filter or not info.get("state")}

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "name", "city", "state"])
        writer.writeheader()

        # Sort by name
        sorted_schools = sorted(schools.values(), key=lambda x: x.get("name", ""))
        for school in sorted_schools:
            writer.writerow({
                "id": school["id"],
                "name": school["name"],
                "city": school.get("city", ""),
                "state": school.get("state", ""),
            })

    print(f"\nSaved {len(schools)} schools to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Spider through TennisReporting to discover schools by crawling match opponents"
    )
    parser.add_argument("--seed", type=int, nargs="+",
                        help="Seed school ID(s) to start from (default: built-in seeds)")
    parser.add_argument("--year", type=int, default=2025,
                        help="Year to fetch data for (default: 2025)")
    parser.add_argument("--gender", type=int, default=1, choices=[1, 2],
                        help="Gender: 1=boys, 2=girls (default: 1)")
    parser.add_argument("--max-depth", type=int, default=None,
                        help="Maximum crawl depth (default: unlimited)")
    parser.add_argument("--no-enrich", action="store_true",
                        help="Skip enriching school data with city/state")
    parser.add_argument("--output", type=str, default=OUTPUT_FILE,
                        help="Output CSV file")
    parser.add_argument("--all-states", action="store_true",
                        help="Include schools from all states (default: Oregon only)")
    args = parser.parse_args()

    # Use provided seeds or defaults
    seed_ids = args.seed if args.seed else list(SEED_SCHOOLS.keys())
    state_filter = None if args.all_states else "OR"

    # Run the spider
    schools = spider_schools(
        seed_ids=seed_ids,
        year=args.year,
        gender_id=args.gender,
        max_depth=args.max_depth,
        state_filter=state_filter,
    )

    # Enrich school data with city/state info
    if not args.no_enrich:
        schools = enrich_school_data(schools, args.year, args.gender)

    # Save to CSV
    save_schools_to_csv(schools, args.output, state_filter=state_filter)

    # Print summary
    print("\n" + "=" * 60)
    print("DISCOVERED SCHOOLS")
    print("=" * 60)
    for school in sorted(schools.values(), key=lambda x: x.get("name", "")):
        city = school.get("city", "")
        city_str = f" ({city})" if city else ""
        print(f"  {school['id']:>8}: {school['name']}{city_str}")


if __name__ == "__main__":
    main()
