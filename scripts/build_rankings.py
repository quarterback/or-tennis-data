#!/usr/bin/env python3
"""
Build rankings from Oregon high school tennis dual match data.

Calculates:
- WWP (Weighted Win Percentage): Based on flight weights
- OWP (Opponent Win Percentage): Average WWP of opponents
- APR (Adjusted Power Rating): (WWP * 0.35) + (OWP * 0.65)
"""

import os
import json
import csv
from collections import defaultdict
from pathlib import Path

# Flight weights for ranking calculation
FLIGHT_WEIGHTS = {
    ('Singles', '1'): 1.0,
    ('Singles', '2'): 0.75,
    ('Singles', '3'): 0.25,
    ('Singles', '4'): 0.10,
    ('Doubles', '1'): 1.0,
    ('Doubles', '2'): 0.50,
    ('Doubles', '3'): 0.25,
    ('Doubles', '4'): 0.10,
}

# APR weights
WWP_WEIGHT = 0.35
OWP_WEIGHT = 0.65

# Gender mapping
GENDER_MAP = {1: 'Boys', 2: 'Girls'}


def load_master_school_list(filepath):
    """Load master school list with classification and league data."""
    schools = {}
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['id']:
                schools[int(row['id'])] = {
                    'name': row['name'],
                    'city': row['city'],
                    'state': row['state'],
                    'classification': row.get('Classification', ''),
                    'league': row.get('League', ''),
                }
    return schools


def is_dual_match(meet):
    """Check if a meet is a dual match (not a tournament or event)."""
    title = meet.get('title', '')

    # Exclude state championships and events
    if 'State Championship' in title:
        return False
    if 'Event' in title and '.' in title:
        return False
    if 'District' in title:
        return False
    if 'Tournament' in title:
        return False

    # Dual matches typically have exactly 2 schools (winner + loser)
    schools = meet.get('schools', {})
    winners = schools.get('winners', [])
    losers = schools.get('losers', [])

    # A dual match has 1 winner and 1 loser
    return len(winners) == 1 and len(losers) == 1


def get_flight_weight(match_type, flight):
    """Get the weight for a given match type and flight."""
    return FLIGHT_WEIGHTS.get((match_type, str(flight)), 0.10)


def extract_match_results(meet, school_id):
    """
    Extract individual match results from a meet.
    Returns list of (opponent_id, match_type, flight, is_win, weight) tuples.
    """
    results = []

    schools = meet.get('schools', {})
    winners = schools.get('winners', [])
    losers = schools.get('losers', [])

    # Find opponent school
    opponent_id = None
    school_is_winner = False

    for w in winners:
        if w['id'] == school_id:
            school_is_winner = True
        else:
            opponent_id = w['id']

    for l in losers:
        if l['id'] == school_id:
            school_is_winner = False
        else:
            opponent_id = l['id']

    if opponent_id is None:
        return results

    # Process individual matches
    matches = meet.get('matches', {})

    for match_type in ['Singles', 'Doubles']:
        type_matches = matches.get(match_type, [])
        if isinstance(type_matches, list):
            for match in type_matches:
                flight = match.get('flight', '1')
                weight = get_flight_weight(match_type, flight)

                # Determine if this school won this individual match
                match_teams = match.get('matchTeams', [])
                is_win = False
                played = False

                for team in match_teams:
                    players = team.get('players', [])
                    for player in players:
                        if player.get('schoolId') == school_id:
                            played = True
                            is_win = team.get('isWinner', False)
                            break
                    if played:
                        break

                if played:
                    results.append((opponent_id, match_type, flight, is_win, weight))

    return results


def process_school_data(data, school_id):
    """
    Process all meets for a school and extract match results.
    Only processes dual matches.
    """
    all_results = []
    opponents = set()

    for meet in data.get('meets', []):
        if is_dual_match(meet):
            results = extract_match_results(meet, school_id)
            all_results.extend(results)
            for r in results:
                opponents.add(r[0])  # opponent_id

    return all_results, opponents


def calculate_wwp(results):
    """Calculate Weighted Win Percentage from match results."""
    if not results:
        return 0.0

    weighted_wins = sum(r[4] for r in results if r[3])  # weight if is_win
    weighted_total = sum(r[4] for r in results)  # total weights

    if weighted_total == 0:
        return 0.0

    return weighted_wins / weighted_total


