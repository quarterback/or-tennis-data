#!/usr/bin/env python3
"""
Generate a static HTML dashboard for Oregon high school tennis rankings.

Features:
- Modern high-density UI with Inter font
- Sortable/filterable tables with DataTables
- League column with filter support
- Tie detection (W-L-T format)
- Playoff Simulator with bracket sizes and auto-bids
- Tiebreaker logic: H2H, Common Opponents Win%, APR
"""

import os
import json
import csv
import time
from collections import defaultdict
from pathlib import Path
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

# Flight weights for ranking calculation
FLIGHT_WEIGHTS = {
    ('Singles', '1'): 1.00,
    ('Singles', '2'): 0.75,
    ('Singles', '3'): 0.25,
    ('Singles', '4'): 0.10,
    ('Doubles', '1'): 1.00,
    ('Doubles', '2'): 0.50,
    ('Doubles', '3'): 0.25,
    ('Doubles', '4'): 0.10,
}  # Total: 3.95

# Max possible FWS per match (sum of all flight weights)
MAX_FWS = sum(FLIGHT_WEIGHTS.values())  # 3.95

# Standard RPI formula weights (OSAA style)
# APR = (WP * 0.25) + (OWP * 0.50) + (OOWP * 0.25)
WP_WEIGHT = 0.25    # Team's own win percentage
OWP_WEIGHT = 0.50   # Opponent win percentage (strength of schedule)
OOWP_WEIGHT = 0.25  # Opponent's opponent win percentage

# Power Index formula weights (50/50 split: Results vs Depth)
APR_WEIGHT = 0.50   # Dual match outcomes (winning)
FWS_WEIGHT = 0.50   # Roster depth (flight performance)

# H2H Tiebreaker threshold - swap if PI difference is less than this
H2H_THRESHOLD = 0.02  # Teams within 2% PI difference eligible for H2H swap
H2H_LEAGUE_RANK_THRESHOLD = 2  # Teams within 2 league rank spots eligible for league-based H2H

GENDER_MAP = {1: 'Boys', 2: 'Girls'}

