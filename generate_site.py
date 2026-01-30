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


def generate_html(rankings, school_data, raw_data_cache, school_info):
    """Generate the HTML dashboard with modern UI and playoff simulator."""

    years = sorted(set(r['year'] for r in rankings), reverse=True)
    genders = sorted(set(r['gender'] for r in rankings))
    classifications = sorted(set(r['classification'] for r in rankings if r['classification']))
    leagues = sorted(set(r['league'] for r in rankings if r['league']))

    # Calculate league power scores
    league_scores = calculate_league_power_scores(rankings)

    rankings_json = json.dumps(rankings)
    league_scores_json = json.dumps(league_scores)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Oregon HS Tennis Rankings</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.datatables.net/1.13.7/css/dataTables.bootstrap5.min.css" rel="stylesheet">
    <style>
        * {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }}
        body {{ background: #0f0f0f; color: #e5e5e5; font-size: 13px; }}
        .navbar {{ background: #1a1a1a; border-bottom: 1px solid #2a2a2a; padding: 0.5rem 1rem; }}
        .navbar-brand {{ font-weight: 700; font-size: 15px; color: #fff !important; }}
        .nav-tabs {{ border: none; gap: 4px; }}
        .nav-tabs .nav-link {{
            background: transparent; border: none; color: #888; font-size: 13px;
            font-weight: 500; padding: 6px 12px; border-radius: 6px;
        }}
        .nav-tabs .nav-link:hover {{ color: #fff; background: #2a2a2a; }}
        .nav-tabs .nav-link.active {{ background: #3b82f6; color: #fff; }}
        .toolbar {{
            background: #1a1a1a; border-bottom: 1px solid #2a2a2a;
            padding: 8px 16px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap;
        }}
        .toolbar select, .toolbar input {{
            background: #2a2a2a; border: 1px solid #3a3a3a; color: #e5e5e5;
            font-size: 12px; padding: 5px 10px; border-radius: 4px; min-width: 120px;
        }}
        .toolbar select:focus, .toolbar input:focus {{ outline: none; border-color: #3b82f6; }}
        .toolbar label {{ color: #888; font-size: 11px; font-weight: 500; text-transform: uppercase; margin-right: 4px; }}
        .filter-group {{ display: flex; align-items: center; gap: 4px; }}
        .table-container {{ padding: 0; }}
        table.dataTable {{ margin: 0 !important; }}
        table.dataTable thead th {{
            background: #1a1a1a; color: #888; font-size: 11px; font-weight: 600;
            text-transform: uppercase; letter-spacing: 0.5px; padding: 10px 12px;
            border-bottom: 1px solid #2a2a2a !important;
        }}
        table.dataTable tbody td {{
            padding: 8px 12px; border-bottom: 1px solid #1f1f1f !important;
            vertical-align: middle; color: #e5e5e5;
        }}
        table.dataTable tbody tr {{ background: #0f0f0f; }}
        table.dataTable tbody tr:hover {{ background: #1a1a1a; }}
        .rank-cell {{ font-weight: 600; color: #888; }}
        .rank-1 {{ color: #fbbf24 !important; }}
        .rank-2 {{ color: #94a3b8 !important; }}
        .rank-3 {{ color: #d97706 !important; }}
        .school-name {{ font-weight: 600; color: #fff; }}
        .apr-value {{ font-weight: 600; font-variant-numeric: tabular-nums; }}
        .apr-high {{ color: #22c55e; }}
        .apr-mid {{ color: #888; }}
        .apr-low {{ color: #ef4444; }}
        .pct-value {{ font-variant-numeric: tabular-nums; color: #888; }}
        .record {{ font-variant-numeric: tabular-nums; color: #888; }}
        .badge-class {{
            font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 3px;
        }}
        .badge-6a {{ background: #3b82f6; color: #fff; }}
        .badge-5a {{ background: #8b5cf6; color: #fff; }}
        .badge-4a {{ background: #22c55e; color: #fff; }}
        .badge-league {{
            font-size: 10px; font-weight: 500; padding: 2px 6px; border-radius: 3px;
            background: #2a2a2a; color: #888; cursor: help; position: relative;
        }}
        .badge-league:hover {{ background: #3a3a3a; }}
        .league-tooltip {{
            position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%);
            background: #1a1a1a; border: 1px solid #3a3a3a; border-radius: 4px;
            padding: 8px 12px; white-space: nowrap; z-index: 1000;
            font-size: 11px; color: #e5e5e5; display: none; margin-bottom: 4px;
        }}
        .badge-league:hover .league-tooltip {{ display: block; }}
        .tooltip-label {{ color: #666; }}
        .tooltip-value {{ color: #22c55e; font-weight: 600; }}
        .dataTables_wrapper .dataTables_length select {{ width: auto; }}
        .dataTables_wrapper .dataTables_filter {{ display: none; }}
        .dataTables_wrapper .dataTables_info {{ color: #666; font-size: 11px; }}
        .dataTables_wrapper .dataTables_paginate .paginate_button {{
            color: #888 !important; background: #1a1a1a !important; border: 1px solid #2a2a2a !important;
        }}
        .dataTables_wrapper .dataTables_paginate .paginate_button.current {{
            background: #3b82f6 !important; color: #fff !important; border-color: #3b82f6 !important;
        }}
        .dataTables_wrapper .dataTables_paginate .paginate_button:hover {{
            background: #2a2a2a !important; color: #fff !important;
        }}
        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}
        /* Playoff Simulator */
        .playoff-container {{ padding: 20px; }}
        .playoff-toolbar {{
            background: #1a1a1a; border-radius: 8px; padding: 16px;
            margin-bottom: 16px; display: flex; gap: 20px; align-items: flex-end; flex-wrap: wrap;
        }}
        .playoff-toolbar .form-group {{ display: flex; flex-direction: column; gap: 4px; }}
        .playoff-toolbar label {{ color: #888; font-size: 11px; font-weight: 600; text-transform: uppercase; }}
        .playoff-toolbar select, .playoff-toolbar input {{
            background: #2a2a2a; border: 1px solid #3a3a3a; color: #e5e5e5;
            padding: 8px 12px; border-radius: 4px; font-size: 13px;
        }}
        .playoff-toolbar button {{
            background: #3b82f6; color: #fff; border: none; padding: 8px 16px;
            border-radius: 4px; font-weight: 600; cursor: pointer;
        }}
        .playoff-toolbar button:hover {{ background: #2563eb; }}
        .field-list {{ background: #1a1a1a; border-radius: 8px; overflow: hidden; }}
        .field-header {{
            padding: 12px 16px; background: #2a2a2a; font-weight: 600;
            display: flex; justify-content: space-between;
        }}
        .field-team {{
            display: flex; align-items: center; padding: 10px 16px;
            border-bottom: 1px solid #2a2a2a; gap: 12px;
        }}
        .field-team:last-child {{ border-bottom: none; }}
        .field-seed {{ width: 24px; font-weight: 700; color: #3b82f6; }}
        .field-name {{ flex: 1; font-weight: 500; }}
        .field-apr {{ width: 60px; font-variant-numeric: tabular-nums; color: #22c55e; }}
        .field-league {{ font-size: 11px; color: #888; }}
        .field-badge {{
            font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 3px;
        }}
        .badge-autobid {{ background: #22c55e; color: #fff; }}
        .badge-atlarge {{ background: #8b5cf6; color: #fff; }}
        .badge-bye {{ background: #fbbf24; color: #000; margin-left: 8px; }}
        .section-title {{ color: #888; font-size: 11px; font-weight: 600; text-transform: uppercase; margin: 16px 0 8px; }}
        /* League Analysis */
        .analysis-container {{ padding: 20px; }}
        .analysis-toolbar {{
            background: #1a1a1a; border-radius: 8px; padding: 16px;
            margin-bottom: 16px; display: flex; gap: 20px; align-items: flex-end; flex-wrap: wrap;
        }}
        .analysis-table {{ width: 100%; }}
        .analysis-table th {{ text-align: left; }}
        footer {{
            margin-top: 40px; padding: 16px; background: #0a0a0a;
            border-top: 1px solid #1a1a1a; text-align: center;
        }}
        footer a {{ color: #444; font-size: 11px; text-decoration: none; }}
        footer a:hover {{ color: #666; }}
    </style>
</head>
<body>
    <nav class="navbar">
        <span class="navbar-brand">Oregon HS Tennis Rankings</span>
        <ul class="nav nav-tabs ms-4" id="mainTabs">
            <li class="nav-item">
                <a class="nav-link active" href="#" data-tab="rankings">Rankings</a>
            </li>
            <li class="nav-item">
                <a class="nav-link" href="#" data-tab="playoffs">Playoff Simulator</a>
            </li>
            <li class="nav-item" id="analysisNavItem" style="display:none;">
                <a class="nav-link" href="#" data-tab="analysis">League Analysis</a>
            </li>
        </ul>
    </nav>

    <!-- Rankings Tab -->
    <div id="rankings-tab" class="tab-content active">
        <div class="toolbar">
            <div class="filter-group">
                <label>Year</label>
                <select id="yearFilter">
                    {chr(10).join(f'<option value="{y}">{y}</option>' for y in years)}
                </select>
            </div>
            <div class="filter-group">
                <label>Gender</label>
                <select id="genderFilter">
                    {chr(10).join(f'<option value="{g}">{g}</option>' for g in genders)}
                </select>
            </div>
            <div class="filter-group">
                <label>Class</label>
                <select id="classFilter">
                    <option value="">All</option>
                    {chr(10).join(f'<option value="{c}">{c}</option>' for c in classifications)}
                </select>
            </div>
            <div class="filter-group">
                <label>League</label>
                <select id="leagueFilter">
                    <option value="">All</option>
                    {chr(10).join(f'<option value="{l}">{l}</option>' for l in leagues)}
                </select>
            </div>
            <div class="filter-group" style="flex:1; max-width: 200px;">
                <label>Search</label>
                <input type="text" id="searchBox" placeholder="School name...">
            </div>
            <div class="filter-group">
                <label>Min Matches</label>
                <input type="number" id="minMatchesFilter" value="3" min="0" max="20" style="width:60px;">
            </div>
        </div>

        <div class="table-container">
            <table id="rankingsTable" class="table" style="width:100%">
                <thead>
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
                    <select id="playoffYear">
                        {chr(10).join(f'<option value="{y}">{y}</option>' for y in years)}
                    </select>
                </div>
                <div class="form-group">
                    <label>Gender</label>
                    <select id="playoffGender">
                        {chr(10).join(f'<option value="{g}">{g}</option>' for g in genders)}
                    </select>
                </div>
                <div class="form-group">
                    <label>Classification</label>
                    <select id="playoffClass">
                        {chr(10).join(f'<option value="{c}">{c}</option>' for c in classifications)}
                    </select>
                </div>
                <div class="form-group">
                    <label>Bracket Size</label>
                    <select id="bracketSize">
                        <option value="8">8 Teams</option>
                        <option value="12" selected>12 Teams</option>
                        <option value="16">16 Teams</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Auto-Bids/League</label>
                    <input type="number" id="autoBids" value="1" min="0" max="4" style="width:70px;">
                </div>
                <div class="form-group">
                    <label>Min Matches</label>
                    <input type="number" id="playoffMinMatches" value="3" min="0" max="20" style="width:70px;">
                </div>
                <button id="simulateBtn">Generate Field</button>
            </div>

            <div id="playoffResults"></div>
        </div>
    </div>

    <!-- League Analysis Tab (Hidden) -->
    <div id="analysis-tab" class="tab-content">
        <div class="analysis-container">
            <div class="analysis-toolbar">
                <div class="form-group">
                    <label>Year</label>
                    <select id="analysisYear">
                        {chr(10).join(f'<option value="{y}">{y}</option>' for y in years)}
                    </select>
                </div>
                <div class="form-group">
                    <label>Gender</label>
                    <select id="analysisGender">
                        {chr(10).join(f'<option value="{g}">{g}</option>' for g in genders)}
                    </select>
                </div>
                <button id="refreshAnalysis">Refresh</button>
            </div>
            <div class="table-container">
                <table id="analysisTable" class="table analysis-table" style="width:100%">
                    <thead>
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
        let table;
        let analysisTable;

        // Build league score lookup for tooltips
        const leagueScoreLookup = {{}};
        leagueScores.forEach(ls => {{
            const key = `${{ls.year}}-${{ls.gender}}-${{ls.league}}`;
            leagueScoreLookup[key] = ls;
        }});

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
                if (tab.dataset.tab === 'analysis') {{
                    refreshAnalysisTable();
                }}
            }});
        }});

        // Admin link behavior
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
                        render: (d, t, r) => {{
                            if (t !== 'display') return d;
                            let cls = 'rank-cell';
                            if (d === 1) cls += ' rank-1';
                            else if (d === 2) cls += ' rank-2';
                            else if (d === 3) cls += ' rank-3';
                            return `<span class="${{cls}}">${{d}}</span>`;
                        }}
                    }},
                    {{
                        data: 'school_name',
                        render: (d) => `<span class="school-name">${{d}}</span>`
                    }},
                    {{
                        data: 'classification',
                        render: (d, t) => {{
                            if (t !== 'display' || !d) return d || '-';
                            let cls = 'badge-class ';
                            if (d === '6A') cls += 'badge-6a';
                            else if (d === '5A') cls += 'badge-5a';
                            else cls += 'badge-4a';
                            return `<span class="${{cls}}">${{d}}</span>`;
                        }}
                    }},
                    {{
                        data: 'league',
                        render: (d, t, row) => {{
                            if (t !== 'display') return d || '';
                            if (!d) return '-';
                            const key = `${{row.year}}-${{row.gender}}-${{d}}`;
                            const ls = leagueScoreLookup[key];
                            const tooltip = ls ?
                                `<span class="league-tooltip">
                                    <span class="tooltip-label">Power Score:</span> <span class="tooltip-value">${{ls.avg_apr.toFixed(4)}}</span><br>
                                    <span class="tooltip-label">Top 4 Depth:</span> <span class="tooltip-value">${{ls.depth_score.toFixed(4)}}</span>
                                </span>` : '';
                            return `<span class="badge-league">${{d}}${{tooltip}}</span>`;
                        }}
                    }},
                    {{ data: 'record', className: 'record' }},
                    {{ data: 'league_record', className: 'record' }},
                    {{
                        data: 'apr',
                        render: (d, t) => {{
                            if (t !== 'display') return d;
                            let cls = 'apr-value ';
                            if (d >= 0.55) cls += 'apr-high';
                            else if (d < 0.40) cls += 'apr-low';
                            else cls += 'apr-mid';
                            return `<span class="${{cls}}">${{d.toFixed(4)}}</span>`;
                        }}
                    }},
                    {{
                        data: 'wwp',
                        render: (d, t) => t === 'display' ? `<span class="pct-value">${{d >= 1 ? '1.000' : d.toFixed(3).substring(1)}}</span>` : d
                    }},
                    {{
                        data: 'owp',
                        render: (d, t) => t === 'display' ? `<span class="pct-value">${{d >= 1 ? '1.000' : d.toFixed(3).substring(1)}}</span>` : d
                    }}
                ],
                order: [[6, 'desc']],
                pageLength: 50,
                lengthMenu: [[25, 50, 100, -1], [25, 50, 100, "All"]],
                dom: 'lrtip'
            }});

            // Custom filtering
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

                // Minimum matches filter (wins + losses + ties)
                const totalMatches = row.wins + row.losses + row.ties;
                if (totalMatches < minMatches) return false;

                return true;
            }});

            $('#yearFilter, #genderFilter, #classFilter, #leagueFilter, #minMatchesFilter').on('change', () => table.draw());
            $('#searchBox').on('keyup', function() {{ table.search(this.value).draw(); }});

            // Set defaults
            $('#yearFilter').val('{years[0]}');
            table.draw();

            // Playoff Simulator
            $('#simulateBtn').on('click', generatePlayoffField);
        }});

        function generatePlayoffField() {{
            const year = parseInt($('#playoffYear').val());
            const gender = $('#playoffGender').val();
            const classification = $('#playoffClass').val();
            const bracketSize = parseInt($('#bracketSize').val());
            const autoBidsPerLeague = parseInt($('#autoBids').val());
            const minMatches = parseInt($('#playoffMinMatches').val()) || 0;

            // Filter teams for this year/gender/classification with minimum matches
            let teams = rankings.filter(r =>
                r.year === year &&
                r.gender === gender &&
                r.classification === classification &&
                (r.wins + r.losses + r.ties) >= minMatches
            );

            if (teams.length === 0) {{
                $('#playoffResults').html('<p style="padding:20px;color:#888;">No teams found for selected criteria (check min matches setting).</p>');
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

            // Sort each league by: league_wins desc, then tiebreakers
            Object.keys(leagueTeams).forEach(league => {{
                leagueTeams[league].sort((a, b) => {{
                    // Primary: League wins (desc)
                    const aLeagueWinPct = a.league_wins / Math.max(1, a.league_wins + a.league_losses + a.league_ties);
                    const bLeagueWinPct = b.league_wins / Math.max(1, b.league_wins + b.league_losses + b.league_ties);
                    if (bLeagueWinPct !== aLeagueWinPct) return bLeagueWinPct - aLeagueWinPct;
                    // Tiebreaker: APR
                    return b.apr - a.apr;
                }});
            }});

            // Select auto-bids from each league
            const autoBidTeams = [];
            const autoBidIds = new Set();

            Object.keys(leagueTeams).forEach(league => {{
                const leagueList = leagueTeams[league];
                for (let i = 0; i < Math.min(autoBidsPerLeague, leagueList.length); i++) {{
                    autoBidTeams.push({{ ...leagueList[i], qualifyType: 'auto' }});
                    autoBidIds.add(leagueList[i].school_id);
                }}
            }});

            // Fill remaining spots with at-large (highest APR not already in)
            const remainingSpots = bracketSize - autoBidTeams.length;
            const atLargeTeams = teams
                .filter(t => !autoBidIds.has(t.school_id))
                .sort((a, b) => b.apr - a.apr)
                .slice(0, Math.max(0, remainingSpots))
                .map(t => ({{ ...t, qualifyType: 'atlarge' }}));

            // Combine and sort by APR for seeding
            const field = [...autoBidTeams, ...atLargeTeams].sort((a, b) => b.apr - a.apr);

            // Render
            let html = `
                <div class="section-title">Qualifying Field (${{field.length}} Teams)</div>
                <div class="field-list">
                    <div class="field-header">
                        <span>Seed / Team</span>
                        <span>APR</span>
                    </div>
            `;

            field.forEach((team, idx) => {{
                const seed = idx + 1;
                const hasBye = bracketSize === 12 && seed <= 4;
                html += `
                    <div class="field-team">
                        <span class="field-seed">${{seed}}</span>
                        <span class="field-name">${{team.school_name}}</span>
                        <span class="field-badge ${{team.qualifyType === 'auto' ? 'badge-autobid' : 'badge-atlarge'}}">
                            ${{team.qualifyType === 'auto' ? 'AUTO' : 'AT-LARGE'}}
                        </span>
                        ${{hasBye ? '<span class="field-badge badge-bye">FIRST ROUND BYE</span>' : ''}}
                        <span class="field-league">${{team.league || '-'}}</span>
                        <span class="field-apr">${{team.apr.toFixed(4)}}</span>
                    </div>
                `;
            }});

            html += '</div>';

            // Summary
            const autoCount = field.filter(t => t.qualifyType === 'auto').length;
            const atLargeCount = field.filter(t => t.qualifyType === 'atlarge').length;
            html += `
                <div class="section-title" style="margin-top:20px;">Summary</div>
                <div style="background:#1a1a1a;padding:12px 16px;border-radius:8px;color:#888;">
                    <strong style="color:#fff;">${{field.length}}</strong> teams qualify &bull;
                    <strong style="color:#22c55e;">${{autoCount}}</strong> auto-bids &bull;
                    <strong style="color:#8b5cf6;">${{atLargeCount}}</strong> at-large
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
                const row = `
                    <tr>
                        <td class="rank-cell">${{idx + 1}}</td>
                        <td><span class="badge-league">${{ls.league}}</span></td>
                        <td>${{ls.classification || '-'}}</td>
                        <td class="apr-value apr-high">${{ls.avg_apr.toFixed(4)}}</td>
                        <td class="apr-value">${{ls.depth_score.toFixed(4)}}</td>
                        <td>${{ls.num_schools}}</td>
                        <td class="school-name">${{ls.top_team}}</td>
                    </tr>
                `;
                tbody.append(row);
            }});
        }}

        $('#refreshAnalysis').on('click', refreshAnalysisTable);
        $('#analysisYear, #analysisGender').on('change', refreshAnalysisTable);
    </script>
</body>
</html>'''

    return html


def main():
    script_dir = Path(__file__).parent
    repo_root = script_dir

    data_dir = repo_root / 'data'
    master_school_list = repo_root / 'master_school_list.csv'
    output_file = repo_root / 'index.html'
    json_output = repo_root / 'public' / 'data' / 'processed_rankings.json'

    json_output.parent.mkdir(parents=True, exist_ok=True)

    print("Building rankings...")
    rankings, school_data, raw_data_cache, school_info = build_rankings(data_dir, master_school_list)

    # Save JSON
    with open(json_output, 'w') as f:
        json.dump(rankings, f, indent=2)
    print(f"JSON saved to {json_output}")

    print("Generating HTML dashboard...")
    html = generate_html(rankings, school_data, raw_data_cache, school_info)

    with open(output_file, 'w') as f:
        f.write(html)

    print(f"Dashboard saved to {output_file}")
    print(f"Total rankings: {len(rankings)}")


if __name__ == '__main__':
    main()