def build_rankings(data_dir, master_school_list):
    """
    Build rankings for all schools across all years and genders.
    """
    # Load master school list
    school_info = load_master_school_list(master_school_list)

    # First pass: Calculate WWP for all schools
    # Structure: {year: {gender: {school_id: {'wwp': float, 'opponents': set, 'results': list}}}}
    school_data = defaultdict(lambda: defaultdict(dict))

    data_path = Path(data_dir)

    for year_dir in sorted(data_path.iterdir()):
        if not year_dir.is_dir():
            continue

        year = year_dir.name
        if not year.isdigit():
            continue

        # Only process 2022-2025
        if int(year) < 2022 or int(year) > 2025:
            continue

        print(f"Processing year {year}...")

        for json_file in year_dir.glob('school_*_gender_*.json'):
            # Parse filename: school_74814_gender_1.json
            parts = json_file.stem.split('_')
            school_id = int(parts[1])
            gender_id = int(parts[3])
            gender = GENDER_MAP.get(gender_id, 'Unknown')

            with open(json_file, 'r') as f:
                data = json.load(f)

            results, opponents = process_school_data(data, school_id)

            if results:  # Only include schools with actual match data
                wwp = calculate_wwp(results)
                school_data[year][gender][school_id] = {
                    'wwp': wwp,
                    'opponents': opponents,
                    'results': results,
                    'matches_played': len(results),
                    'weighted_wins': sum(r[4] for r in results if r[3]),
                    'weighted_total': sum(r[4] for r in results),
                }

    # Second pass: Calculate OWP (average WWP of opponents)
    for year in school_data:
        for gender in school_data[year]:
            for school_id in school_data[year][gender]:
                school = school_data[year][gender][school_id]
                opponents = school['opponents']

                opponent_wwps = []
                for opp_id in opponents:
                    if opp_id in school_data[year][gender]:
                        opponent_wwps.append(school_data[year][gender][opp_id]['wwp'])

                if opponent_wwps:
                    owp = sum(opponent_wwps) / len(opponent_wwps)
                else:
                    owp = 0.0

                school['owp'] = owp

                # Calculate APR
                school['apr'] = (school['wwp'] * WWP_WEIGHT) + (owp * OWP_WEIGHT)

    # Build output with school info joined
    output = []

    for year in sorted(school_data.keys()):
        for gender in sorted(school_data[year].keys()):
            # Sort by APR descending
            ranked = sorted(
                school_data[year][gender].items(),
                key=lambda x: x[1]['apr'],
                reverse=True
            )

            for rank, (school_id, stats) in enumerate(ranked, 1):
                info = school_info.get(school_id, {})

                output.append({
                    'year': int(year),
                    'gender': gender,
                    'rank': rank,
                    'school_id': school_id,
                    'school_name': info.get('name', f'School {school_id}'),
                    'city': info.get('city', ''),
                    'classification': info.get('classification', ''),
                    'league': info.get('league', ''),
                    'wwp': round(stats['wwp'], 4),
                    'owp': round(stats['owp'], 4),
                    'apr': round(stats['apr'], 4),
                    'matches_played': stats['matches_played'],
                    'opponents_count': len(stats['opponents']),
                })

    return output


def main():
    # Paths relative to repo root
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    data_dir = repo_root / 'data'
    master_school_list = repo_root / 'master_school_list.csv'
    output_file = repo_root / 'public' / 'data' / 'processed_rankings.json'

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    print("Building rankings...")
    rankings = build_rankings(data_dir, master_school_list)

    # Save output
    with open(output_file, 'w') as f:
        json.dump(rankings, f, indent=2)

    print(f"\nRankings saved to {output_file}")
    print(f"Total entries: {len(rankings)}")

    # Summary stats
    from collections import Counter
    year_counts = Counter(r['year'] for r in rankings)
    gender_counts = Counter(r['gender'] for r in rankings)

    print("\nBy year:")
    for year, count in sorted(year_counts.items()):
        print(f"  {year}: {count} rankings")

    print("\nBy gender:")
    for gender, count in sorted(gender_counts.items()):
        print(f"  {gender}: {count} rankings")


if __name__ == '__main__':
    main()
