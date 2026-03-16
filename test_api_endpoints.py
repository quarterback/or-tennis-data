#!/usr/bin/env python3
"""
Test different TennisReporting API endpoints and parameters to find S4/D4 data.
"""

import requests
import json
from typing import Any

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://www.tennisreporting.com/",
    "Origin": "https://www.tennisreporting.com",
}

def test_endpoint(url: str, params: dict = None, description: str = "") -> Any:
    """Test an API endpoint and return the response."""
    print(f"\n{'='*80}")
    print(f"Testing: {description}")
    print(f"URL: {url}")
    print(f"Params: {params}")
    print('-'*80)

    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=30)
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            # Check for flight 4 data
            json_str = json.dumps(data)
            has_flight_4 = '"flight":"4"' in json_str or '"flight":4' in json_str

            # Count meets and matches
            meets = data.get('meets', [])
            total_matches = 0
            for meet in meets:
                matches = meet.get('matches', {})
                total_matches += len(matches.get('Singles', []))
                total_matches += len(matches.get('Doubles', []))

            print(f"✓ Success!")
            print(f"  - Meets: {len(meets)}")
            print(f"  - Total matches: {total_matches}")
            print(f"  - Has Flight 4: {'YES' if has_flight_4 else 'NO'}")

            return data
        else:
            print(f"✗ Failed: {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            return None

    except Exception as e:
        print(f"✗ Error: {e}")
        return None


def main():
    # Test school: Catlin Gabel
    school_id = 124895
    year = 2025
    gender_id = 2  # Female

    print("="*80)
    print("TESTING TENNISREPORTING API ENDPOINTS FOR S4/D4 DATA")
    print("="*80)
    print(f"School ID: {school_id} (Catlin Gabel)")
    print(f"Year: {year}")
    print(f"Gender: Female")

    # Test 1: Current endpoint
    test_endpoint(
        f"https://api.v2.tennisreporting.com/report/school/{school_id}",
        {"year": year, "genderId": gender_id, "isNotVarsity": 0},
        "Current endpoint (baseline)"
    )

    # Test 2: Try with additional parameters
    test_endpoint(
        f"https://api.v2.tennisreporting.com/report/school/{school_id}",
        {"year": year, "genderId": gender_id, "isNotVarsity": 0, "allFlights": True},
        "Current endpoint + allFlights parameter"
    )

    test_endpoint(
        f"https://api.v2.tennisreporting.com/report/school/{school_id}",
        {"year": year, "genderId": gender_id, "isNotVarsity": 0, "detailed": True},
        "Current endpoint + detailed parameter"
    )

    test_endpoint(
        f"https://api.v2.tennisreporting.com/report/school/{school_id}",
        {"year": year, "genderId": gender_id, "isNotVarsity": 0, "full": True},
        "Current endpoint + full parameter"
    )

    # Test 3: Try different API versions
    test_endpoint(
        f"https://api.v3.tennisreporting.com/report/school/{school_id}",
        {"year": year, "genderId": gender_id, "isNotVarsity": 0},
        "v3 API (if exists)"
    )

    test_endpoint(
        f"https://api.tennisreporting.com/report/school/{school_id}",
        {"year": year, "genderId": gender_id, "isNotVarsity": 0},
        "API without version (if exists)"
    )

    # Test 4: Try different endpoint structures
    test_endpoint(
        f"https://api.v2.tennisreporting.com/school/{school_id}/matches",
        {"year": year, "genderId": gender_id},
        "Alternative endpoint: /school/{id}/matches"
    )

    test_endpoint(
        f"https://api.v2.tennisreporting.com/matches",
        {"schoolId": school_id, "year": year, "genderId": gender_id},
        "Alternative endpoint: /matches with schoolId param"
    )

    test_endpoint(
        f"https://api.v2.tennisreporting.com/report/matches/{school_id}",
        {"year": year, "genderId": gender_id},
        "Alternative endpoint: /report/matches/{id}"
    )

    print("\n" + "="*80)
    print("TESTING COMPLETE")
    print("="*80)
    print("\nIf none of these show Flight 4 data, the API may not provide it.")
    print("Next step: Inspect browser network traffic on tennisreporting.com")


if __name__ == "__main__":
    main()
