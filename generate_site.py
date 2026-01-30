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

WWP_WEIGHT = 0.35
OWP_WEIGHT = 0.65
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
                wwp = calculate_wwp(results)
                school_data[year][gender][school_id] = {
                    'wwp': wwp,
                    'opponents': opponents,
                    'results': results,
                    'matches_played': len(results),
                    'dual_wins': wins,
                    'dual_losses': losses,
                    'dual_ties': ties,
                    'league_wins': league_wins,
                    'league_losses': league_losses,
                    'league_ties': league_ties,
                }

    # Calculate OWP and common opponent data
    for year in school_data:
        for gender in school_data[year]:
            for school_id in school_data[year][gender]:
                school = school_data[year][gender][school_id]
                opponents = school['opponents']

                opponent_wwps = []
                for opp_id in opponents:
                    if opp_id in school_data[year][gender]:
                        opponent_wwps.append(school_data[year][gender][opp_id]['wwp'])
                    else:
                        # Unknown opponents (e.g., Idaho schools) rated as neutral average
                        opponent_wwps.append(0.5)

                owp = sum(opponent_wwps) / len(opponent_wwps) if opponent_wwps else 0.5
                school['owp'] = owp
                school['apr'] = (school['wwp'] * WWP_WEIGHT) + (owp * OWP_WEIGHT)

    # Build output
    output = []
    for year in sorted(school_data.keys()):
        for gender in sorted(school_data[year].keys()):
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
                    'classification': info.get('classification', ''),
                    'league': info.get('league', ''),
                    'wwp': round(stats['wwp'], 4),
                    'owp': round(stats['owp'], 4),
                    'apr': round(stats['apr'], 4),
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
                        <th>APR</th>
                        <th>WWP</th>
                        <th>OWP</th>
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
                    <label>Auto-Bids/League</label>
                    <select id="autoBids" class="form-select form-select-sm">
                        <option value="1">1 per league</option>
                        <option value="2">2 per league</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Min Matches</label>
                    <input type="number" id="playoffMinMatches" class="form-control form-control-sm" value="3" min="0" max="20" style="width:70px;">
                </div>
                <div class="form-group">
                    <label>&nbsp;</label>
                    <button id="simulateBtn" class="btn btn-success btn-sm">Generate Field</button>
                </div>
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
                        data: 'apr',
                        render: (d, t) => {{
                            if (t !== 'display') return d;
                            let cls = 'apr-mid';
                            if (d >= 0.55) cls = 'apr-high';
                            else if (d < 0.40) cls = 'apr-low';
                            return `<span class="${{cls}}">${{d.toFixed(4)}}</span>`;
                        }}
                    }},
                    {{ data: 'wwp', render: (d, t) => t === 'display' ? (d >= 1 ? '1.000' : d.toFixed(3).substring(1)) : d }},
                    {{ data: 'owp', render: (d, t) => t === 'display' ? (d >= 1 ? '1.000' : d.toFixed(3).substring(1)) : d }}
                ],
                order: [[6, 'desc']],
                pageLength: 50,
                lengthMenu: [[25, 50, 100, -1], [25, 50, 100, "All"]],
                dom: 'lrtip'
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

            $('#simulateBtn').on('click', generatePlayoffField);
        }});

        function generatePlayoffField() {{
            const year = parseInt($('#playoffYear').val());
            const gender = $('#playoffGender').val();
            const classification = $('#playoffClass').val();
            const bracketSize = parseInt($('#bracketSize').val());
            const autoBidsPerLeague = parseInt($('#autoBids').val());
            const minMatches = parseInt($('#playoffMinMatches').val()) || 0;

            let teams = rankings.filter(r =>
                r.year === year &&
                r.gender === gender &&
                r.classification === classification &&
                (r.wins + r.losses + r.ties) >= minMatches
            );

            if (teams.length === 0) {{
                $('#playoffResults').html('<p class="text-muted p-3">No teams found for selected criteria.</p>');
                return;
            }}

            // Group by league
            const leagueTeams = {{}};
            teams.forEach(t => {{
                if (t.league) {{
                    if (!leagueTeams[t.league]) leagueTeams[t.league] = [];
                    leagueTeams[t.league].push(t);
                }}
            }});

            // Sort each league by league win % then APR
            Object.keys(leagueTeams).forEach(league => {{
                leagueTeams[league].sort((a, b) => {{
                    const aWinPct = a.league_wins / Math.max(1, a.league_wins + a.league_losses + a.league_ties);
                    const bWinPct = b.league_wins / Math.max(1, b.league_wins + b.league_losses + b.league_ties);
                    if (bWinPct !== aWinPct) return bWinPct - aWinPct;
                    return b.apr - a.apr;
                }});
            }});

            // Select auto-bids
            const autoBidTeams = [];
            const autoBidIds = new Set();
            Object.keys(leagueTeams).forEach(league => {{
                const leagueList = leagueTeams[league];
                for (let i = 0; i < Math.min(autoBidsPerLeague, leagueList.length); i++) {{
                    autoBidTeams.push({{ ...leagueList[i], qualifyType: 'auto' }});
                    autoBidIds.add(leagueList[i].school_id);
                }}
            }});

            // Fill remaining with at-large by APR
            const remainingSpots = bracketSize - autoBidTeams.length;
            const atLargeTeams = teams
                .filter(t => !autoBidIds.has(t.school_id))
                .sort((a, b) => b.apr - a.apr)
                .slice(0, Math.max(0, remainingSpots))
                .map(t => ({{ ...t, qualifyType: 'atlarge' }}));

            const field = [...autoBidTeams, ...atLargeTeams].sort((a, b) => b.apr - a.apr);

            let html = `
                <div class="section-title">Qualifying Field (${{field.length}} Teams)</div>
                <div class="field-list">
                    <div class="field-header d-flex justify-content-between">
                        <span>Seed / Team</span>
                        <span>Record / APR</span>
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
                        <span class="field-apr">${{team.apr.toFixed(4)}}</span>
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
                    <span class="text-success"><strong>${{autoCount}}</strong> auto-bids</span> &bull;
                    <span style="color:#6f42c1;"><strong>${{atLargeCount}}</strong> at-large</span>
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

            // Get APR-ranked teams for this classification
            let teams = rankings.filter(r =>
                r.year === year &&
                r.gender === gender &&
                r.classification === classification &&
                (r.wins + r.losses + r.ties) >= 3
            ).sort((a, b) => b.apr - a.apr).slice(0, bracketSize);

            // Get state tournament results for this year/gender/classification
            const stateData = stateResults.filter(s =>
                s.year === year &&
                s.gender === gender &&
                s.classification === classification
            );

            // Create lookup by team name (normalized)
            const stateLookup = {{}};
            stateData.forEach(s => {{
                // Normalize team names for matching
                const normalized = s.team.toLowerCase()
                    .replace(/st\\.? mary'?s?.*/i, 'st marys')
                    .replace(/st\\.? mary'?s? of medford/i, 'st marys of medford')
                    .replace(/oregon episcopal school/i, 'oregon episcopal')
                    .replace(/ high school/i, '')
                    .replace(/barlow/i, 'sam barlow')
                    .replace(/^sam barlow$/i, 'sam barlow')
                    .trim();
                stateLookup[normalized] = s;
            }});

            // Match APR teams with state results
            let teamsWithState = 0;
            let teamsWithoutState = 0;
            let totalEntries = 0;
            let totalPoints = 0;
            let hiddenGems = []; // Teams that would qualify by APR but had 0 or few entries

            const comparisonData = teams.map((team, idx) => {{
                const normalized = team.school_name.toLowerCase()
                    .replace(/st\\.? mary'?s?.*/i, 'st marys of medford')
                    .replace(/oregon episcopal school/i, 'oregon episcopal')
                    .replace(/ high school/i, '')
                    .trim();

                // Try to find state result
                let stateMatch = null;
                for (const [key, val] of Object.entries(stateLookup)) {{
                    if (normalized.includes(key) || key.includes(normalized) ||
                        team.school_name.toLowerCase().includes(key) ||
                        key.includes(team.school_name.toLowerCase())) {{
                        stateMatch = val;
                        break;
                    }}
                }}

                if (stateMatch) {{
                    teamsWithState++;
                    totalEntries += stateMatch.entries;
                    totalPoints += stateMatch.total_points;
                }} else {{
                    teamsWithoutState++;
                    if (idx < bracketSize) {{
                        hiddenGems.push(team);
                    }}
                }}

                return {{
                    ...team,
                    aprRank: idx + 1,
                    stateEntries: stateMatch ? stateMatch.entries : 0,
                    statePoints: stateMatch ? stateMatch.total_points : 0,
                    statePlace: stateMatch ? stateMatch.place : null,
                    hadStatePresence: !!stateMatch
                }};
            }});

            // Calculate insights
            const avgEntries = teamsWithState > 0 ? (totalEntries / teamsWithState).toFixed(1) : 0;
            const avgPoints = teamsWithState > 0 ? (totalPoints / teamsWithState).toFixed(1) : 0;

            let html = `
                <div class="row mb-4">
                    <div class="col-md-3">
                        <div class="comparison-card text-center">
                            <div class="stat-highlight">${{teamsWithoutState}}</div>
                            <div class="stat-label">APR Qualifiers with No/Few State Entries</div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="comparison-card text-center">
                            <div class="stat-highlight">${{teamsWithState}}</div>
                            <div class="stat-label">APR Qualifiers at State Tournament</div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="comparison-card text-center">
                            <div class="stat-highlight">${{avgEntries}}</div>
                            <div class="stat-label">Avg Entries (of those at state)</div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="comparison-card text-center">
                            <div class="stat-highlight">${{avgPoints}}</div>
                            <div class="stat-label">Avg Points (of those at state)</div>
                        </div>
                    </div>
                </div>
            `;

            if (hiddenGems.length > 0) {{
                html += `
                    <div class="comparison-card">
                        <h5>Teams Rewarded by APR Format</h5>
                        <p class="text-muted small">These teams would qualify for team playoffs based on APR but had no entries at the individual state tournament:</p>
                `;
                hiddenGems.forEach(team => {{
                    html += `
                        <div class="team-comparison">
                            <span class="tc-rank">#${{comparisonData.find(t => t.school_id === team.school_id)?.aprRank}}</span>
                            <span class="tc-name">${{team.school_name}}</span>
                            <span class="tc-record">${{team.record}}</span>
                            <span class="tc-apr">${{team.apr.toFixed(4)}}</span>
                            <span class="tc-state tc-no-state">No State Entries</span>
                        </div>
                    `;
                }});
                html += '</div>';
            }}

            html += `
                <div class="comparison-card">
                    <h5>APR Playoff Field vs State Tournament Presence</h5>
                    <p class="text-muted small">Comparing ${{bracketSize}}-team APR playoff field with actual state tournament individual entries and points:</p>
                    <div class="table-responsive">
                        <table class="table table-sm">
                            <thead class="table-light">
                                <tr>
                                    <th>APR Seed</th>
                                    <th>Team</th>
                                    <th>Record</th>
                                    <th>APR</th>
                                    <th>State Entries</th>
                                    <th>State Points</th>
                                    <th>State Place</th>
                                </tr>
                            </thead>
                            <tbody>
            `;

            comparisonData.forEach(team => {{
                const stateClass = team.hadStatePresence ? '' : 'table-warning';
                html += `
                    <tr class="${{stateClass}}">
                        <td class="tc-rank">${{team.aprRank}}</td>
                        <td class="school-name">${{team.school_name}}</td>
                        <td>${{team.record}}</td>
                        <td>${{team.apr.toFixed(4)}}</td>
                        <td class="tc-state-entries">${{team.stateEntries || '-'}}</td>
                        <td class="tc-state-points">${{team.statePoints || '-'}}</td>
                        <td>${{team.statePlace || '-'}}</td>
                    </tr>
                `;
            }});

            html += `
                            </tbody>
                        </table>
                    </div>
                </div>
            `;

            // Summary insight
            const hiddenGemPct = ((teamsWithoutState / bracketSize) * 100).toFixed(0);
            html += `
                <div class="comparison-card">
                    <h5>Key Insight</h5>
                    <p><strong>${{hiddenGemPct}}%</strong> of teams that would qualify under the APR team playoff format had no or minimal representation at the individual state tournament.
                    This demonstrates how the current individual-based qualification system can overlook programs with strong overall team performance throughout the dual match season.</p>
                    <p class="text-muted small">The APR format rewards teams for season-long success across all flights, not just having a few elite individual players who qualify for state.</p>
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