# Oregon city coordinates for distance calculations (lat, lng)
# Used for playoff bracket regionalization
OREGON_CITY_COORDS = {
    'albany': (44.6365, -123.1059),
    'arlington': (45.7226, -120.1990),
    'ashland': (42.1946, -122.7095),
    'astoria': (46.1879, -123.8313),
    'baker city': (44.7749, -117.8344),
    'bandon': (43.1190, -124.4084),
    'beaverton': (45.4871, -122.8037),
    'bend': (44.0582, -121.3153),
    'brookings': (42.0526, -124.2839),
    'burns': (43.5863, -119.0541),
    'canby': (45.2629, -122.6926),
    'coos bay': (43.3665, -124.2179),
    'corvallis': (44.5646, -123.2620),
    'cottage grove': (43.7973, -123.0595),
    'dallas': (44.9193, -123.3170),
    'enterprise': (45.4268, -117.2787),
    'eugene': (44.0521, -123.0868),
    'florence': (43.9826, -124.0999),
    'forest grove': (45.5198, -123.1107),
    'grants pass': (42.4390, -123.3284),
    'gresham': (45.4983, -122.4310),
    'hermiston': (45.8404, -119.2895),
    'hillsboro': (45.5229, -122.9898),
    'hood river': (45.7054, -121.5215),
    'junction city': (44.2193, -123.2054),
    'klamath falls': (42.2249, -121.7817),
    'la grande': (45.3246, -118.0877),
    'lake oswego': (45.4207, -122.6706),
    'lakeview': (42.1888, -120.3458),
    'lebanon': (44.5368, -122.9070),
    'lincoln city': (44.9582, -124.0178),
    'madras': (44.6332, -121.1295),
    'mcminnville': (45.2101, -123.1987),
    'medford': (42.3265, -122.8756),
    'milwaukie': (45.4462, -122.6393),
    'newberg': (45.3007, -122.9729),
    'newport': (44.6368, -124.0535),
    'north bend': (43.4065, -124.2243),
    'nyssa': (43.8776, -116.9938),
    'ontario': (44.0266, -116.9629),
    'oregon city': (45.3573, -122.6068),
    'pendleton': (45.6721, -118.7886),
    'phoenix': (42.2751, -122.8181),
    'pleasant hill': (43.9443, -122.9562),
    'portland': (45.5152, -122.6784),
    'prineville': (44.2999, -120.8345),
    'redmond': (44.2726, -121.1739),
    'reedsport': (43.7023, -124.0968),
    'roseburg': (43.2165, -123.3417),
    'salem': (44.9429, -123.0351),
    'sandy': (45.3973, -122.2612),
    'seaside': (45.9932, -123.9226),
    'silverton': (45.0054, -122.7831),
    'springfield': (44.0462, -123.0220),
    'st helens': (45.8640, -122.8065),
    'stayton': (44.8007, -122.7937),
    'sublimity': (44.8296, -122.7934),
    'sweet home': (44.3973, -122.7359),
    'the dalles': (45.5946, -121.1787),
    'tigard': (45.4312, -122.7715),
    'tillamook': (45.4562, -123.8426),
    'toledo': (44.6215, -123.9384),
    'tualatin': (45.3840, -122.7640),
    'turner': (44.8443, -122.9526),
    'west linn': (45.3657, -122.6120),
    'wilsonville': (45.2998, -122.7735),
    'woodburn': (45.1437, -122.8554),
}


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in miles between two points using Haversine formula."""
    from math import radians, sin, cos, sqrt, atan2
    R = 3959  # Earth's radius in miles

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c


# Geocoding cache file path
GEOCODE_CACHE_FILE = Path(__file__).parent / 'geocode_cache.json'

# Global geocoder instance (lazy initialized)
_geocoder = None
_geocode_cache = None

def _get_geocoder():
    """Get or create the geocoder instance."""
    global _geocoder
    if _geocoder is None:
        _geocoder = Nominatim(user_agent="or-tennis-rankings", timeout=10)
    return _geocoder

def _load_geocode_cache():
    """Load geocoding cache from file."""
    global _geocode_cache
    if _geocode_cache is None:
        if GEOCODE_CACHE_FILE.exists():
            try:
                with open(GEOCODE_CACHE_FILE, 'r') as f:
                    _geocode_cache = json.load(f)
            except (json.JSONDecodeError, IOError):
                _geocode_cache = {}
        else:
            _geocode_cache = {}
    return _geocode_cache

def _save_geocode_cache():
    """Save geocoding cache to file."""
    global _geocode_cache
    if _geocode_cache:
        with open(GEOCODE_CACHE_FILE, 'w') as f:
            json.dump(_geocode_cache, f, indent=2)

def geocode_city(city, state='Oregon'):
    """Geocode a city using OpenStreetMap Nominatim API with caching."""
    if not city:
        return None

    cache = _load_geocode_cache()
    cache_key = f"{city.lower().strip()}, {state}"

    # Check cache first
    if cache_key in cache:
        cached = cache[cache_key]
        if cached is None:
            return None
        return tuple(cached)

    # Try geocoding
    try:
        geocoder = _get_geocoder()
        location = geocoder.geocode(f"{city}, {state}, USA")
        if location:
            coords = (location.latitude, location.longitude)
            cache[cache_key] = list(coords)
            _save_geocode_cache()
            time.sleep(1)  # Rate limiting for Nominatim
            return coords
        else:
            cache[cache_key] = None
            _save_geocode_cache()
            return None
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"  Geocoding error for {city}: {e}")
        return None

def get_city_coords(city):
    """Get coordinates for a city, using cache then geocoding API."""
    if not city:
        return None
    city_lower = city.lower().strip()

    # Check hardcoded cache first (fast)
    if city_lower in OREGON_CITY_COORDS:
        return OREGON_CITY_COORDS[city_lower]

    # Try partial match in hardcoded cache
    for known_city, coords in OREGON_CITY_COORDS.items():
        if known_city in city_lower or city_lower in known_city:
            return coords

    # Fall back to geocoding API
    return geocode_city(city)


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
    if 'State Championship' in title:
        return False
    if 'Event' in title and '.' in title:
        return False
    if 'District' in title:
        return False
    if 'Tournament' in title:
        return False
    schools = meet.get('schools', {})
    winners = schools.get('winners', [])
    losers = schools.get('losers', [])
    return len(winners) == 1 and len(losers) == 1


def get_flight_weight(match_type, flight):
    """Get the weight for a given match type and flight."""
    return FLIGHT_WEIGHTS.get((match_type, str(flight)), 0.10)


def extract_match_results(meet, school_id):
    """Extract individual match results from a meet."""
    results = []
    schools = meet.get('schools', {})
    winners = schools.get('winners', [])
    losers = schools.get('losers', [])

    opponent_id = None
    for w in winners:
        if w['id'] != school_id:
            opponent_id = w['id']
    for l in losers:
        if l['id'] != school_id:
            opponent_id = l['id']

    if opponent_id is None:
        return results

    matches = meet.get('matches', {})
    for match_type in ['Singles', 'Doubles']:
        type_matches = matches.get(match_type, [])
        if isinstance(type_matches, list):
            for match in type_matches:
                flight = match.get('flight', '1')
                weight = get_flight_weight(match_type, flight)
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


def get_dual_match_record(meets, school_id):
    """Get the dual match win-loss-tie record for a school."""
    wins = 0
    losses = 0
    ties = 0

    for meet in meets:
        if not is_dual_match(meet):
            continue

        schools = meet.get('schools', {})
        winners = schools.get('winners', [])
        losers = schools.get('losers', [])

        school_score = None
        opponent_score = None

        for w in winners:
            if w['id'] == school_id:
                school_score = w.get('score', 0)
            else:
                opponent_score = w.get('score', 0)
        for l in losers:
            if l['id'] == school_id:
                school_score = l.get('score', 0)
            else:
                opponent_score = l.get('score', 0)

        if school_score is not None and opponent_score is not None:
            if school_score > opponent_score:
                wins += 1
            elif school_score < opponent_score:
                losses += 1
            else:
                ties += 1

    return wins, losses, ties


def get_league_record(meets, school_id, school_league, school_info):
    """Get the league-only win-loss-tie record."""
    wins = 0
    losses = 0
    ties = 0

    if not school_league:
        return wins, losses, ties

    for meet in meets:
        if not is_dual_match(meet):
            continue

        schools = meet.get('schools', {})
        winners = schools.get('winners', [])
        losers = schools.get('losers', [])

        opponent_id = None
        school_score = None
        opponent_score = None

        for w in winners:
            if w['id'] == school_id:
                school_score = w.get('score', 0)
            else:
                opponent_id = w['id']
                opponent_score = w.get('score', 0)
        for l in losers:
            if l['id'] == school_id:
                school_score = l.get('score', 0)
            else:
                opponent_id = l['id']
                opponent_score = l.get('score', 0)

        # Check if opponent is in same league
        if opponent_id and opponent_id in school_info:
            opponent_league = school_info[opponent_id].get('league', '')
            if opponent_league == school_league:
                if school_score is not None and opponent_score is not None:
                    if school_score > opponent_score:
                        wins += 1
                    elif school_score < opponent_score:
                        losses += 1
                    else:
                        ties += 1

    return wins, losses, ties


def get_head_to_head(school1_meets, school1_id, school2_id):
    """Get head-to-head record between two schools. Returns (wins, losses, ties)."""
    wins = 0
    losses = 0
    ties = 0

    for meet in school1_meets:
        if not is_dual_match(meet):
            continue

        schools = meet.get('schools', {})
        winners = schools.get('winners', [])
        losers = schools.get('losers', [])

        is_vs_school2 = False
        school1_score = None
        school2_score = None

        for w in winners:
            if w['id'] == school1_id:
                school1_score = w.get('score', 0)
            elif w['id'] == school2_id:
                school2_score = w.get('score', 0)
                is_vs_school2 = True
        for l in losers:
            if l['id'] == school1_id:
                school1_score = l.get('score', 0)
            elif l['id'] == school2_id:
                school2_score = l.get('score', 0)
                is_vs_school2 = True

        if is_vs_school2 and school1_score is not None and school2_score is not None:
            if school1_score > school2_score:
                wins += 1
            elif school1_score < school2_score:
                losses += 1
            else:
                ties += 1

    return wins, losses, ties


def get_head_to_head_detailed(school1_meets, school1_id, school2_id):
    """
    Get detailed head-to-head record between two schools.
    Returns dict with wins, losses, ties, and match details including dates and FWS.
    """
    results = {
        'wins': 0,
        'losses': 0,
        'ties': 0,
        'matches': []  # List of {date, score1, score2, result, fws1, fws2}
    }

    for meet in school1_meets:
        if not is_dual_match(meet):
            continue

        schools = meet.get('schools', {})
        winners = schools.get('winners', [])
        losers = schools.get('losers', [])

        is_vs_school2 = False
        school1_score = None
        school2_score = None

        for w in winners:
            if w['id'] == school1_id:
                school1_score = w.get('score', 0)
            elif w['id'] == school2_id:
                school2_score = w.get('score', 0)
                is_vs_school2 = True
        for l in losers:
            if l['id'] == school1_id:
                school1_score = l.get('score', 0)
            elif l['id'] == school2_id:
                school2_score = l.get('score', 0)
                is_vs_school2 = True

        if is_vs_school2 and school1_score is not None and school2_score is not None:
            # Get match date (try multiple possible field names)
            match_date = meet.get('meetDateTime', meet.get('startDate', meet.get('date', '')))
            if match_date and 'T' in match_date:
                match_date = match_date.split('T')[0]

            # Calculate FWS for each school in this match
            fws1 = 0.0
            fws2 = 0.0
            matches_data = meet.get('matches', {})
            for match_type in ['Singles', 'Doubles']:
                type_matches = matches_data.get(match_type, [])
                if isinstance(type_matches, list):
                    for match in type_matches:
                        flight = match.get('flight', '1')
                        weight = get_flight_weight(match_type, flight)
                        match_teams = match.get('matchTeams', [])
                        for team in match_teams:
                            if team.get('isWinner', False):
                                players = team.get('players', [])
                                for player in players:
                                    if player.get('schoolId') == school1_id:
                                        fws1 += weight
                                    elif player.get('schoolId') == school2_id:
                                        fws2 += weight
                                    break

            result = 'win' if school1_score > school2_score else ('loss' if school1_score < school2_score else 'tie')

            if result == 'win':
                results['wins'] += 1
            elif result == 'loss':
                results['losses'] += 1
            else:
                results['ties'] += 1

            results['matches'].append({
                'date': match_date,
                'score1': school1_score,
                'score2': school2_score,
                'result': result,
                'fws1': fws1,
                'fws2': fws2
            })

    return results


def process_school_data(data, school_id):
    """Process all meets for a school and extract match results."""
    all_results = []
    opponents = set()
    for meet in data.get('meets', []):
        if is_dual_match(meet):
            results = extract_match_results(meet, school_id)
            all_results.extend(results)
            for r in results:
                opponents.add(r[0])
    return all_results, opponents


def calculate_wwp(results):
    """Calculate Weighted Win Percentage from match results."""
    if not results:
        return 0.0
    weighted_wins = sum(r[4] for r in results if r[3])
    weighted_total = sum(r[4] for r in results)
    if weighted_total == 0:
        return 0.0
    return weighted_wins / weighted_total


def calculate_fws_per_match(data, school_id):
    """
    Calculate Flight Weighted Score (FWS) per dual match using Proportional Weighting.

    Instead of dividing by MAX_FWS (3.95) every time, we divide by the total
    potential weight of flights actually contested in each match. This handles
    forfeits and shorthanded matches fairly.

    Example:
    - Full match (8 flights): Denominator = 3.95
    - Short match (1S, 2S, 1D, 2D only): Denominator = 3.0 (1.0+0.75+1.0+0.5)

    Returns dict with:
    - normalized_fws: 0-1 range average
    - match_count: number of dual matches
    - fws_pct: percentage of flights won (simple ratio)
    - flight_breakdown: win rate per flight position
    - total_flights_won: raw count of flights won
    - total_flights_played: raw count of flights contested
    """
    dual_match_fws_scores = []

    # Track flight-by-flight stats
    flight_stats = {
        'S1': {'wins': 0, 'played': 0},
        'S2': {'wins': 0, 'played': 0},
        'S3': {'wins': 0, 'played': 0},
        'S4': {'wins': 0, 'played': 0},
        'D1': {'wins': 0, 'played': 0},
        'D2': {'wins': 0, 'played': 0},
        'D3': {'wins': 0, 'played': 0},
        'D4': {'wins': 0, 'played': 0},
    }

    total_flights_won = 0
    total_flights_played = 0

    for meet in data.get('meets', []):
        if not is_dual_match(meet):
            continue

        # Track points earned and available weight for this match
        points_earned = 0.0
        available_weight = 0.0
        matches = meet.get('matches', {})

        for match_type in ['Singles', 'Doubles']:
            type_matches = matches.get(match_type, [])
            if isinstance(type_matches, list):
                for match in type_matches:
                    flight = match.get('flight', '1')
                    weight = get_flight_weight(match_type, flight)
                    match_teams = match.get('matchTeams', [])

                    # Flight key for breakdown (S1, S2, D1, D2, etc.)
                    flight_key = f"{'S' if match_type == 'Singles' else 'D'}{flight}"

                    # Check if this flight was actually contested (has teams/result)
                    flight_contested = len(match_teams) >= 2

                    if flight_contested:
                        available_weight += weight
                        total_flights_played += 1
                        if flight_key in flight_stats:
                            flight_stats[flight_key]['played'] += 1

                        # Check if our school won this flight
                        for team in match_teams:
                            players = team.get('players', [])
                            for player in players:
                                if player.get('schoolId') == school_id:
                                    if team.get('isWinner', False):
                                        points_earned += weight
                                        total_flights_won += 1
                                        if flight_key in flight_stats:
                                            flight_stats[flight_key]['wins'] += 1
                                    break

        # Calculate proportionally-weighted FWS for this match
        if available_weight > 0:
            match_fws = points_earned / available_weight
            dual_match_fws_scores.append(match_fws)

    if not dual_match_fws_scores:
        return {
            'normalized_fws': 0.0,
            'match_count': 0,
            'fws_pct': 0.0,
            'flight_breakdown': flight_stats,
            'total_flights_won': 0,
            'total_flights_played': 0
        }

    # Average of normalized match FWS scores (already in 0-1 range)
    avg_fws = sum(dual_match_fws_scores) / len(dual_match_fws_scores)

    # Simple FWS percentage (flights won / flights played)
    fws_pct = (total_flights_won / total_flights_played * 100) if total_flights_played > 0 else 0.0

    return {
        'normalized_fws': avg_fws,
        'match_count': len(dual_match_fws_scores),
        'fws_pct': fws_pct,
        'flight_breakdown': flight_stats,
        'total_flights_won': total_flights_won,
        'total_flights_played': total_flights_played
    }


def build_rankings(data_dir, master_school_list):
    """Build rankings for all schools across all years and genders."""
    school_info = load_master_school_list(master_school_list)
    school_data = defaultdict(lambda: defaultdict(dict))
    raw_data_cache = defaultdict(lambda: defaultdict(dict))

    data_path = Path(data_dir)

    for year_dir in sorted(data_path.iterdir()):
        if not year_dir.is_dir():
            continue
        year = year_dir.name
        if not year.isdigit() or int(year) < 2021 or int(year) > 2025:
            continue

        print(f"Processing year {year}...")

        for json_file in year_dir.glob('school_*_gender_*.json'):
            parts = json_file.stem.split('_')
            school_id = int(parts[1])
            gender_id = int(parts[3])
            gender = GENDER_MAP.get(gender_id, 'Unknown')

            with open(json_file, 'r') as f:
                data = json.load(f)

            raw_data_cache[year][gender][school_id] = data
            results, opponents = process_school_data(data, school_id)
            wins, losses, ties = get_dual_match_record(data.get('meets', []), school_id)

            # Get league record
            info = school_info.get(school_id, {})
            school_league = info.get('league', '')
            league_wins, league_losses, league_ties = get_league_record(
                data.get('meets', []), school_id, school_league, school_info
            )

            if results:
                # FWS calculation returns dict with breakdown data
                fws_data = calculate_fws_per_match(data, school_id)

                # Calculate simple Win Percentage (WP) - ties count as 0.5 wins
                total_duals = wins + losses + ties
                wp = (wins + ties * 0.5) / total_duals if total_duals > 0 else 0.0

                school_data[year][gender][school_id] = {
                    'wp': wp,  # Simple win percentage for RPI
                    'opponents': opponents,
                    'results': results,
                    'matches_played': len(results),
                    'dual_wins': wins,
                    'dual_losses': losses,
                    'dual_ties': ties,
                    'league_wins': league_wins,
                    'league_losses': league_losses,
                    'league_ties': league_ties,
                    # FWS data
                    'fws': fws_data['normalized_fws'] * MAX_FWS,  # Scale to 0-3.95 for display
                    'normalized_fws': fws_data['normalized_fws'],  # 0-1 range for Power Index
                    'fws_pct': fws_data['fws_pct'],  # Simple percentage (flights won / played)
                    'fws_match_count': fws_data['match_count'],
                    'flight_breakdown': fws_data['flight_breakdown'],
                    'total_flights_won': fws_data['total_flights_won'],
                    'total_flights_played': fws_data['total_flights_played'],
                }

    # Calculate OWP (Opponent Win Percentage) - based on simple WP
    for year in school_data:
        for gender in school_data[year]:
            for school_id in school_data[year][gender]:
                school = school_data[year][gender][school_id]
                opponents = school['opponents']

                opponent_wps = []
                for opp_id in opponents:
                    if opp_id in school_data[year][gender]:
                        opponent_wps.append(school_data[year][gender][opp_id]['wp'])
                    else:
                        # Unknown opponents (e.g., Idaho schools) rated as neutral average
                        opponent_wps.append(0.5)

                owp = sum(opponent_wps) / len(opponent_wps) if opponent_wps else 0.5
                school['owp'] = owp

    # Calculate OOWP (Opponent's Opponent Win Percentage) and final APR
    for year in school_data:
        for gender in school_data[year]:
            for school_id in school_data[year][gender]:
                school = school_data[year][gender][school_id]
                opponents = school['opponents']

                # OOWP = average of all opponents' OWP values
                opponent_owps = []
                for opp_id in opponents:
                    if opp_id in school_data[year][gender]:
                        opponent_owps.append(school_data[year][gender][opp_id]['owp'])
                    else:
                        # Unknown opponents rated as neutral average
                        opponent_owps.append(0.5)

                oowp = sum(opponent_owps) / len(opponent_owps) if opponent_owps else 0.5
                school['oowp'] = oowp

                # APR = Standard RPI formula: (WP * 0.25) + (OWP * 0.50) + (OOWP * 0.25)
                school['apr'] = (school['wp'] * WP_WEIGHT) + (school['owp'] * OWP_WEIGHT) + (oowp * OOWP_WEIGHT)

                # Power Index = 50/50 split between Results (APR) and Depth (FWS)
                school['power_index'] = (school['apr'] * APR_WEIGHT) + (school['normalized_fws'] * FWS_WEIGHT)

    # Build output
    output = []
    for year in sorted(school_data.keys()):
        for gender in sorted(school_data[year].keys()):
            # Initial sort by Power Index
            ranked = sorted(
                school_data[year][gender].items(),
                key=lambda x: x[1]['power_index'],
                reverse=True
            )

            # Calculate league rankings for H2H league position condition
            league_rankings = {}  # {league: [(school_id, league_rank), ...]}
            league_groups = defaultdict(list)
            for i, (school_id, stats) in enumerate(ranked):
                info = school_info.get(school_id, {})
                league = info.get('league', '')
                if league:
                    league_groups[league].append((school_id, i + 1, stats))  # (id, state_rank, stats)

            # Assign league ranks based on state rank order within each league
            school_league_rank = {}  # {school_id: league_rank}
            for league, teams in league_groups.items():
                # Teams already sorted by state rank (from ranked list order)
                for league_rank, (school_id, state_rank, stats) in enumerate(teams, 1):
                    school_league_rank[school_id] = league_rank

            # H2H Tiebreaker Pass with two conditions:
            # A: Statewide PI Gap (within 2%)
            # B: League Context (same league, within 2 league rank spots)
            h2h_swaps = []  # [(winner_id, loser_id, wins, losses, reason)]
            swapped_pairs = set()  # Track swapped pairs to detect circles

            def would_create_circle(new_winner, new_loser, existing_swaps):
                """Check if adding this swap would create a circular dependency."""
                # Build graph of who beat whom via swaps
                beat_graph = defaultdict(set)
                for swap in existing_swaps:
                    winner, loser = swap[0], swap[1]
                    beat_graph[winner].add(loser)

                # Add the proposed swap
                beat_graph[new_winner].add(new_loser)

                # Check if there's a path from new_loser back to new_winner (would be circular)
                visited = set()
                stack = [new_loser]
                while stack:
                    current = stack.pop()
                    if current == new_winner:
                        return True  # Circle detected
                    if current in visited:
                        continue
                    visited.add(current)
                    stack.extend(beat_graph.get(current, []))
                return False

            # PHASE 1: In-League H2H enforcement
            # For same-league teams, if Team A beat Team B H2H, Team A should rank above Team B
            # This can move teams multiple positions across the entire ranking
            for league, teams in league_groups.items():
                if len(teams) < 2:
                    continue

                # Get all H2H results within this league
                league_h2h = {}  # {(winner_id, loser_id): (wins, losses)}
                for school_id, state_rank, stats in teams:
                    if school_id not in raw_data_cache[year][gender]:
                        continue
                    school_meets = raw_data_cache[year][gender][school_id].get('meets', [])

                    for other_id, other_rank, other_stats in teams:
                        if school_id == other_id:
                            continue
                        if other_id not in raw_data_cache[year][gender]:
                            continue

                        h2h_detail = get_head_to_head_detailed(school_meets, school_id, other_id)
                        if h2h_detail['wins'] > 0 or h2h_detail['losses'] > 0:
                            league_h2h[(school_id, other_id)] = (h2h_detail['wins'], h2h_detail['losses'])

                # Find pairs where lower-ranked team beat higher-ranked team H2H
                # Then bubble them up through the overall ranking
                for (winner_id, loser_id), (wins, losses) in league_h2h.items():
                    if wins <= losses:  # Not a clear winner
                        continue

                    # Find positions of both teams in overall ranking
                    winner_pos = None
                    loser_pos = None
                    for i, (sid, _) in enumerate(ranked):
                        if sid == winner_id:
                            winner_pos = i
                        if sid == loser_id:
                            loser_pos = i

                    # If winner is ranked lower than loser, bubble them up
                    if winner_pos is not None and loser_pos is not None and winner_pos > loser_pos:
                        if not would_create_circle(winner_id, loser_id, h2h_swaps):
                            # Bubble winner up to just above loser
                            current_pos = winner_pos
                            while current_pos > loser_pos:
                                ranked[current_pos], ranked[current_pos - 1] = ranked[current_pos - 1], ranked[current_pos]
                                current_pos -= 1

                            if (winner_id, loser_id) not in swapped_pairs:
                                h2h_swaps.append((winner_id, loser_id, wins, losses, 'League', None))
                                swapped_pairs.add((winner_id, loser_id))

            # PHASE 2: Standard adjacent-pair swap for statewide PI threshold
            i = 0
            while i < len(ranked) - 1:
                school1_id, stats1 = ranked[i]
                school2_id, stats2 = ranked[i + 1]

                info1 = school_info.get(school1_id, {})
                info2 = school_info.get(school2_id, {})
                league1 = info1.get('league', '')
                league2 = info2.get('league', '')

                pi_diff = abs(stats1['power_index'] - stats2['power_index'])

                # Condition A: Statewide PI Gap (within 2%)
                condition_a = pi_diff < H2H_THRESHOLD

                # Condition B: League Context (same league, within 2 league rank spots)
                condition_b = False
                if league1 and league1 == league2:
                    lr1 = school_league_rank.get(school1_id, 0)
                    lr2 = school_league_rank.get(school2_id, 0)
                    if abs(lr1 - lr2) <= H2H_LEAGUE_RANK_THRESHOLD:
                        condition_b = True

                if condition_a or condition_b:
                    # Check H2H - does lower-ranked team (school2) beat higher-ranked (school1)?
                    if school1_id in raw_data_cache[year][gender] and school2_id in raw_data_cache[year][gender]:
                        school2_meets = raw_data_cache[year][gender][school2_id].get('meets', [])
                        h2h_detail = get_head_to_head_detailed(school2_meets, school2_id, school1_id)
                        h2h_wins = h2h_detail['wins']
                        h2h_losses = h2h_detail['losses']

                        # Determine if swap should occur
                        should_swap = False
                        swap_date = None

                        if h2h_wins > h2h_losses:
                            # Clear winner - swap
                            should_swap = True
                            # Get the most recent win date
                            win_matches = [m for m in h2h_detail['matches'] if m['result'] == 'win']
                            if win_matches:
                                swap_date = win_matches[-1]['date']
                        elif h2h_wins == h2h_losses and h2h_wins > 0:
                            # Split series (1-1, 2-2, etc.) - use FWS as tiebreaker
                            total_fws_school2 = sum(m['fws1'] for m in h2h_detail['matches'])
                            total_fws_school1 = sum(m['fws2'] for m in h2h_detail['matches'])
                            if total_fws_school2 > total_fws_school1:
                                should_swap = True
                                swap_date = h2h_detail['matches'][-1]['date'] if h2h_detail['matches'] else None
                            # If FWS also tied or school1 has higher FWS, no swap (default to PI)

                        if should_swap:
                            # Determine reason
                            if condition_a and condition_b:
                                reason = 'Both'
                            elif condition_a:
                                reason = 'Statewide'
                            else:
                                reason = 'League'

                            # Check for circular swap before applying
                            if not would_create_circle(school2_id, school1_id, h2h_swaps):
                                # Swap: school2 beat school1 H2H
                                ranked[i], ranked[i + 1] = ranked[i + 1], ranked[i]
                                h2h_swaps.append((school2_id, school1_id, h2h_wins, h2h_losses, reason, swap_date))
                                swapped_pairs.add((school2_id, school1_id))
                i += 1

            if h2h_swaps:
                print(f"  H2H swaps in {year} {gender}: {len(h2h_swaps)}")

            # Build H2H lookup for nearby teams (for UI display)
            h2h_nearby = {}
            for i, (school_id, stats) in enumerate(ranked):
                nearby_h2h = []
                info = school_info.get(school_id, {})
                my_league = info.get('league', '')

                # Check teams within ±3 state ranks OR same league within ±5 league ranks
                for j in range(len(ranked)):
                    if i == j:
                        continue
                    other_id, other_stats = ranked[j]
                    other_info = school_info.get(other_id, {})
                    other_league = other_info.get('league', '')

                    # Include if within ±3 state ranks
                    state_rank_close = abs(i - j) <= 3

                    # Include if same league and within ±5 league ranks
                    league_close = False
                    if my_league and my_league == other_league:
                        my_lr = school_league_rank.get(school_id, 0)
                        other_lr = school_league_rank.get(other_id, 0)
                        if abs(my_lr - other_lr) <= 5:
                            league_close = True

                    if state_rank_close or league_close:
                        if school_id in raw_data_cache[year][gender]:
                            school_meets = raw_data_cache[year][gender][school_id].get('meets', [])
                            h2h_detail = get_head_to_head_detailed(school_meets, school_id, other_id)
                            wins = h2h_detail['wins']
                            losses = h2h_detail['losses']
                            ties = h2h_detail['ties']

                            if wins + losses + ties > 0:
                                # Get match dates
                                match_dates = [m['date'] for m in h2h_detail['matches'] if m['date']]

                                # Determine if this matchup triggered H2H
                                swap_reason = None
                                swap_date = None
                                for swap in h2h_swaps:
                                    if (swap[0] == school_id and swap[1] == other_id) or \
                                       (swap[0] == other_id and swap[1] == school_id):
                                        swap_reason = swap[4]
                                        swap_date = swap[5] if len(swap) > 5 else None
                                        break

                                # Check if same league for league-specific tooltip
                                is_league_match = my_league and my_league == other_league

                                nearby_h2h.append({
                                    'opponent_id': other_id,
                                    'opponent_name': other_info.get('name', f'School {other_id}'),
                                    'opponent_rank': j + 1,
                                    'opponent_league_rank': school_league_rank.get(other_id, 0),
                                    'wins': wins,
                                    'losses': losses,
                                    'ties': ties,
                                    'match_dates': match_dates,
                                    'swap_reason': swap_reason,  # 'Statewide', 'League', 'Both', or None
                                    'swap_date': swap_date,
                                    'is_league_match': is_league_match
                                })

                h2h_nearby[school_id] = nearby_h2h

            # Generate output with final ranks
            for rank, (school_id, stats) in enumerate(ranked, 1):
                info = school_info.get(school_id, {})

                # Check if this team was boosted by H2H and get the reason
                h2h_boosted = False
                h2h_boost_reason = None
                for swap in h2h_swaps:
                    if swap[0] == school_id:
                        h2h_boosted = True
                        h2h_boost_reason = swap[4]  # 'Statewide', 'League', or 'Both'
                        break

                # Calculate flight breakdown percentages
                flight_breakdown = stats.get('flight_breakdown', {})
                flight_pcts = {}
                for flight, data in flight_breakdown.items():
                    if data['played'] > 0:
                        flight_pcts[flight] = round(data['wins'] / data['played'] * 100, 1)
                    else:
                        flight_pcts[flight] = None

                output.append({
                    'year': int(year),
                    'gender': gender,
                    'rank': rank,  # State rank (all schools)
                    'class_rank': 0,  # Will be calculated below
                    'school_id': school_id,
                    'school_name': info.get('name', f'School {school_id}'),
                    'city': info.get('city', ''),
                    'coords': get_city_coords(info.get('city', '')),
                    'classification': info.get('classification', ''),
                    'league': info.get('league', ''),
                    'league_rank': school_league_rank.get(school_id, 0),  # Rank within league
                    'wp': round(stats['wp'], 4),      # Win Percentage (simple)
                    'owp': round(stats['owp'], 4),    # Opponent Win Percentage
                    'oowp': round(stats['oowp'], 4),  # Opponent's Opponent Win Percentage
                    'apr': round(stats['apr'], 4),    # RPI: (WP*0.25)+(OWP*0.50)+(OOWP*0.25)
                    'fws': round(stats['fws'], 4),    # Proportional FWS (0-3.95 scale)
                    'normalized_fws': round(stats['normalized_fws'], 4),  # FWS normalized (0-1)
                    'fws_pct': round(stats.get('fws_pct', 0), 1),  # Simple percentage (flights won / played)
                    'fws_plus': 100,  # Will be calculated below (league-adjusted, 100 = average)
                    'power_index': round(stats['power_index'], 4),  # (APR*0.50)+(Normalized_FWS*0.50)
                    'matches_played': stats['matches_played'],
                    'opponents_count': len(stats['opponents']),
                    'record': f"{stats['dual_wins']}-{stats['dual_losses']}-{stats['dual_ties']}",
                    'wins': stats['dual_wins'],
                    'losses': stats['dual_losses'],
                    'ties': stats['dual_ties'],
                    'league_record': f"{stats['league_wins']}-{stats['league_losses']}-{stats['league_ties']}",
                    'league_wins': stats['league_wins'],
                    'league_losses': stats['league_losses'],
                    'league_ties': stats['league_ties'],
                    'h2h_boosted': h2h_boosted,       # True if rank improved via H2H tiebreaker
                    'h2h_boost_reason': h2h_boost_reason,  # 'Statewide', 'League', 'Both', or None
                    'h2h_nearby': h2h_nearby.get(school_id, []),  # H2H records vs nearby teams
                    'flight_breakdown': flight_pcts,  # Win % per flight position
                    'total_flights_won': stats.get('total_flights_won', 0),
                    'total_flights_played': stats.get('total_flights_played', 0),
                })

    # Calculate class_rank and FWS+ (league-adjusted) for each year/gender/classification
    class_groups = defaultdict(list)
    for entry in output:
        key = (entry['year'], entry['gender'], entry['classification'])
        class_groups[key].append(entry)

    for key, entries in class_groups.items():
        # Sort by state rank (already sorted by Power Index)
        entries.sort(key=lambda x: x['rank'])

        # Calculate classification average FWS%
        fws_pcts = [e['fws_pct'] for e in entries if e['fws_pct'] > 0]
        class_avg_fws_pct = sum(fws_pcts) / len(fws_pcts) if fws_pcts else 50.0

        for class_rank, entry in enumerate(entries, 1):
            entry['class_rank'] = class_rank
            # FWS+ = (team FWS% / class avg FWS%) * 100
            # 100 = average, >100 = better than average, <100 = worse
            if class_avg_fws_pct > 0 and entry['fws_pct'] > 0:
                entry['fws_plus'] = round(entry['fws_pct'] / class_avg_fws_pct * 100, 0)
            else:
                entry['fws_plus'] = 100

    return output, school_data, raw_data_cache, school_info


def calculate_league_power_scores(rankings):
    """Calculate Conference Power Score and Depth Score for each league."""
    from collections import defaultdict

    # Group by year, gender, league
    league_data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for r in rankings:
        if r['league']:
            league_data[r['year']][r['gender']][r['league']].append(r)

    league_scores = []
    for year in league_data:
        for gender in league_data[year]:
            for league, teams in league_data[year][gender].items():
                if not teams:
                    continue

                # Sort by APR descending
                sorted_teams = sorted(teams, key=lambda x: x['apr'], reverse=True)

                # Avg APR of all teams
                avg_apr = sum(t['apr'] for t in sorted_teams) / len(sorted_teams)

                # Top 4 depth score
                top_4 = sorted_teams[:4]
                depth_score = sum(t['apr'] for t in top_4) / len(top_4) if top_4 else 0

                # Get classification from first team
                classification = sorted_teams[0]['classification'] if sorted_teams else ''

                league_scores.append({
                    'year': year,
                    'gender': gender,
                    'league': league,
                    'classification': classification,
                    'avg_apr': round(avg_apr, 4),
                    'depth_score': round(depth_score, 4),
                    'num_schools': len(sorted_teams),
                    'top_team': sorted_teams[0]['school_name'] if sorted_teams else '',
                })

    return league_scores


def load_state_tournament_results(filepath):
    """Load state tournament results from CSV."""
    results = []
    if not filepath.exists():
        return results
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append({
                'year': int(row['year']),
                'classification': row['classification'],
                'gender': row['gender'],
                'place': int(row['place']),
                'team': row['team'],
                'entries': int(row['entries']),
                'total_points': float(row['total_points']),
            })
    return results


def generate_html(rankings, school_data, raw_data_cache, school_info, state_results):
    """Generate the HTML dashboard with modern UI and playoff simulator."""

    years = sorted(set(r['year'] for r in rankings), reverse=True)
    genders = sorted(set(r['gender'] for r in rankings))
    classifications = sorted(set(r['classification'] for r in rankings if r['classification']))
    leagues = sorted(set(r['league'] for r in rankings if r['league']))

    # Calculate league power scores
    league_scores = calculate_league_power_scores(rankings)

    rankings_json = json.dumps(rankings)
    league_scores_json = json.dumps(league_scores)
    state_results_json = json.dumps(state_results)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Oregon HS Tennis Rankings</title>
    
    <!-- Meta Description -->
    <meta name="description" content="Oregon High School Tennis Rankings - Power Index rankings for OSAA 6A, 5A, and 4A-1A tennis teams. Featuring APR, FWS, and comprehensive team statistics.">
    
    <!-- Favicon -->
    <link rel="icon" type="image/x-icon" href="favicon.ico">
    
    <!-- Open Graph / Facebook -->
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://oregontennis.org/">
    <meta property="og:title" content="Oregon HS Tennis Rankings">
    <meta property="og:description" content="Oregon High School Tennis Rankings - Power Index rankings for OSAA 6A, 5A, and 4A-1A tennis teams. Featuring APR, FWS, and comprehensive team statistics.">
    <meta property="og:image" content="https://oregontennis.org/tennis-ball-social.png">
    
    <!-- Twitter -->
    <meta name="twitter:card" content="summary">
    <meta name="twitter:url" content="https://oregontennis.org/">
    <meta name="twitter:title" content="Oregon HS Tennis Rankings">
    <meta name="twitter:description" content="Oregon High School Tennis Rankings - Power Index rankings for OSAA 6A, 5A, and 4A-1A tennis teams. Featuring APR, FWS, and comprehensive team statistics.">
    <meta name="twitter:image" content="https://oregontennis.org/tennis-ball-social.png">
    
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.datatables.net/1.13.7/css/dataTables.bootstrap5.min.css" rel="stylesheet">
    <style>
        body {{ background: #f8f9fa; }}
        .navbar {{ background: #198754; }}
        .navbar-brand {{ color: #fff !important; font-weight: 600; }}
        .nav-tabs .nav-link {{ color: rgba(255,255,255,0.7); }}
        .nav-tabs .nav-link:hover {{ color: #fff; }}
        .nav-tabs .nav-link.active {{ background: rgba(255,255,255,0.2); color: #fff; border: none; }}
        .toolbar {{ background: #fff; border-bottom: 1px solid #dee2e6; padding: 12px 16px; }}
        .filter-group {{ display: inline-flex; align-items: center; gap: 6px; margin-right: 16px; }}
        .filter-group label {{ font-size: 12px; font-weight: 600; color: #6c757d; margin: 0; }}
        .filter-group select, .filter-group input {{ font-size: 13px; }}
        .table {{ font-size: 13px; }}
        .table th {{ font-size: 11px; text-transform: uppercase; color: #6c757d; font-weight: 600; }}
        .rank-1 {{ color: #ffc107; font-weight: 700; }}
        .rank-2 {{ color: #6c757d; font-weight: 700; }}
        .rank-3 {{ color: #cd7f32; font-weight: 700; }}
        .school-name {{ font-weight: 600; }}
        .apr-high {{ color: #198754; font-weight: 600; }}
        .apr-mid {{ color: #6c757d; }}
        .apr-low {{ color: #dc3545; }}
        .fws-positive {{ background: linear-gradient(90deg, rgba(25,135,84,0.2), rgba(25,135,84,0.1)); }}
        .fws-negative {{ background: linear-gradient(90deg, rgba(220,53,69,0.2), rgba(220,53,69,0.1)); }}
        .power-index {{ color: #0d6efd; font-weight: 700; }}
        .h2h-boosted {{ background: rgba(13,110,253,0.1); }}
        .h2h-badge {{ font-size: 10px; padding: 2px 6px; border-radius: 3px; cursor: help; }}
        .h2h-badge.h2h-win {{ background: #d1e7dd; color: #0f5132; }}
        .h2h-badge.h2h-loss {{ background: #f8d7da; color: #842029; }}
        .h2h-badge.h2h-split {{ background: #fff3cd; color: #664d03; }}
        .h2h-boosted-badge {{ font-size: 14px; margin-left: 4px; cursor: help; }}
        .h2h-tooltip {{ position: relative; display: inline-block; }}
        .h2h-tooltip .h2h-content {{ visibility: hidden; background: #333; color: #fff; padding: 8px 12px; border-radius: 6px; position: absolute; z-index: 1000; bottom: 125%; left: 50%; transform: translateX(-50%); white-space: nowrap; font-size: 11px; }}
        .h2h-tooltip:hover .h2h-content {{ visibility: visible; }}
        .formula-footer {{ margin-top: 12px; padding: 10px 15px; background: #f8f9fa; border-radius: 4px; border-left: 3px solid #198754; }}
        /* Flight breakdown expandable row */
        .flight-detail-row {{ background: #f8f9fa; }}
        .flight-detail-row td {{ padding: 12px 16px !important; }}
        .flight-breakdown {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}
        .flight-stat {{ display: inline-flex; flex-direction: column; align-items: center; padding: 6px 10px; background: #fff; border-radius: 4px; border: 1px solid #dee2e6; min-width: 50px; }}
        .flight-stat-label {{ font-size: 10px; font-weight: 600; color: #6c757d; text-transform: uppercase; }}
        .flight-stat-value {{ font-size: 14px; font-weight: 700; }}
        .flight-stat-value.high {{ color: #198754; }}
        .flight-stat-value.mid {{ color: #6c757d; }}
        .flight-stat-value.low {{ color: #dc3545; }}
        .flight-divider {{ width: 1px; height: 30px; background: #dee2e6; margin: 0 4px; }}
        .expand-icon {{ cursor: pointer; color: #6c757d; margin-right: 4px; transition: transform 0.2s; }}
        .expand-icon.open {{ transform: rotate(90deg); }}
        #rankingsTable tbody tr {{ cursor: pointer; }}
        #rankingsTable tbody tr:hover {{ background: rgba(13,110,253,0.05); }}
        .sort-toggle {{ display: inline-flex; gap: 4px; }}
        .sort-toggle .btn {{ padding: 2px 8px; font-size: 11px; }}
        .sort-toggle .btn.active {{ background: #198754; color: #fff; border-color: #198754; }}
        .league-group {{ border-bottom: 1px solid #dee2e6; padding: 12px 16px; }}
        .league-group:last-child {{ border-bottom: none; }}
        .league-group-header {{ font-weight: 600; color: #198754; margin-bottom: 8px; }}
        .team-checkbox {{ display: flex; align-items: center; gap: 8px; padding: 4px 0; }}
        .team-checkbox input {{ width: 18px; height: 18px; cursor: pointer; }}
        .team-checkbox label {{ cursor: pointer; flex: 1; }}
        .team-checkbox .team-stats {{ font-size: 12px; color: #6c757d; }}
        .team-checkbox.selected {{ background: rgba(25,135,84,0.1); margin: -4px -8px; padding: 4px 8px; border-radius: 4px; }}
        .badge-6a {{ background: #0d6efd; }}
        .badge-5a {{ background: #6f42c1; }}
        .badge-4a {{ background: #198754; }}
        .badge-league {{ background: #e9ecef; color: #495057; font-size: 11px; }}
        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}
        .playoff-container {{ padding: 20px; }}
        .playoff-toolbar {{ background: #fff; border-radius: 8px; padding: 16px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .playoff-toolbar .form-group {{ display: inline-block; margin-right: 16px; }}
        .playoff-toolbar label {{ font-size: 12px; font-weight: 600; color: #6c757d; display: block; margin-bottom: 4px; }}
        .field-list {{ background: #fff; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .field-header {{ padding: 12px 16px; background: #f8f9fa; border-bottom: 1px solid #dee2e6; font-weight: 600; }}
        .field-team {{ display: flex; align-items: center; padding: 10px 16px; border-bottom: 1px solid #f0f0f0; gap: 12px; }}
        .field-team:last-child {{ border-bottom: none; }}
        .field-seed {{ width: 30px; font-weight: 700; color: #198754; }}
        .field-name {{ flex: 1; font-weight: 500; }}
        .field-record {{ width: 60px; color: #495057; font-size: 12px; }}
        .field-apr {{ width: 70px; color: #198754; font-weight: 600; }}
        .field-league {{ font-size: 12px; color: #6c757d; width: 150px; }}
        .comparison-container {{ padding: 20px; }}
        .comparison-toolbar {{ background: #fff; border-radius: 8px; padding: 16px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .comparison-card {{ background: #fff; border-radius: 8px; padding: 16px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .comparison-card h5 {{ margin-bottom: 12px; color: #198754; }}
        .stat-highlight {{ font-size: 24px; font-weight: 700; color: #198754; }}
        .stat-label {{ font-size: 11px; color: #6c757d; text-transform: uppercase; }}
        .team-comparison {{ display: flex; gap: 16px; margin-bottom: 8px; padding: 8px 0; border-bottom: 1px solid #f0f0f0; }}
        .team-comparison:last-child {{ border-bottom: none; }}
        .tc-rank {{ width: 40px; font-weight: 700; color: #198754; }}
        .tc-name {{ flex: 1; font-weight: 500; }}
        .tc-apr {{ width: 70px; }}
        .tc-record {{ width: 60px; }}
        .tc-state {{ width: 100px; text-align: right; }}
        .tc-state-entries {{ color: #6f42c1; }}
        .tc-state-points {{ color: #0d6efd; }}
        .tc-no-state {{ color: #dc3545; font-weight: 600; }}
        .badge-autobid {{ background: #198754; }}
        .badge-atlarge {{ background: #6f42c1; }}
        .badge-bye {{ background: #ffc107; color: #000; }}
        .section-title {{ color: #6c757d; font-size: 12px; font-weight: 600; text-transform: uppercase; margin: 16px 0 8px; }}
        .analysis-container {{ padding: 20px; }}
        .analysis-toolbar {{ background: #fff; border-radius: 8px; padding: 16px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        footer {{ margin-top: 40px; padding: 16px; text-align: center; }}
        footer a {{ color: #6c757d; font-size: 12px; }}

        /* Responsive design for mobile devices */
        @media (max-width: 768px) {{
            .navbar {{ padding: 10px 0; }}
            .navbar .container-fluid {{ flex-direction: column; gap: 10px; }}
            .navbar-brand {{ font-size: 1rem; }}
            
            .nav-tabs {{ flex-wrap: wrap; justify-content: center; gap: 5px; }}
            .nav-tabs .nav-link {{ padding: 6px 12px; font-size: 0.85rem; }}
            
            .toolbar {{ padding: 10px 12px; }}
            .toolbar .filter-group {{ display: block; width: 100%; margin-right: 0; margin-bottom: 10px; }}
            .toolbar .filter-group:last-child {{ margin-bottom: 0; }}
            .toolbar .filter-group label {{ display: block; margin-bottom: 4px; }}
            .toolbar .filter-group select,
            .toolbar .filter-group input {{ width: 100%; }}
            
            .table {{ font-size: 11px; }}
            .table th {{ font-size: 10px; padding: 8px 4px; }}
            .table td {{ padding: 8px 4px; }}
            .table-responsive {{ overflow-x: auto; -webkit-overflow-scrolling: touch; }}
            
            .school-name {{ font-size: 0.9rem; }}
            
            .playoff-container {{ padding: 10px; }}
            .playoff-toolbar {{ padding: 12px; }}
            .playoff-toolbar .form-group {{ display: block; width: 100%; margin-right: 0; margin-bottom: 12px; }}
            .playoff-toolbar .form-group:last-child {{ margin-bottom: 0; }}
            
            .field-team {{ padding: 8px 12px; font-size: 0.9rem; }}
            .field-seed {{ width: 25px; font-size: 0.9rem; }}
            .field-record {{ font-size: 11px; }}
            .field-league {{ font-size: 11px; width: 120px; }}
            
            .comparison-container {{ padding: 10px; }}
            .comparison-toolbar {{ padding: 12px; }}
            .comparison-card {{ padding: 12px; }}
            
            .team-comparison {{ flex-wrap: wrap; gap: 8px; }}
            .tc-rank {{ width: 30px; font-size: 0.9rem; }}
            .tc-name {{ font-size: 0.9rem; }}
            .tc-apr {{ font-size: 0.85rem; }}
            .tc-record {{ font-size: 0.85rem; }}
            .tc-state {{ font-size: 0.85rem; width: 80px; }}
            
            .stat-highlight {{ font-size: 20px; }}
            .stat-label {{ font-size: 10px; }}
            
            .analysis-container {{ padding: 10px; }}
            .analysis-toolbar {{ padding: 12px; }}
            
            .badge {{ font-size: 0.7rem; }}
            
            footer {{ margin-top: 20px; padding: 12px; }}
        }}
        
        @media (max-width: 480px) {{
            .navbar-brand {{ font-size: 0.9rem; }}
            .nav-tabs .nav-link {{ padding: 5px 10px; font-size: 0.75rem; }}
            
            .table {{ font-size: 10px; }}
            .table th {{ font-size: 9px; padding: 6px 2px; }}
            .table td {{ padding: 6px 2px; }}
            
            .stat-highlight {{ font-size: 18px; }}
        }}
    </style>
</head>
<body>
    <nav class="navbar navbar-dark">
        <div class="container-fluid">
            <span class="navbar-brand">Oregon HS Tennis Rankings</span>
            <ul class="nav nav-tabs border-0">
                <li class="nav-item">
                    <a class="nav-link active" href="#" data-tab="rankings">Rankings</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" href="#" data-tab="playoffs">Playoff Simulator</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" href="#" data-tab="comparison">APR vs State</a>
                </li>
                <li class="nav-item" id="analysisNavItem" style="display:none;">
                    <a class="nav-link" href="#" data-tab="analysis">League Analysis</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" href="all-state.html">All-State Teams</a>
                </li>
            </ul>
        </div>
    </nav>

    <!-- Rankings Tab -->
    <div id="rankings-tab" class="tab-content active">
        <div class="toolbar">
            <div class="filter-group">
                <label>Year</label>
                <select id="yearFilter" class="form-select form-select-sm">
                    {chr(10).join(f'<option value="{y}">{y}</option>' for y in years)}
                </select>
            </div>
            <div class="filter-group">
                <label>Gender</label>
                <select id="genderFilter" class="form-select form-select-sm">
                    {chr(10).join(f'<option value="{g}">{g}</option>' for g in genders)}
                </select>
            </div>
            <div class="filter-group">
                <label>Class</label>
                <select id="classFilter" class="form-select form-select-sm">
                    <option value="">All</option>
                    {chr(10).join(f'<option value="{c}">{c}</option>' for c in classifications)}
                </select>
            </div>
            <div class="filter-group">
                <label>League</label>
                <select id="leagueFilter" class="form-select form-select-sm">
                    <option value="">All</option>
                    {chr(10).join(f'<option value="{l}">{l}</option>' for l in leagues)}
                </select>
            </div>
            <div class="filter-group">
                <label>Search</label>
                <input type="text" id="searchBox" class="form-control form-control-sm" placeholder="School..." style="width:140px;">
            </div>
            <div class="filter-group">
                <label>Min Matches</label>
                <input type="number" id="minMatchesFilter" class="form-control form-control-sm" value="3" min="0" max="20" style="width:70px;">
            </div>
            <div class="filter-group">
                <label>Sort By</label>
                <div class="sort-toggle">
                    <button class="btn btn-outline-secondary btn-sm active" id="sortPowerIndex">Power Index</button>
                    <button class="btn btn-outline-secondary btn-sm" id="sortAPR">APR</button>
                </div>
            </div>
        </div>

        <div class="table-responsive">
            <table id="rankingsTable" class="table table-striped table-hover mb-0">
                <thead class="table-light">
                    <tr>
                        <th>State</th>
                        <th>School</th>
                        <th>Class</th>
                        <th>Class Rank</th>
                        <th>League</th>
                        <th>Record</th>
                        <th>H2H</th>
                        <th>League Rec</th>
                        <th>Power Index</th>
                        <th>APR</th>
                        <th>FWS%</th>
                        <th>SOS</th>
                    </tr>
                </thead>
                <tbody></tbody>
            </table>
            <div class="formula-footer">
                <small class="text-muted">
                    <strong>Power Index</strong> = 50% APR + 50% Flight-Weighted Score.
                    <strong>FWS%</strong> = percentage of individual flights won. Hover for FWS+ (100 = classification average).
                </small>
            </div>
        </div>
    </div>

    <!-- Playoff Simulator Tab -->
    <div id="playoffs-tab" class="tab-content">
        <div class="playoff-container">
            <div class="playoff-toolbar">
                <div class="form-group">
                    <label>Year</label>
                    <select id="playoffYear" class="form-select form-select-sm">
                        {chr(10).join(f'<option value="{y}">{y}</option>' for y in years)}
                    </select>
                </div>
                <div class="form-group">
                    <label>Gender</label>
                    <select id="playoffGender" class="form-select form-select-sm">
                        {chr(10).join(f'<option value="{g}">{g}</option>' for g in genders)}
                    </select>
                </div>
                <div class="form-group">
                    <label>Classification</label>
                    <select id="playoffClass" class="form-select form-select-sm">
                        {chr(10).join(f'<option value="{c}">{c}</option>' for c in classifications)}
                    </select>
                </div>
                <div class="form-group">
                    <label>Bracket Size</label>
                    <select id="bracketSize" class="form-select form-select-sm">
                        <option value="8">8 Teams</option>
                        <option value="12" selected>12 Teams</option>
                        <option value="16">16 Teams</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Min Matches</label>
                    <input type="number" id="playoffMinMatches" class="form-control form-control-sm" value="3" min="0" max="20" style="width:70px;">
                </div>
                <div class="form-group">
                    <label>&nbsp;</label>
                    <button id="loadTeamsBtn" class="btn btn-outline-secondary btn-sm">Load Teams</button>
                </div>
            </div>

            <div class="playoff-toolbar" style="margin-top:10px; padding-top:10px; border-top:1px solid #dee2e6;">
                <div class="form-group">
                    <label>Bracket Mode</label>
                    <select id="bracketMode" class="form-select form-select-sm">
                        <option value="pure">Pure Seeding (1v16, 2v15...)</option>
                        <option value="regional">OSAA Regional (Travel Optimized)</option>
                    </select>
                </div>
                <div id="regionalInfo" class="form-group" style="display:none;">
                    <small class="text-muted">
                        <strong>Regional Mode:</strong> Seeds 1-4 protected. Seeds 5-12 optimized for proximity (no same-district matchups).
                    </small>
                </div>
            </div>

            <div id="autobidSelection" style="display:none;">
                <div class="section-title">Step 1: Select Auto-Bid Teams (League Champions)</div>
                <p class="text-muted small mb-2">Check the boxes for confirmed league champions. Remaining spots will be filled by Power Index.</p>
                <div id="leagueTeamsList" class="bg-white rounded shadow-sm mb-3"></div>
                <button id="generateFieldBtn" class="btn btn-success">Generate Playoff Field</button>
            </div>

            <div id="playoffResults"></div>
        </div>
    </div>

    <!-- APR vs State Comparison Tab -->
    <div id="comparison-tab" class="tab-content">
        <div class="comparison-container">
            <div class="comparison-toolbar">
                <div class="form-group" style="display:inline-block; margin-right:16px;">
                    <label style="display:block; font-size:12px; font-weight:600; color:#6c757d; margin-bottom:4px;">Year</label>
                    <select id="compYear" class="form-select form-select-sm">
                        {chr(10).join(f'<option value="{y}">{y}</option>' for y in years)}
                    </select>
                </div>
                <div class="form-group" style="display:inline-block; margin-right:16px;">
                    <label style="display:block; font-size:12px; font-weight:600; color:#6c757d; margin-bottom:4px;">Gender</label>
                    <select id="compGender" class="form-select form-select-sm">
                        {chr(10).join(f'<option value="{g}">{g}</option>' for g in genders)}
                    </select>
                </div>
                <div class="form-group" style="display:inline-block; margin-right:16px;">
                    <label style="display:block; font-size:12px; font-weight:600; color:#6c757d; margin-bottom:4px;">Classification</label>
                    <select id="compClass" class="form-select form-select-sm">
                        {chr(10).join(f'<option value="{c}">{c}</option>' for c in classifications)}
                    </select>
                </div>
                <div class="form-group" style="display:inline-block; margin-right:16px;">
                    <label style="display:block; font-size:12px; font-weight:600; color:#6c757d; margin-bottom:4px;">Bracket Size</label>
                    <select id="compBracket" class="form-select form-select-sm">
                        <option value="8">8 Teams</option>
                        <option value="12" selected>12 Teams</option>
                        <option value="16">16 Teams</option>
                    </select>
                </div>
                <div class="form-group" style="display:inline-block;">
                    <label style="display:block;">&nbsp;</label>
                    <button id="runComparison" class="btn btn-success btn-sm">Compare</button>
                </div>
            </div>
            <div id="comparisonResults"></div>
        </div>
    </div>

    <!-- League Analysis Tab (Hidden) -->
    <div id="analysis-tab" class="tab-content">
        <div class="analysis-container">
            <div class="analysis-toolbar">
                <div class="form-group" style="display:inline-block; margin-right:16px;">
                    <label style="display:block; font-size:12px; font-weight:600; color:#6c757d; margin-bottom:4px;">Year</label>
                    <select id="analysisYear" class="form-select form-select-sm">
                        {chr(10).join(f'<option value="{y}">{y}</option>' for y in years)}
                    </select>
                </div>
                <div class="form-group" style="display:inline-block; margin-right:16px;">
                    <label style="display:block; font-size:12px; font-weight:600; color:#6c757d; margin-bottom:4px;">Gender</label>
                    <select id="analysisGender" class="form-select form-select-sm">
                        {chr(10).join(f'<option value="{g}">{g}</option>' for g in genders)}
                    </select>
                </div>
                <div class="form-group" style="display:inline-block;">
                    <label style="display:block;">&nbsp;</label>
                    <button id="refreshAnalysis" class="btn btn-success btn-sm">Refresh</button>
                </div>
            </div>
            <div class="table-responsive">
                <table id="analysisTable" class="table table-striped">
                    <thead class="table-light">
                        <tr>
                            <th>#</th>
                            <th>League</th>
                            <th>Classification</th>
                            <th>Avg APR</th>
                            <th>Top 4 APR</th>
                            <th>Schools</th>
                            <th>Top Team</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
    </div>

    <footer>
        <a href="?view=analysis" id="adminLink">Admin Analysis</a>
    </footer>

    <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.7/js/jquery.dataTables.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.7/js/dataTables.bootstrap5.min.js"></script>

    <script>
        const rankings = {rankings_json};
        const leagueScores = {league_scores_json};
        const stateResults = {state_results_json};
        let table;

        // Check for analysis view URL param
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('view') === 'analysis') {{
            document.getElementById('analysisNavItem').style.display = 'block';
        }}

        // Tab switching
        document.querySelectorAll('[data-tab]').forEach(tab => {{
            tab.addEventListener('click', (e) => {{
                e.preventDefault();
                document.querySelectorAll('[data-tab]').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById(tab.dataset.tab + '-tab').classList.add('active');
                if (tab.dataset.tab === 'analysis') refreshAnalysisTable();
            }});
        }});

        // Admin link
        document.getElementById('adminLink').addEventListener('click', (e) => {{
            e.preventDefault();
            document.getElementById('analysisNavItem').style.display = 'block';
            document.querySelectorAll('[data-tab]').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.querySelector('[data-tab="analysis"]').classList.add('active');
            document.getElementById('analysis-tab').classList.add('active');
            refreshAnalysisTable();
        }});

        let currentSortColumn = 8; // Power Index by default (after adding Class Rank column)

        $(document).ready(function() {{
            table = $('#rankingsTable').DataTable({{
                data: rankings,
                columns: [
                    {{
                        data: 'rank',
                        render: (d, t) => {{
                            if (t !== 'display') return d;
                            let cls = '';
                            if (d === 1) cls = 'rank-1';
                            else if (d === 2) cls = 'rank-2';
                            else if (d === 3) cls = 'rank-3';
                            return `<span class="${{cls}}">${{d}}</span>`;
                        }}
                    }},
                    {{ data: 'school_name', render: d => `<span class="school-name">${{d}}</span>` }},
                    {{
                        data: 'classification',
                        render: (d, t) => {{
                            if (t !== 'display' || !d) return d || '-';
                            let cls = 'badge ';
                            if (d === '6A') cls += 'badge-6a';
                            else if (d === '5A') cls += 'badge-5a';
                            else cls += 'badge-4a';
                            return `<span class="${{cls}}">${{d}}</span>`;
                        }}
                    }},
                    {{
                        data: 'class_rank',
                        render: (d, t) => {{
                            if (t !== 'display') return d;
                            let rankCls = '';
                            if (d === 1) rankCls = 'rank-1';
                            else if (d === 2) rankCls = 'rank-2';
                            else if (d === 3) rankCls = 'rank-3';
                            return `<span class="${{rankCls}}">${{d}}</span>`;
                        }}
                    }},
                    {{ data: 'league', render: (d) => d ? `<span class="badge badge-league">${{d}}</span>` : '-' }},
                    {{ data: 'record' }},
                    {{
                        data: 'h2h_nearby',
                        render: (d, t, row) => {{
                            if (t !== 'display') return d ? d.length : 0;
                            if (!d || d.length === 0) return '-';

                            // Calculate overall H2H record vs nearby teams (including ties)
                            let wins = 0, losses = 0, ties = 0;
                            d.forEach(h => {{
                                wins += h.wins;
                                losses += h.losses;
                                ties += h.ties || 0;
                            }});

                            if (wins + losses + ties === 0) return '-';

                            let cls = 'h2h-badge ';
                            if (wins > losses) cls += 'h2h-win';
                            else if (losses > wins) cls += 'h2h-loss';
                            else cls += 'h2h-split';

                            // Build tooltip content with swap reasons and dates
                            const tooltipLines = d.map(h => {{
                                const tieStr = (h.ties || 0) > 0 ? `-${{h.ties}}` : '';
                                let line = `#${{h.opponent_rank}} ${{h.opponent_name}}: ${{h.wins}}-${{h.losses}}${{tieStr}}`;

                                // Add match dates if available
                                if (h.match_dates && h.match_dates.length > 0) {{
                                    line += ` <span style="color:#aaa">(${{h.match_dates.join(', ')}})</span>`;
                                }}

                                // Add swap reason indicator
                                if (h.swap_reason) {{
                                    if (h.swap_reason === 'League' && h.is_league_match) {{
                                        line += `<br><span style="color:#17a2b8">  ↳ League H2H: Result recognized for league standings</span>`;
                                    }} else if (h.swap_reason === 'Statewide') {{
                                        line += ` <span style="color:#ffc107">(PI Proximity)</span>`;
                                    }} else if (h.swap_reason === 'Both') {{
                                        line += ` <span style="color:#ffc107">(PI + League)</span>`;
                                    }}
                                }}
                                return line;
                            }}).join('<br>');

                            // Show 🪢 emoji with reason if boosted
                            let boostBadge = '';
                            if (row.h2h_boosted) {{
                                const reasonText = row.h2h_boost_reason === 'Statewide' ? 'PI Proximity' :
                                                  row.h2h_boost_reason === 'League' ? 'League Position' :
                                                  row.h2h_boost_reason === 'Both' ? 'PI + League' : 'H2H';
                                boostBadge = `<span class="h2h-boosted-badge" title="Rank boosted: ${{reasonText}}">🪢</span>`;
                            }}

                            // Format record with ties if present
                            const tieDisplay = ties > 0 ? `-${{ties}}` : '';

                            return `<div class="h2h-tooltip">
                                <span class="${{cls}}">${{wins}}-${{losses}}${{tieDisplay}}</span>${{boostBadge}}
                                <div class="h2h-content">${{tooltipLines}}</div>
                            </div>`;
                        }}
                    }},
                    {{ data: 'league_record' }},
                    {{
                        data: 'power_index',
                        render: (d, t) => {{
                            if (t !== 'display') return d;
                            return `<span class="power-index">${{d.toFixed(4)}}</span>`;
                        }}
                    }},
                    {{
                        data: 'apr',
                        render: (d, t) => {{
                            if (t !== 'display') return d;
                            let cls = 'apr-mid';
                            if (d >= 0.55) cls = 'apr-high';
                            else if (d < 0.40) cls = 'apr-low';
                            return `<span class="${{cls}}">${{d.toFixed(4)}}</span>`;
                        }}
                    }},
                    {{
                        data: 'fws_pct',
                        render: (d, t, row) => {{
                            if (t !== 'display') return d;
                            const fwsPlus = row.fws_plus || 100;
                            let cls = '';
                            if (fwsPlus >= 115) cls = 'apr-high';
                            else if (fwsPlus < 85) cls = 'apr-low';
                            const tooltip = `FWS+ ${{fwsPlus}} (100 = avg)`;
                            return `<span class="${{cls}}" title="${{tooltip}}" style="cursor:help;">${{d.toFixed(1)}}%</span>`;
                        }}
                    }},
                    {{
                        data: 'owp',
                        render: (d, t) => {{
                            if (t !== 'display') return d;
                            // SOS (Strength of Schedule) = OWP
                            let cls = 'apr-mid';
                            if (d >= 0.55) cls = 'apr-high';
                            else if (d < 0.45) cls = 'apr-low';
                            return `<span class="${{cls}}">${{d.toFixed(3)}}</span>`;
                        }}
                    }}
                ],
                order: [[8, 'desc']],  // Power Index column (after adding Class Rank)
                pageLength: 50,
                lengthMenu: [[25, 50, 100, -1], [25, 50, 100, "All"]],
                dom: 'lrtip'
            }});

            // Sort toggle buttons
            $('#sortPowerIndex').on('click', function() {{
                $(this).addClass('active');
                $('#sortAPR').removeClass('active');
                table.order([[8, 'desc']]).draw();  // Power Index is column 8
            }});

            $('#sortAPR').on('click', function() {{
                $(this).addClass('active');
                $('#sortPowerIndex').removeClass('active');
                table.order([[9, 'desc']]).draw();  // APR is column 9
            }});

            // Filtering
            $.fn.dataTable.ext.search.push((settings, data, idx) => {{
                const row = table.row(idx).data();
                const year = $('#yearFilter').val();
                const gender = $('#genderFilter').val();
                const cls = $('#classFilter').val();
                const league = $('#leagueFilter').val();
                const minMatches = parseInt($('#minMatchesFilter').val()) || 0;

                if (year && row.year != year) return false;
                if (gender && row.gender !== gender) return false;
                if (cls && row.classification !== cls) return false;
                if (league && row.league !== league) return false;
                const totalMatches = row.wins + row.losses + row.ties;
                if (totalMatches < minMatches) return false;
                return true;
            }});

            $('#yearFilter, #genderFilter, #classFilter, #leagueFilter, #minMatchesFilter').on('change', () => table.draw());
            $('#searchBox').on('keyup', function() {{ table.search(this.value).draw(); }});

            $('#yearFilter').val('{years[0]}');
            table.draw();

            // Expandable row for flight breakdown
            function formatFlightBreakdown(d) {{
                const fb = d.flight_breakdown || {{}};
                const flights = ['S1', 'S2', 'S3', 'S4', 'D1', 'D2', 'D3', 'D4'];

                let html = '<div class="flight-breakdown">';
                html += '<span style="font-weight:600;color:#6c757d;margin-right:8px;">Flight Win %:</span>';

                // Singles
                html += '<div class="flight-breakdown">';
                ['S1', 'S2', 'S3', 'S4'].forEach(f => {{
                    const val = fb[f];
                    let cls = 'mid';
                    if (val !== null && val !== undefined) {{
                        if (val >= 70) cls = 'high';
                        else if (val < 40) cls = 'low';
                        html += `<div class="flight-stat"><span class="flight-stat-label">${{f}}</span><span class="flight-stat-value ${{cls}}">${{val.toFixed(0)}}%</span></div>`;
                    }} else {{
                        html += `<div class="flight-stat"><span class="flight-stat-label">${{f}}</span><span class="flight-stat-value mid">—</span></div>`;
                    }}
                }});
                html += '</div>';

                html += '<div class="flight-divider"></div>';

                // Doubles
                html += '<div class="flight-breakdown">';
                ['D1', 'D2', 'D3', 'D4'].forEach(f => {{
                    const val = fb[f];
                    let cls = 'mid';
                    if (val !== null && val !== undefined) {{
                        if (val >= 70) cls = 'high';
                        else if (val < 40) cls = 'low';
                        html += `<div class="flight-stat"><span class="flight-stat-label">${{f}}</span><span class="flight-stat-value ${{cls}}">${{val.toFixed(0)}}%</span></div>`;
                    }} else {{
                        html += `<div class="flight-stat"><span class="flight-stat-label">${{f}}</span><span class="flight-stat-value mid">—</span></div>`;
                    }}
                }});
                html += '</div>';

                // Add totals
                html += '<div class="flight-divider"></div>';
                html += `<div class="flight-stat"><span class="flight-stat-label">Total</span><span class="flight-stat-value">${{d.total_flights_won || 0}}/${{d.total_flights_played || 0}}</span></div>`;
                html += `<div class="flight-stat"><span class="flight-stat-label">FWS+</span><span class="flight-stat-value ${{d.fws_plus >= 115 ? 'high' : d.fws_plus < 85 ? 'low' : 'mid'}}">${{d.fws_plus || 100}}</span></div>`;

                html += '</div>';
                return html;
            }}

            $('#rankingsTable tbody').on('click', 'tr', function() {{
                const tr = $(this);
                const row = table.row(tr);

                if (tr.hasClass('flight-detail-row')) return;

                if (row.child.isShown()) {{
                    row.child.hide();
                    tr.removeClass('shown');
                }} else {{
                    row.child(formatFlightBreakdown(row.data())).show();
                    row.child().addClass('flight-detail-row');
                    tr.addClass('shown');
                }}
            }});

            $('#loadTeamsBtn').on('click', loadTeamsForSelection);
            $('#generateFieldBtn').on('click', generatePlayoffFieldFromSelection);

            // Bracket mode toggle handler
            $('#bracketMode').on('change', function() {{
                if ($(this).val() === 'regional') {{
                    $('#regionalInfo').show();
                }} else {{
                    $('#regionalInfo').hide();
                }}
                // Regenerate if field already exists
                if (currentPlayoffTeams.length > 0) {{
                    generatePlayoffFieldFromSelection();
                }}
            }});
        }});

        let currentPlayoffTeams = [];
        let currentLeagueTeams = {{}};

        function loadTeamsForSelection() {{
            const year = parseInt($('#playoffYear').val());
            const gender = $('#playoffGender').val();
            const classification = $('#playoffClass').val();
            const minMatches = parseInt($('#playoffMinMatches').val()) || 0;

            currentPlayoffTeams = rankings.filter(r =>
                r.year === year &&
                r.gender === gender &&
                r.classification === classification &&
                (r.wins + r.losses + r.ties) >= minMatches
            );

            if (currentPlayoffTeams.length === 0) {{
                $('#playoffResults').html('<p class="text-muted p-3">No teams found for selected criteria.</p>');
                $('#autobidSelection').hide();
                return;
            }}

            // Group by league
            currentLeagueTeams = {{}};
            currentPlayoffTeams.forEach(t => {{
                if (t.league) {{
                    if (!currentLeagueTeams[t.league]) currentLeagueTeams[t.league] = [];
                    currentLeagueTeams[t.league].push(t);
                }}
            }});

            // Sort each league by league win %, then apply H2H tiebreaker, then Power Index
            Object.keys(currentLeagueTeams).forEach(league => {{
                // First sort by league win % and Power Index
                currentLeagueTeams[league].sort((a, b) => {{
                    const aWinPct = a.league_wins / Math.max(1, a.league_wins + a.league_losses + a.league_ties);
                    const bWinPct = b.league_wins / Math.max(1, b.league_wins + b.league_losses + b.league_ties);
                    if (bWinPct !== aWinPct) return bWinPct - aWinPct;
                    return b.power_index - a.power_index;
                }});

                // Apply H2H swaps for adjacent teams with same league win %
                let swapped = true;
                while (swapped) {{
                    swapped = false;
                    for (let i = 0; i < currentLeagueTeams[league].length - 1; i++) {{
                        const a = currentLeagueTeams[league][i];
                        const b = currentLeagueTeams[league][i + 1];

                        const aWinPct = a.league_wins / Math.max(1, a.league_wins + a.league_losses + a.league_ties);
                        const bWinPct = b.league_wins / Math.max(1, b.league_wins + b.league_losses + b.league_ties);

                        // Only apply H2H if league win % is close (within 0.1)
                        if (Math.abs(aWinPct - bWinPct) <= 0.1) {{
                            // Check if b beat a in H2H
                            const h2hMatch = (b.h2h_nearby || []).find(h =>
                                h.opponent_id === a.school_id && h.is_league_match
                            );
                            if (h2hMatch && h2hMatch.wins > h2hMatch.losses) {{
                                // Swap: b beat a in H2H
                                currentLeagueTeams[league][i] = b;
                                currentLeagueTeams[league][i + 1] = a;
                                swapped = true;
                            }}
                        }}
                    }}
                }}
            }});

            // Build selection UI
            let html = '';
            Object.keys(currentLeagueTeams).sort().forEach(league => {{
                const teams = currentLeagueTeams[league];
                html += `<div class="league-group">
                    <div class="league-group-header">${{league}} (${{teams.length}} teams)</div>`;

                teams.forEach((team, idx) => {{
                    const isTopTeam = idx === 0;

                    // Check for H2H tiebreaker indicator
                    let h2hIndicator = '';
                    let h2hTitle = '';
                    if (team.h2h_boosted && (team.h2h_boost_reason === 'League' || team.h2h_boost_reason === 'Both')) {{
                        h2hIndicator = ' 🪢';
                        h2hTitle = 'H2H tiebreaker applied (League Position)';
                    }}

                    // Find league H2H matchups with adjacent teams
                    let leagueH2H = '';
                    const leagueH2HMatches = (team.h2h_nearby || []).filter(h =>
                        h.is_league_match && (h.wins > 0 || h.losses > 0)
                    );
                    if (leagueH2HMatches.length > 0) {{
                        const h2hSummary = leagueH2HMatches.map(h => {{
                            const result = h.wins > h.losses ? 'W' : (h.losses > h.wins ? 'L' : 'T');
                            return `${{result}} vs ${{h.opponent_name}}`;
                        }}).slice(0, 2).join(', ');
                        leagueH2H = ` <span class="text-muted small">[H2H: ${{h2hSummary}}]</span>`;
                    }}

                    html += `
                        <div class="team-checkbox ${{isTopTeam ? 'selected' : ''}}">
                            <input type="checkbox" id="team_${{team.school_id}}" value="${{team.school_id}}"
                                ${{isTopTeam ? 'checked' : ''}} onchange="updateTeamSelection(this)">
                            <label for="team_${{team.school_id}}" ${{h2hTitle ? `title="${{h2hTitle}}"` : ''}}>
                                ${{team.school_name}}${{h2hIndicator}}
                                <span class="team-stats">
                                    League: ${{team.league_record}} | Overall: ${{team.record}} | PI: ${{team.power_index.toFixed(4)}}${{leagueH2H}}
                                </span>
                            </label>
                        </div>
                    `;
                }});
                html += '</div>';
            }});

            $('#leagueTeamsList').html(html);
            $('#autobidSelection').show();
            $('#playoffResults').empty();
        }}

        function updateTeamSelection(checkbox) {{
            const parent = checkbox.closest('.team-checkbox');
            if (checkbox.checked) {{
                parent.classList.add('selected');
            }} else {{
                parent.classList.remove('selected');
            }}
        }}

        // Distance calculation for regionalization
        function calcDistance(coords1, coords2) {{
            if (!coords1 || !coords2) return 999;
            const R = 3959; // Earth's radius in miles
            const lat1 = coords1[0] * Math.PI / 180;
            const lat2 = coords2[0] * Math.PI / 180;
            const dLat = (coords2[0] - coords1[0]) * Math.PI / 180;
            const dLon = (coords2[1] - coords1[1]) * Math.PI / 180;
            const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                      Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon/2) * Math.sin(dLon/2);
            const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
            return Math.round(R * c);
        }}

        // Check if two teams are in the same league (OSAA rule: no same-league first round matchups)
        function sameLeague(team1, team2) {{
            if (!team1?.league || !team2?.league) return false;
            return team1.league === team2.league;
        }}

        // Generate regionalized matchups using greedy nearest-neighbor (baseball/softball methodology)
        // Hosts (1-8) can match with any Visitor (9-16) based on proximity
        // Constraint: No same-league first-round matchups (OSAA rule)
        // Treats seeds 9-16 as interchangeable "peer group"
        function generateRegionalMatchups(field) {{
            const matchups = [];
            const bracketSize = field.length;

            if (bracketSize === 16) {{
                // Hosts: seeds 1-8, Visitors: seeds 9-16 (peer group)
                const hosts = field.slice(0, 8);
                const visitors = field.slice(8, 16);
                const usedVisitors = new Set();

                // Greedy nearest-neighbor: for each host, find closest available visitor
                hosts.forEach((host, i) => {{
                    let bestMatch = null;
                    let bestDist = Infinity;

                    visitors.forEach((visitor, j) => {{
                        if (usedVisitors.has(j)) return;
                        if (sameLeague(host, visitor)) return; // OSAA rule
                        const dist = calcDistance(host.coords, visitor.coords);
                        if (dist < bestDist) {{
                            bestDist = dist;
                            bestMatch = {{ index: j, team: visitor, dist }};
                        }}
                    }});

                    if (bestMatch) {{
                        usedVisitors.add(bestMatch.index);
                        matchups.push({{
                            seed1: i + 1, team1: host,
                            seed2: 9 + bestMatch.index, team2: bestMatch.team,
                            distance: bestMatch.dist,
                            optimized: true
                        }});
                    }} else {{
                        // Fallback: find any unused visitor (same-league if unavoidable)
                        for (let j = 0; j < visitors.length; j++) {{
                            if (!usedVisitors.has(j)) {{
                                usedVisitors.add(j);
                                const visitor = visitors[j];
                                matchups.push({{
                                    seed1: i + 1, team1: host,
                                    seed2: 9 + j, team2: visitor,
                                    distance: calcDistance(host.coords, visitor?.coords),
                                    conflict: sameLeague(host, visitor)
                                }});
                                break;
                            }}
                        }}
                    }}
                }});
            }} else if (bracketSize === 12) {{
                // 12-team: seeds 1-4 have byes, Hosts: 5-8, Visitors: 9-12
                const hosts = field.slice(4, 8);
                const visitors = field.slice(8, 12);
                const usedVisitors = new Set();

                hosts.forEach((host, i) => {{
                    let bestMatch = null;
                    let bestDist = Infinity;

                    visitors.forEach((visitor, j) => {{
                        if (usedVisitors.has(j)) return;
                        if (sameLeague(host, visitor)) return;
                        const dist = calcDistance(host.coords, visitor.coords);
                        if (dist < bestDist) {{
                            bestDist = dist;
                            bestMatch = {{ index: j, team: visitor, dist }};
                        }}
                    }});

                    if (bestMatch) {{
                        usedVisitors.add(bestMatch.index);
                        matchups.push({{
                            seed1: i + 5, team1: host,
                            seed2: 9 + bestMatch.index, team2: bestMatch.team,
                            distance: bestMatch.dist,
                            optimized: true
                        }});
                    }} else {{
                        for (let j = 0; j < visitors.length; j++) {{
                            if (!usedVisitors.has(j)) {{
                                usedVisitors.add(j);
                                const visitor = visitors[j];
                                matchups.push({{
                                    seed1: i + 5, team1: host,
                                    seed2: 9 + j, team2: visitor,
                                    distance: calcDistance(host.coords, visitor?.coords),
                                    conflict: sameLeague(host, visitor)
                                }});
                                break;
                            }}
                        }}
                    }}
                }});
            }} else if (bracketSize === 8) {{
                // 8-team: Hosts: 1-4, Visitors: 5-8
                const hosts = field.slice(0, 4);
                const visitors = field.slice(4, 8);
                const usedVisitors = new Set();

                hosts.forEach((host, i) => {{
                    let bestMatch = null;
                    let bestDist = Infinity;

                    visitors.forEach((visitor, j) => {{
                        if (usedVisitors.has(j)) return;
                        if (sameLeague(host, visitor)) return;
                        const dist = calcDistance(host.coords, visitor.coords);
                        if (dist < bestDist) {{
                            bestDist = dist;
                            bestMatch = {{ index: j, team: visitor, dist }};
                        }}
                    }});

                    if (bestMatch) {{
                        usedVisitors.add(bestMatch.index);
                        matchups.push({{
                            seed1: i + 1, team1: host,
                            seed2: 5 + bestMatch.index, team2: bestMatch.team,
                            distance: bestMatch.dist,
                            optimized: true
                        }});
                    }} else {{
                        for (let j = 0; j < visitors.length; j++) {{
                            if (!usedVisitors.has(j)) {{
                                usedVisitors.add(j);
                                const visitor = visitors[j];
                                matchups.push({{
                                    seed1: i + 1, team1: host,
                                    seed2: 5 + j, team2: visitor,
                                    distance: calcDistance(host.coords, visitor?.coords),
                                    conflict: sameLeague(host, visitor)
                                }});
                                break;
                            }}
                        }}
                    }}
                }});
            }}

            return matchups;
        }}

        // Generate pure seeding matchups with same-district avoidance
        function generatePureMatchups(field) {{
            const matchups = [];
            const bracketSize = field.length;

            if (bracketSize === 16) {{
                // Hosts: seeds 1-8, Visitors: seeds 9-16
                const hosts = field.slice(0, 8);
                const visitors = field.slice(8, 16);
                const usedVisitors = new Set();

                hosts.forEach((host, i) => {{
                    // Standard opponent index (1v16=index 7, 2v15=index 6, etc.)
                    const standardIdx = 7 - i;
                    let assignedIdx = standardIdx;
                    let isConflict = false;

                    // Check if standard matchup is same-district
                    if (sameLeague(host, visitors[standardIdx])) {{
                        // Try to find a non-same-district swap
                        let found = false;
                        for (let j = 0; j < visitors.length; j++) {{
                            if (usedVisitors.has(j)) continue;
                            if (!sameLeague(host, visitors[j])) {{
                                assignedIdx = j;
                                found = true;
                                break;
                            }}
                        }}
                        if (!found) {{
                            // No swap available, use standard but mark as conflict
                            assignedIdx = standardIdx;
                            isConflict = true;
                        }}
                    }}

                    // If standard opponent already used, find next available
                    if (usedVisitors.has(assignedIdx)) {{
                        for (let j = 0; j < visitors.length; j++) {{
                            if (!usedVisitors.has(j)) {{
                                assignedIdx = j;
                                isConflict = sameLeague(host, visitors[j]);
                                break;
                            }}
                        }}
                    }}

                    usedVisitors.add(assignedIdx);
                    const visitor = visitors[assignedIdx];
                    matchups.push({{
                        seed1: i + 1, team1: host,
                        seed2: 9 + assignedIdx, team2: visitor,
                        distance: calcDistance(host.coords, visitor?.coords),
                        tier: i < 4 ? 'protected' : 'standard',
                        conflict: isConflict
                    }});
                }});
            }} else if (bracketSize === 12) {{
                // 5v12, 6v11, 7v10, 8v9 (1-4 have byes)
                const hosts = field.slice(4, 8);  // Seeds 5-8
                const visitors = field.slice(8, 12);  // Seeds 9-12
                const usedVisitors = new Set();

                hosts.forEach((host, i) => {{
                    // Standard opponent index (5v12=index 3, 6v11=index 2, etc.)
                    const standardIdx = 3 - i;
                    let assignedIdx = standardIdx;
                    let isConflict = false;

                    if (sameLeague(host, visitors[standardIdx])) {{
                        let found = false;
                        for (let j = 0; j < visitors.length; j++) {{
                            if (usedVisitors.has(j)) continue;
                            if (!sameLeague(host, visitors[j])) {{
                                assignedIdx = j;
                                found = true;
                                break;
                            }}
                        }}
                        if (!found) {{
                            assignedIdx = standardIdx;
                            isConflict = true;
                        }}
                    }}

                    if (usedVisitors.has(assignedIdx)) {{
                        for (let j = 0; j < visitors.length; j++) {{
                            if (!usedVisitors.has(j)) {{
                                assignedIdx = j;
                                isConflict = sameLeague(host, visitors[j]);
                                break;
                            }}
                        }}
                    }}

                    usedVisitors.add(assignedIdx);
                    const visitor = visitors[assignedIdx];
                    matchups.push({{
                        seed1: i + 5, team1: host,
                        seed2: 9 + assignedIdx, team2: visitor,
                        distance: calcDistance(host.coords, visitor?.coords),
                        tier: 'standard',
                        conflict: isConflict
                    }});
                }});
            }} else if (bracketSize === 8) {{
                const hosts = field.slice(0, 4);  // Seeds 1-4
                const visitors = field.slice(4, 8);  // Seeds 5-8
                const usedVisitors = new Set();

                hosts.forEach((host, i) => {{
                    const standardIdx = 3 - i;  // 1v8=index 3, 2v7=index 2, etc.
                    let assignedIdx = standardIdx;
                    let isConflict = false;

                    if (sameLeague(host, visitors[standardIdx])) {{
                        let found = false;
                        for (let j = 0; j < visitors.length; j++) {{
                            if (usedVisitors.has(j)) continue;
                            if (!sameLeague(host, visitors[j])) {{
                                assignedIdx = j;
                                found = true;
                                break;
                            }}
                        }}
                        if (!found) {{
                            assignedIdx = standardIdx;
                            isConflict = true;
                        }}
                    }}

                    if (usedVisitors.has(assignedIdx)) {{
                        for (let j = 0; j < visitors.length; j++) {{
                            if (!usedVisitors.has(j)) {{
                                assignedIdx = j;
                                isConflict = sameLeague(host, visitors[j]);
                                break;
                            }}
                        }}
                    }}

                    usedVisitors.add(assignedIdx);
                    const visitor = visitors[assignedIdx];
                    matchups.push({{
                        seed1: i + 1, team1: host,
                        seed2: 5 + assignedIdx, team2: visitor,
                        distance: calcDistance(host.coords, visitor?.coords),
                        tier: 'standard',
                        conflict: isConflict
                    }});
                }});
            }}

            return matchups;
        }}

        function generatePlayoffFieldFromSelection() {{
            const bracketSize = parseInt($('#bracketSize').val());
            const bracketMode = $('#bracketMode').val();

            // Get manually selected auto-bids
            const selectedAutoBids = [];
            const selectedIds = new Set();
            document.querySelectorAll('#leagueTeamsList input[type="checkbox"]:checked').forEach(cb => {{
                const schoolId = parseInt(cb.value);
                const team = currentPlayoffTeams.find(t => t.school_id === schoolId);
                if (team) {{
                    selectedAutoBids.push({{ ...team, qualifyType: 'auto' }});
                    selectedIds.add(schoolId);
                }}
            }});

            // Fill remaining spots with at-large by Power Index
            const remainingSpots = bracketSize - selectedAutoBids.length;
            const atLargeTeams = currentPlayoffTeams
                .filter(t => !selectedIds.has(t.school_id))
                .sort((a, b) => b.power_index - a.power_index)
                .slice(0, Math.max(0, remainingSpots))
                .map(t => ({{ ...t, qualifyType: 'atlarge' }}));

            // Combine and sort by Power Index for seeding
            const field = [...selectedAutoBids, ...atLargeTeams].sort((a, b) => b.power_index - a.power_index);

            let html = `
                <div class="section-title">Qualifying Field (${{field.length}} Teams)</div>
                <div class="field-list">
                    <div class="field-header d-flex justify-content-between">
                        <span>Seed / Team</span>
                        <span>Record / Power Index</span>
                    </div>
            `;

            field.forEach((team, idx) => {{
                const seed = idx + 1;
                const hasBye = bracketSize === 12 && seed <= 4;
                html += `
                    <div class="field-team">
                        <span class="field-seed">${{seed}}</span>
                        <span class="field-name">${{team.school_name}}</span>
                        <span class="badge ${{team.qualifyType === 'auto' ? 'badge-autobid' : 'badge-atlarge'}}">
                            ${{team.qualifyType === 'auto' ? 'AUTO' : 'AT-LARGE'}}
                        </span>
                        ${{hasBye ? '<span class="badge badge-bye ms-1">BYE</span>' : ''}}
                        <span class="field-league">${{team.league || '-'}}</span>
                        <span class="field-record">${{team.record}}</span>
                        <span class="field-apr">${{team.power_index.toFixed(4)}}</span>
                    </div>
                `;
            }});

            html += '</div>';

            const autoCount = field.filter(t => t.qualifyType === 'auto').length;
            const atLargeCount = field.filter(t => t.qualifyType === 'atlarge').length;
            html += `
                <div class="section-title mt-3">Summary</div>
                <div class="bg-white p-3 rounded shadow-sm">
                    <strong>${{field.length}}</strong> teams qualify &bull;
                    <span class="text-success"><strong>${{autoCount}}</strong> auto-bids (selected)</span> &bull;
                    <span style="color:#6f42c1;"><strong>${{atLargeCount}}</strong> at-large (by Power Index)</span>
                    ${{bracketSize === 12 ? ' &bull; Top 4 seeds receive first-round byes' : ''}}
                </div>
            `;

            // Generate matchups based on bracket mode
            const pureMatchups = generatePureMatchups(field);
            const regionalMatchups = bracketMode === 'regional' ? generateRegionalMatchups(field) : pureMatchups;

            const pureMileage = pureMatchups.reduce((sum, m) => sum + (m.distance || 0), 0);
            const regionalMileage = regionalMatchups.reduce((sum, m) => sum + (m.distance || 0), 0);
            const mileageSaved = pureMileage - regionalMileage;

            html += `
                <div class="section-title mt-3">First Round Matchups</div>
                <div class="bg-white p-3 rounded shadow-sm">
            `;

            if (bracketMode === 'regional') {{
                const validMileage = !isNaN(pureMileage) && !isNaN(regionalMileage);
                if (validMileage && mileageSaved > 0) {{
                    html += `
                        <div class="alert alert-success mb-3">
                            <strong>🚗 Mileage Savings:</strong> ${{Math.round(mileageSaved)}} miles saved vs pure seeding
                            <br><small>Pure seeding: ${{Math.round(pureMileage)}} mi | Regional: ${{Math.round(regionalMileage)}} mi</small>
                        </div>
                    `;
                }} else if (validMileage) {{
                    html += `
                        <div class="alert alert-info mb-3">
                            <strong>🚗 Mileage Comparison:</strong> No savings with regional matching
                            <br><small>Pure seeding: ${{Math.round(pureMileage)}} mi | Regional: ${{Math.round(regionalMileage)}} mi</small>
                        </div>
                    `;
                }} else {{
                    html += `
                        <div class="alert alert-warning mb-3">
                            <strong>⚠️ Mileage:</strong> Unable to calculate distances (missing coordinates)
                            <br><small>Pure: ${{pureMileage}} | Regional: ${{regionalMileage}} | Matchups: ${{pureMatchups.length}} pure, ${{regionalMatchups.length}} regional</small>
                        </div>
                    `;
                }}
            }}

            // Define displayMatchups early so we can use it in the bye team section
            const displayMatchups = bracketMode === 'regional' ? regionalMatchups : pureMatchups;

            if (bracketSize === 12) {{
                // Show bye teams and their potential QF opponents
                html += `<div class="section-title mt-3">Quarterfinal Preview (Seeds 1-4 have byes)</div>`;
                html += `<div class="bg-white p-3 rounded shadow-sm mb-3">`;
                html += `<p class="text-muted small mb-2"><em>After first round, winners are reseeded: #1 plays lowest remaining seed, #4 plays highest.</em></p>`;

                const byeTeams = field.slice(0, 4);

                // Get all first round seeds (both high and low from each matchup)
                const firstRoundSeeds = [];
                displayMatchups.forEach(m => {{
                    firstRoundSeeds.push({{ seed: m.seed1, team: m.team1 }});
                    firstRoundSeeds.push({{ seed: m.seed2, team: m.team2 }});
                }});
                // Sort by seed number (ascending = highest seed first like #5, then #6...)
                firstRoundSeeds.sort((a, b) => a.seed - b.seed);

                // Show bye teams with their QF opponents if chalk holds (higher seeds win)
                // If chalk: #5,#6,#7,#8 advance → #1 plays #8, #2 plays #7, #3 plays #6, #4 plays #5
                const chalkWinners = firstRoundSeeds.filter(s => s.seed <= 8).sort((a, b) => b.seed - a.seed);

                byeTeams.forEach((byeTeam, i) => {{
                    const chalkOpponent = chalkWinners[i];
                    const worstCaseOpponent = firstRoundSeeds.filter(s => s.seed > 8).sort((a, b) => b.seed - a.seed)[i];

                    html += `
                        <div style="padding:8px 0; border-bottom:1px solid #eee;">
                            <span class="matchup-seed">#${{i + 1}}</span>
                            <strong>${{byeTeam.school_name}}</strong>
                            <span class="badge bg-secondary ms-1">BYE</span>
                            <span class="text-muted mx-2">→ QF vs</span>
                            <span class="text-muted">
                                ${{chalkOpponent ? `#${{chalkOpponent.seed}} ${{chalkOpponent.team?.school_name}}` : '?'}}
                                <small>(if chalk)</small>
                            </span>
                        </div>
                    `;
                }});
                html += `</div>`;
            }}

            html += `
                <div class="section-title mt-3">First Round Matchups</div>
                <div class="bg-white p-3 rounded shadow-sm">
            `;

            displayMatchups.forEach(m => {{
                const conflictBadge = m.conflict ? '<span class="badge bg-warning text-dark ms-1">⚠️ Same District</span>' : '';
                const optimizedBadge = m.optimized ? '<span class="badge bg-info text-white ms-1">📍 Optimized</span>' : '';
                const tierClass = m.tier === 'flex' ? 'border-start border-info border-3 ps-2' : '';

                html += `
                    <div class="matchup-row ${{tierClass}}" style="padding:8px 0; border-bottom:1px solid #eee;">
                        <span class="matchup-seed">#${{m.seed1}}</span>
                        <strong>${{m.team1?.school_name || 'TBD'}}</strong>
                        <span class="text-muted mx-2">vs</span>
                        <span class="matchup-seed">#${{m.seed2}}</span>
                        <strong>${{m.team2?.school_name || 'TBD'}}</strong>
                        <span class="text-muted ms-2">(${{m.distance === 999 ? '~far' : (m.distance !== undefined ? m.distance : '?')}} mi)</span>
                        ${{conflictBadge}}${{optimizedBadge}}
                    </div>
                `;
            }});

            html += '</div>';

            $('#playoffResults').html(html);
        }}

        function refreshAnalysisTable() {{
            const year = parseInt($('#analysisYear').val());
            const gender = $('#analysisGender').val();
            const filtered = leagueScores
                .filter(ls => ls.year === year && ls.gender === gender)
                .sort((a, b) => b.avg_apr - a.avg_apr);

            const tbody = $('#analysisTable tbody');
            tbody.empty();
            filtered.forEach((ls, idx) => {{
                tbody.append(`
                    <tr>
                        <td>${{idx + 1}}</td>
                        <td><span class="badge badge-league">${{ls.league}}</span></td>
                        <td>${{ls.classification || '-'}}</td>
                        <td class="apr-high">${{ls.avg_apr.toFixed(4)}}</td>
                        <td>${{ls.depth_score.toFixed(4)}}</td>
                        <td>${{ls.num_schools}}</td>
                        <td class="school-name">${{ls.top_team}}</td>
                    </tr>
                `);
            }});
        }}

        $('#refreshAnalysis').on('click', refreshAnalysisTable);
        $('#analysisYear, #analysisGender').on('change', refreshAnalysisTable);

        // APR vs State Comparison
        $('#runComparison').on('click', runComparison);

        function runComparison() {{
            const year = parseInt($('#compYear').val());
            const gender = $('#compGender').val();
            const classification = $('#compClass').val();
            const bracketSize = parseInt($('#compBracket').val());

            // Get all ranked teams for this year/gender/classification
            const allTeams = rankings.filter(r =>
                r.year === year &&
                r.gender === gender &&
                r.classification === classification &&
                (r.wins + r.losses + r.ties) >= 3
            ).sort((a, b) => (b.power_index || b.apr) - (a.power_index || a.apr));

            // Power Index playoff qualifiers (top N by bracket size)
            const piQualifiers = allTeams.slice(0, bracketSize);
            const piQualifierIds = new Set(piQualifiers.map(t => t.school_id));

            // Get state tournament results for this year/gender/classification
            const stateData = stateResults.filter(s =>
                s.year === year &&
                s.gender === gender &&
                s.classification === classification
            ).sort((a, b) => a.place - b.place);

            // Helper to normalize names for matching
            const normalizeName = (name) => name.toLowerCase()
                .replace(/st\\.? mary'?s?.*/i, 'st marys')
                .replace(/oregon episcopal school/i, 'oregon episcopal')
                .replace(/ high school/i, '')
                .replace(/^barlow$/i, 'sam barlow')
                .trim();

            // Match state tournament teams with rankings data
            const stateTeamsWithRecords = stateData.map(stateTeam => {{
                const stateNorm = normalizeName(stateTeam.team);

                // Find matching team in rankings
                let rankingMatch = null;
                let piRank = null;

                for (let i = 0; i < allTeams.length; i++) {{
                    const teamNorm = normalizeName(allTeams[i].school_name);
                    if (stateNorm === teamNorm ||
                        stateNorm.includes(teamNorm) ||
                        teamNorm.includes(stateNorm) ||
                        stateTeam.team.toLowerCase().includes(allTeams[i].school_name.toLowerCase()) ||
                        allTeams[i].school_name.toLowerCase().includes(stateTeam.team.toLowerCase())) {{
                        rankingMatch = allTeams[i];
                        piRank = i + 1;
                        break;
                    }}
                }}

                const hasLosingRecord = rankingMatch ? rankingMatch.wins < rankingMatch.losses : false;
                const wouldQualifyPI = rankingMatch ? piQualifierIds.has(rankingMatch.school_id) : false;
                const winPct = rankingMatch ? rankingMatch.wins / Math.max(1, rankingMatch.wins + rankingMatch.losses + rankingMatch.ties) : null;

                return {{
                    ...stateTeam,
                    rankingMatch,
                    piRank,
                    hasLosingRecord,
                    wouldQualifyPI,
                    winPct
                }};
            }});

            // Calculate statistics
            const teamsWithLosingRecords = stateTeamsWithRecords.filter(t => t.hasLosingRecord);
            const teamsWouldNotQualify = stateTeamsWithRecords.filter(t => !t.wouldQualifyPI && t.rankingMatch);
            const piQualifiersNotAtState = piQualifiers.filter(team => {{
                const teamNorm = normalizeName(team.school_name);
                return !stateData.some(s => {{
                    const stateNorm = normalizeName(s.team);
                    return stateNorm === teamNorm || stateNorm.includes(teamNorm) || teamNorm.includes(stateNorm);
                }});
            }});

            let html = `
                <div class="row mb-4">
                    <div class="col-md-3">
                        <div class="comparison-card text-center">
                            <div class="stat-highlight text-danger">${{teamsWithLosingRecords.length}}</div>
                            <div class="stat-label">State Placers with Losing Records</div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="comparison-card text-center">
                            <div class="stat-highlight text-warning">${{teamsWouldNotQualify.length}}</div>
                            <div class="stat-label">State Placers Who Wouldn't Qualify by PI</div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="comparison-card text-center">
                            <div class="stat-highlight text-success">${{piQualifiersNotAtState.length}}</div>
                            <div class="stat-label">PI Qualifiers NOT at State</div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="comparison-card text-center">
                            <div class="stat-highlight">${{stateData.length}}</div>
                            <div class="stat-label">Total Teams at State Tournament</div>
                        </div>
                    </div>
                </div>
            `;

            // Highlight teams that placed at state with losing records
            if (teamsWithLosingRecords.length > 0) {{
                html += `
                    <div class="comparison-card" style="border-left: 4px solid #dc3545;">
                        <h5 style="color: #dc3545;">State Placers with Losing Records</h5>
                        <p class="text-muted small">These teams placed at the state tournament despite having losing team records. Under the current individual-based system, 1-2 strong players can carry a team to state success:</p>
                        <div class="table-responsive">
                            <table class="table table-sm">
                                <thead class="table-light">
                                    <tr>
                                        <th>State Place</th>
                                        <th>Team</th>
                                        <th>Record</th>
                                        <th>Win %</th>
                                        <th>Entries</th>
                                        <th>Points</th>
                                        <th>PI Rank</th>
                                        <th>Would Qualify?</th>
                                    </tr>
                                </thead>
                                <tbody>
                `;
                teamsWithLosingRecords.forEach(team => {{
                    const record = team.rankingMatch ? team.rankingMatch.record : 'N/A';
                    const winPctDisplay = team.winPct !== null ? (team.winPct * 100).toFixed(0) + '%' : 'N/A';
                    const piRankDisplay = team.piRank ? '#' + team.piRank : 'N/A';
                    const qualifyBadge = team.wouldQualifyPI ?
                        '<span class="badge bg-success">Yes</span>' :
                        '<span class="badge bg-danger">No</span>';
                    html += `
                        <tr class="table-danger">
                            <td><strong>${{team.place}}</strong></td>
                            <td class="school-name">${{team.team}}</td>
                            <td><strong style="color: #dc3545;">${{record}}</strong></td>
                            <td style="color: #dc3545;">${{winPctDisplay}}</td>
                            <td>${{team.entries}}</td>
                            <td>${{team.total_points}}</td>
                            <td>${{piRankDisplay}}</td>
                            <td>${{qualifyBadge}}</td>
                        </tr>
                    `;
                }});
                html += '</tbody></table></div></div>';
            }}

            // Show PI qualifiers that didn't make it to state
            if (piQualifiersNotAtState.length > 0) {{
                html += `
                    <div class="comparison-card" style="border-left: 4px solid #198754;">
                        <h5 style="color: #198754;">Teams Rewarded by Power Index (No State Presence)</h5>
                        <p class="text-muted small">These teams would qualify for playoffs under the Power Index system but had no entries at the individual state tournament:</p>
                `;
                piQualifiersNotAtState.slice(0, 10).forEach(team => {{
                    const piRank = allTeams.findIndex(t => t.school_id === team.school_id) + 1;
                    html += `
                        <div class="team-comparison" style="background: #d1e7dd; padding: 8px; margin: 4px 0; border-radius: 4px;">
                            <span class="tc-rank">#${{piRank}}</span>
                            <span class="tc-name" style="font-weight: bold;">${{team.school_name}}</span>
                            <span class="tc-record">${{team.record}}</span>
                            <span class="tc-apr">PI: ${{(team.power_index || team.apr).toFixed(4)}}</span>
                            <span style="color: #198754;">Full roster depth, no state entries</span>
                        </div>
                    `;
                }});
                if (piQualifiersNotAtState.length > 10) {{
                    html += `<p class="text-muted small">... and ${{piQualifiersNotAtState.length - 10}} more teams</p>`;
                }}
                html += '</div>';
            }}

            // Full state tournament results table
            html += `
                <div class="comparison-card">
                    <h5>All State Tournament Placers vs Power Index Rankings</h5>
                    <p class="text-muted small">Every team that placed at the ${{year}} ${{classification}} ${{gender === 'boys' ? "Boys'" : "Girls'"}} State Tournament, with their season record and Power Index rank:</p>
                    <div class="table-responsive">
                        <table class="table table-sm">
                            <thead class="table-light">
                                <tr>
                                    <th>State Place</th>
                                    <th>Team</th>
                                    <th>Season Record</th>
                                    <th>Win %</th>
                                    <th>Entries</th>
                                    <th>Points</th>
                                    <th>Power Index</th>
                                    <th>PI Rank</th>
                                    <th>Qualifies by PI?</th>
                                </tr>
                            </thead>
                            <tbody>
            `;

            stateTeamsWithRecords.forEach(team => {{
                const record = team.rankingMatch ? team.rankingMatch.record : 'N/A';
                const winPctDisplay = team.winPct !== null ? (team.winPct * 100).toFixed(0) + '%' : 'N/A';
                const piDisplay = team.rankingMatch ? (team.rankingMatch.power_index || team.rankingMatch.apr).toFixed(4) : 'N/A';
                const piRankDisplay = team.piRank ? '#' + team.piRank : 'N/A';
                const qualifyBadge = team.wouldQualifyPI ?
                    '<span class="badge bg-success">Yes</span>' :
                    (team.rankingMatch ? '<span class="badge bg-danger">No</span>' : '<span class="badge bg-secondary">N/A</span>');

                let rowClass = '';
                if (team.hasLosingRecord) rowClass = 'table-danger';
                else if (!team.wouldQualifyPI && team.rankingMatch) rowClass = 'table-warning';

                html += `
                    <tr class="${{rowClass}}">
                        <td><strong>${{team.place}}</strong></td>
                        <td class="school-name">${{team.team}}</td>
                        <td>${{record}}</td>
                        <td>${{winPctDisplay}}</td>
                        <td>${{team.entries}}</td>
                        <td>${{team.total_points}}</td>
                        <td class="power-index">${{piDisplay}}</td>
                        <td>${{piRankDisplay}}</td>
                        <td>${{qualifyBadge}}</td>
                    </tr>
                `;
            }});

            html += `
                            </tbody>
                        </table>
                    </div>
                    <div class="mt-2">
                        <span class="badge bg-danger">Red</span> = Losing record &nbsp;
                        <span class="badge bg-warning text-dark">Yellow</span> = Wouldn't qualify by Power Index &nbsp;
                        <span class="badge bg-light text-dark">White</span> = Would qualify
                    </div>
                </div>
            `;

            // Summary insight
            const losingRecordPct = stateData.length > 0 ? ((teamsWithLosingRecords.length / stateData.length) * 100).toFixed(0) : 0;
            const wouldNotQualifyPct = stateData.length > 0 ? ((teamsWouldNotQualify.length / stateData.length) * 100).toFixed(0) : 0;

            html += `
                <div class="comparison-card">
                    <h5>Key Insight: Individual vs Team Success</h5>
                    <p><strong>${{losingRecordPct}}%</strong> of teams that placed at the state tournament had <strong>losing records</strong> during the regular season.</p>
                    <p><strong>${{wouldNotQualifyPct}}%</strong> of state tournament placers <strong>would NOT qualify</strong> for the playoffs under the Power Index system.</p>
                    <p class="text-muted">This demonstrates how the current individual-based system allows teams to succeed at state on the strength of just 1-2 elite players,
                    even when the team as a whole has a losing record. The Power Index system would instead reward programs that field competitive players across ALL flights throughout the dual match season.</p>
                </div>
            `;

            $('#comparisonResults').html(html);
        }}
    </script>
</body>
</html>'''

    return html


def main():
    script_dir = Path(__file__).parent
    repo_root = script_dir

    data_dir = repo_root / 'data'
    master_school_list = repo_root / 'master_school_list.csv'
    state_results_file = repo_root / 'state_tournament_results.csv'
    output_file = repo_root / 'index.html'
    json_output = repo_root / 'public' / 'data' / 'processed_rankings.json'

    json_output.parent.mkdir(parents=True, exist_ok=True)

    print("Building rankings...")
    rankings, school_data, raw_data_cache, school_info = build_rankings(data_dir, master_school_list)

    print("Loading state tournament results...")
    state_results = load_state_tournament_results(state_results_file)
    print(f"Loaded {len(state_results)} state tournament entries")

    # Save JSON
    with open(json_output, 'w') as f:
        json.dump(rankings, f, indent=2)
    print(f"JSON saved to {json_output}")

    print("Generating HTML dashboard...")
    html = generate_html(rankings, school_data, raw_data_cache, school_info, state_results)

    with open(output_file, 'w') as f:
        f.write(html)

    print(f"Dashboard saved to {output_file}")
    print(f"Total rankings: {len(rankings)}")


if __name__ == '__main__':
    main()
