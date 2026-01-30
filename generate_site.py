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
    Calculate Flight Weighted Score (FWS) per dual match.
    FWS = average of weighted flight wins across all dual matches.
    Returns (fws, match_count) tuple.
    """
    dual_match_fws_scores = []

    for meet in data.get('meets', []):
        if not is_dual_match(meet):
            continue

        # Calculate weighted points won in this match
        match_points = 0.0
        matches = meet.get('matches', {})

        for match_type in ['Singles', 'Doubles']:
            type_matches = matches.get(match_type, [])
            if isinstance(type_matches, list):
                for match in type_matches:
                    flight = match.get('flight', '1')
                    weight = get_flight_weight(match_type, flight)
                    match_teams = match.get('matchTeams', [])

                    for team in match_teams:
                        players = team.get('players', [])
                        for player in players:
                            if player.get('schoolId') == school_id:
                                if team.get('isWinner', False):
                                    match_points += weight
                                break

        dual_match_fws_scores.append(match_points)

    if not dual_match_fws_scores:
        return 0.0, 0

    avg_fws = sum(dual_match_fws_scores) / len(dual_match_fws_scores)
    return avg_fws, len(dual_match_fws_scores)


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
        if not year.isdigit() or int(year) < 2022 or int(year) > 2025:
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
                fws, fws_match_count = calculate_fws_per_match(data, school_id)
                normalized_fws = fws / MAX_FWS  # Normalize to 0-1 range

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
                    'fws': fws,
                    'normalized_fws': normalized_fws,
                    'fws_match_count': fws_match_count,
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
            # Rank by Power Index (primary ranking metric)
            ranked = sorted(
                school_data[year][gender].items(),
                key=lambda x: x[1]['power_index'],
                reverse=True
            )

            for rank, (school_id, stats) in enumerate(ranked, 1):
                info = school_info.get(school_id, {})

                # Calculate win rate for yaw comparison
                total_matches = stats['dual_wins'] + stats['dual_losses'] + stats['dual_ties']
                win_rate = (stats['dual_wins'] + stats['dual_ties'] * 0.5) / max(1, total_matches)

                # Yaw = FWS normalized - win_rate (positive = depth exceeds record)
                yaw = stats['normalized_fws'] - win_rate

                output.append({
                    'year': int(year),
                    'gender': gender,
                    'rank': rank,
                    'school_id': school_id,
                    'school_name': info.get('name', f'School {school_id}'),
                    'classification': info.get('classification', ''),
                    'league': info.get('league', ''),
                    'wp': round(stats['wp'], 4),      # Win Percentage (simple)
                    'owp': round(stats['owp'], 4),    # Opponent Win Percentage
                    'oowp': round(stats['oowp'], 4),  # Opponent's Opponent Win Percentage
                    'apr': round(stats['apr'], 4),    # RPI: (WP*0.25)+(OWP*0.50)+(OOWP*0.25)
                    'fws': round(stats['fws'], 4),    # Raw Flight Weighted Score
                    'normalized_fws': round(stats['normalized_fws'], 4),  # FWS / 3.95
                    'power_index': round(stats['power_index'], 4),  # (APR*0.50)+(FWS*0.50)
                    'yaw': round(yaw, 4),             # Depth vs Record indicator
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
                })

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
                        <th>#</th>
                        <th>School</th>
                        <th>Class</th>
                        <th>League</th>
                        <th>Record</th>
                        <th>League Rec</th>
                        <th>Power Index</th>
                        <th>APR</th>
                        <th>FWS</th>
                        <th>SOS</th>
                    </tr>
                </thead>
                <tbody></tbody>
            </table>
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

        let currentSortColumn = 6; // Power Index by default

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
                    {{ data: 'league', render: (d) => d ? `<span class="badge badge-league">${{d}}</span>` : '-' }},
                    {{ data: 'record' }},
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
                        data: 'fws',
                        render: (d, t, row) => {{
                            if (t !== 'display') return d;
                            // Color based on yaw (depth vs record)
                            const yaw = row.yaw || 0;
                            let cls = '';
                            if (yaw > 0.05) cls = 'fws-positive';
                            else if (yaw < -0.05) cls = 'fws-negative';
                            return `<span class="${{cls}}" style="padding:2px 6px;border-radius:3px;">${{d.toFixed(2)}}</span>`;
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
                order: [[6, 'desc']],
                pageLength: 50,
                lengthMenu: [[25, 50, 100, -1], [25, 50, 100, "All"]],
                dom: 'lrtip'
            }});

            // Sort toggle buttons
            $('#sortPowerIndex').on('click', function() {{
                $(this).addClass('active');
                $('#sortAPR').removeClass('active');
                table.order([[6, 'desc']]).draw();
            }});

            $('#sortAPR').on('click', function() {{
                $(this).addClass('active');
                $('#sortPowerIndex').removeClass('active');
                table.order([[7, 'desc']]).draw();
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

            $('#loadTeamsBtn').on('click', loadTeamsForSelection);
            $('#generateFieldBtn').on('click', generatePlayoffFieldFromSelection);
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

            // Sort each league by league win % then Power Index
            Object.keys(currentLeagueTeams).forEach(league => {{
                currentLeagueTeams[league].sort((a, b) => {{
                    const aWinPct = a.league_wins / Math.max(1, a.league_wins + a.league_losses + a.league_ties);
                    const bWinPct = b.league_wins / Math.max(1, b.league_wins + b.league_losses + b.league_ties);
                    if (bWinPct !== aWinPct) return bWinPct - aWinPct;
                    return b.power_index - a.power_index;
                }});
            }});

            // Build selection UI
            let html = '';
            Object.keys(currentLeagueTeams).sort().forEach(league => {{
                const teams = currentLeagueTeams[league];
                html += `<div class="league-group">
                    <div class="league-group-header">${{league}} (${{teams.length}} teams)</div>`;

                teams.forEach((team, idx) => {{
                    const isTopTeam = idx === 0;
                    html += `
                        <div class="team-checkbox ${{isTopTeam ? 'selected' : ''}}">
                            <input type="checkbox" id="team_${{team.school_id}}" value="${{team.school_id}}"
                                ${{isTopTeam ? 'checked' : ''}} onchange="updateTeamSelection(this)">
                            <label for="team_${{team.school_id}}">
                                ${{team.school_name}}
                                <span class="team-stats">
                                    League: ${{team.league_record}} | Overall: ${{team.record}} | PI: ${{team.power_index.toFixed(4)}}
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

        function generatePlayoffFieldFromSelection() {{
            const bracketSize = parseInt($('#bracketSize').val());

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
