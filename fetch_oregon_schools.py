#!/usr/bin/env python3
"""
Fetch all Oregon schools from the TennisReporting API.

This script queries the API for each letter a-z, collects all schools
with state='OR', and saves them to oregon_schools.csv.

Note: The search endpoint may require authentication. If you get 401 errors,
you may need to provide an API key or authentication token.
"""

import csv
import time
import string
import requests

API_BASE_URL = "https://api.v2.tennisreporting.com/search/school"
OUTPUT_FILE = "oregon_schools.csv"


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.tennisreporting.com/",
    "Origin": "https://www.tennisreporting.com",
}


def fetch_schools_for_letter(letter: str) -> list[dict]:
    """Fetch schools matching a given letter from the API."""
    url = f"{API_BASE_URL}?term={letter}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print(f"Auth required for '{letter}'")
        elif e.response.status_code == 404:
            print(f"Not found for '{letter}'")
        else:
            print(f"HTTP error for '{letter}': {e}")
        return []
    except requests.RequestException as e:
        print(f"Error fetching schools for letter '{letter}': {e}")
        return []


def filter_oregon_schools(schools: list[dict]) -> list[dict]:
    """Filter schools to only include those in Oregon (state='OR')."""
    oregon_schools = []
    for school in schools:
        # Handle both flat structure and nested structure
        state = school.get("state")
        if isinstance(state, dict):
            state = state.get("abbr") or state.get("name")
        if state == "OR" or state == "Oregon":
            oregon_schools.append(school)
    return oregon_schools


def extract_school_info(school: dict) -> dict:
    """Extract id, name, and city from school data (handles nested structures)."""
    school_id = school.get("id")
    name = school.get("name", "")

    # Handle nested city structure
    city = school.get("city", "")
    if isinstance(city, dict):
        city = city.get("name", "")

    return {
        "id": school_id,
        "name": name,
        "city": city,
    }


def main():
    """Main function to fetch all Oregon schools and save to CSV."""
    oregon_schools = {}  # Use dict to deduplicate by ID

    print("Fetching Oregon schools from TennisReporting API...")
    print(f"URL: {API_BASE_URL}")
    print("-" * 50)

    for letter in string.ascii_lowercase:
        print(f"Searching for schools starting with '{letter}'...", end=" ")

        schools = fetch_schools_for_letter(letter)
        or_schools = filter_oregon_schools(schools)

        # Add to dict (deduplicates by ID)
        for school in or_schools:
            school_info = extract_school_info(school)
            school_id = school_info["id"]
            if school_id and school_id not in oregon_schools:
                oregon_schools[school_id] = school_info

        print(f"Found {len(or_schools)} OR schools (total unique: {len(oregon_schools)})")

        # Add delay between requests to avoid rate limiting
        time.sleep(1)

    print("-" * 50)
    print(f"Total unique Oregon schools found: {len(oregon_schools)}")

    # Write to CSV
    if oregon_schools:
        with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["id", "name", "city"])
            writer.writeheader()
            # Sort by name for easier reading
            sorted_schools = sorted(oregon_schools.values(), key=lambda x: x["name"])
            writer.writerows(sorted_schools)

        print(f"Saved {len(oregon_schools)} schools to {OUTPUT_FILE}")
    else:
        print("No Oregon schools found.")
        print("Note: The API may require authentication. Check the endpoint and headers.")


if __name__ == "__main__":
    main()
