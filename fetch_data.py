#!/usr/bin/env python3
"""
Fetch dual match data for Oregon schools from the TennisReporting API.

This script reads school IDs from oregon_schools.csv and fetches
dual match data for each school with a 1-second delay between requests.
"""

import csv
import json
import time
import os
import argparse
from datetime import datetime
import requests

# Configuration
INPUT_FILE = "oregon_schools.csv"
OUTPUT_DIR = "match_data"
API_BASE_URL = "https://api.v2.tennisreporting.com/report/school"
REQUEST_DELAY = 1  # seconds between requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}


def load_school_ids(csv_file: str) -> list[dict]:
    """Load school IDs and names from the CSV file."""
    schools = []
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            schools.append({
                "id": row["id"],
                "name": row.get("name", ""),
                "city": row.get("city", ""),
            })
    return schools


def fetch_school_data(school_id: str, year: int, gender_id: int = 1, is_not_varsity: int = 0) -> dict | None:
    """
    Fetch dual match data for a school from the API.

    Args:
        school_id: The school's ID
        year: The year to fetch data for
        gender_id: 1 for boys, 2 for girls
        is_not_varsity: 0 for varsity, 1 for JV

    Returns:
        The JSON response data or None if request failed
    """
    url = f"{API_BASE_URL}/{school_id}"
    params = {
        "year": year,
        "genderId": gender_id,
        "isNotVarsity": is_not_varsity,
    }

    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"  HTTP error: {e.response.status_code}")
        return None
    except requests.RequestException as e:
        print(f"  Request error: {e}")
        return None


def save_school_data(school_id: str, data: dict, output_dir: str, year: int, gender_id: int):
    """Save school data to a JSON file."""
    os.makedirs(output_dir, exist_ok=True)
    filename = f"school_{school_id}_year_{year}_gender_{gender_id}.json"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return filepath


def main():
    """Main function to fetch dual match data for all Oregon schools."""
    parser = argparse.ArgumentParser(description="Fetch dual match data for Oregon schools")
    parser.add_argument("--year", type=int, default=2025, help="Year to fetch data for (default: 2025)")
    parser.add_argument("--gender", type=int, default=1, choices=[1, 2], help="Gender ID: 1=boys, 2=girls (default: 1)")
    parser.add_argument("--jv", action="store_true", help="Fetch JV instead of varsity")
    parser.add_argument("--input", type=str, default=INPUT_FILE, help="Input CSV file")
    parser.add_argument("--output", type=str, default=OUTPUT_DIR, help="Output directory")
    args = parser.parse_args()

    is_not_varsity = 1 if args.jv else 0
    gender_label = "boys" if args.gender == 1 else "girls"
    level_label = "JV" if args.jv else "varsity"

    # Load school IDs
    print(f"Loading schools from {args.input}...")
    try:
        schools = load_school_ids(args.input)
    except FileNotFoundError:
        print(f"Error: {args.input} not found. Run fetch_oregon_schools.py first.")
        return
    except KeyError as e:
        print(f"Error: CSV missing required column: {e}")
        return

    print(f"Found {len(schools)} schools")
    print(f"Fetching {args.year} {level_label} {gender_label} dual match data...")
    print("-" * 60)

    successful = 0
    failed = 0

    for i, school in enumerate(schools, 1):
        school_id = school["id"]
        school_name = school.get("name", f"School {school_id}")

        print(f"[{i}/{len(schools)}] Fetching {school_name} (ID: {school_id})...", end=" ")

        data = fetch_school_data(school_id, args.year, args.gender, is_not_varsity)

        if data:
            filepath = save_school_data(school_id, data, args.output, args.year, args.gender)
            print(f"OK -> {filepath}")
            successful += 1
        else:
            print("FAILED")
            failed += 1

        # Delay between requests (except for the last one)
        if i < len(schools):
            time.sleep(REQUEST_DELAY)

    print("-" * 60)
    print(f"Completed: {successful} successful, {failed} failed")
    print(f"Data saved to {args.output}/")


if __name__ == "__main__":
    main()
