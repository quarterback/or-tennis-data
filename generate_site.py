#!/usr/bin/env python3
"""
Generate a static HTML dashboard for Oregon high school tennis rankings.

Creates a single index.html file with:
- Bootstrap for styling
- DataTables for sortable, searchable tables
- Dropdown filters for Year, Gender, and Classification
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
    """Get the dual match win-loss record for a school."""
    wins = 0
    losses = 0

    for meet in meets:
        if not is_dual_match(meet):
            continue

        schools = meet.get('schools', {})
        winners = schools.get('winners', [])
        losers = schools.get('losers', [])

        for w in winners:
            if w['id'] == school_id:
                wins += 1
                break
        for l in losers:
            if l['id'] == school_id:
                losses += 1
                break

    return wins, losses


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

    data_path = Path(data_dir)

    for year_dir in sorted(data_path.iterdir()):
        if not year_dir.is_dir():
            continue

        year = year_dir.name
        if not year.isdigit():
            continue

        if int(year) < 2022 or int(year) > 2025:
            continue

        print(f"Processing year {year}...")

        for json_file in year_dir.glob('school_*_gender_*.json'):
            parts = json_file.stem.split('_')
            school_id = int(parts[1])
            gender_id = int(parts[3])
            gender = GENDER_MAP.get(gender_id, 'Unknown')

            with open(json_file, 'r') as f:
                data = json.load(f)

            results, opponents = process_school_data(data, school_id)
            wins, losses = get_dual_match_record(data.get('meets', []), school_id)

            if results:
                wwp = calculate_wwp(results)
                school_data[year][gender][school_id] = {
                    'wwp': wwp,
                    'opponents': opponents,
                    'results': results,
                    'matches_played': len(results),
                    'weighted_wins': sum(r[4] for r in results if r[3]),
                    'weighted_total': sum(r[4] for r in results),
                    'dual_wins': wins,
                    'dual_losses': losses,
                }

    # Calculate OWP
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
                    'city': info.get('city', ''),
                    'classification': info.get('classification', ''),
                    'league': info.get('league', ''),
                    'wwp': round(stats['wwp'], 4),
                    'owp': round(stats['owp'], 4),
                    'apr': round(stats['apr'], 4),
                    'matches_played': stats['matches_played'],
                    'opponents_count': len(stats['opponents']),
                    'record': f"{stats['dual_wins']}-{stats['dual_losses']}",
                })

    return output


def generate_html(rankings):
    """Generate the HTML dashboard."""

    # Get unique values for filters
    years = sorted(set(r['year'] for r in rankings), reverse=True)
    genders = sorted(set(r['gender'] for r in rankings))
    classifications = sorted(set(r['classification'] for r in rankings if r['classification']))

    # Convert rankings to JSON for JavaScript
    rankings_json = json.dumps(rankings)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Oregon High School Tennis Rankings</title>

    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">

    <!-- DataTables CSS -->
    <link href="https://cdn.datatables.net/1.13.7/css/dataTables.bootstrap5.min.css" rel="stylesheet">

    <style>
        body {{
            background-color: #f8f9fa;
        }}
        .header {{
            background: linear-gradient(135deg, #1a5f2a 0%, #2d8f4e 100%);
            color: white;
            padding: 2rem 0;
            margin-bottom: 2rem;
        }}
        .header h1 {{
            font-weight: 700;
            margin-bottom: 0.5rem;
        }}
        .header p {{
            opacity: 0.9;
            margin-bottom: 0;
        }}
        .filter-section {{
            background: white;
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .table-container {{
            background: white;
            border-radius: 8px;
            padding: 1.5rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .rank-1 {{ color: #ffd700; font-weight: bold; }}
        .rank-2 {{ color: #c0c0c0; font-weight: bold; }}
        .rank-3 {{ color: #cd7f32; font-weight: bold; }}
        .apr-high {{ color: #28a745; font-weight: 600; }}
        .apr-mid {{ color: #6c757d; }}
        .apr-low {{ color: #dc3545; }}
        .badge-6a {{ background-color: #0d6efd; }}
        .badge-5a {{ background-color: #6610f2; }}
        .badge-4a {{ background-color: #198754; }}
        .stat-card {{
            text-align: center;
            padding: 1rem;
            border-radius: 8px;
            background: #f8f9fa;
        }}
        .stat-card .value {{
            font-size: 2rem;
            font-weight: 700;
            color: #1a5f2a;
        }}
        .stat-card .label {{
            color: #6c757d;
            font-size: 0.875rem;
        }}
        footer {{
            margin-top: 3rem;
            padding: 2rem 0;
            background: #343a40;
            color: #adb5bd;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="container">
            <h1>Oregon High School Tennis Rankings</h1>
            <p>Power rankings based on weighted individual match results (APR System)</p>
        </div>
    </div>

    <div class="container">
        <!-- Stats Row -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="stat-card">
                    <div class="value">{len(set(r['school_id'] for r in rankings))}</div>
                    <div class="label">Schools Ranked</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-card">
                    <div class="value">{len(years)}</div>
                    <div class="label">Years of Data</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-card">
                    <div class="value">{sum(r['matches_played'] for r in rankings):,}</div>
                    <div class="label">Individual Matches</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-card">
                    <div class="value">{len(rankings)}</div>
                    <div class="label">Total Rankings</div>
                </div>
            </div>
        </div>

        <!-- Filter Section -->
        <div class="filter-section">
            <div class="row g-3">
                <div class="col-md-3">
                    <label for="yearFilter" class="form-label">Year</label>
                    <select id="yearFilter" class="form-select">
                        <option value="">All Years</option>
                        {chr(10).join(f'<option value="{y}">{y}</option>' for y in years)}
                    </select>
                </div>
                <div class="col-md-3">
                    <label for="genderFilter" class="form-label">Gender</label>
                    <select id="genderFilter" class="form-select">
                        <option value="">All</option>
                        {chr(10).join(f'<option value="{g}">{g}</option>' for g in genders)}
                    </select>
                </div>
                <div class="col-md-3">
                    <label for="classFilter" class="form-label">Classification</label>
                    <select id="classFilter" class="form-select">
                        <option value="">All Classifications</option>
                        {chr(10).join(f'<option value="{c}">{c}</option>' for c in classifications)}
                    </select>
                </div>
                <div class="col-md-3">
                    <label for="searchBox" class="form-label">Search School</label>
                    <input type="text" id="searchBox" class="form-control" placeholder="Type to search...">
                </div>
            </div>
        </div>

        <!-- Table Section -->
        <div class="table-container">
            <table id="rankingsTable" class="table table-striped table-hover" style="width:100%">
                <thead class="table-dark">
                    <tr>
                        <th>Rank</th>
                        <th>School</th>
                        <th>City</th>
                        <th>Classification</th>
                        <th>Record</th>
                        <th>APR</th>
                        <th>WWP</th>
                        <th>OWP</th>
                        <th>Year</th>
                        <th>Gender</th>
                    </tr>
                </thead>
                <tbody>
                </tbody>
            </table>
        </div>

        <!-- Formula Explanation -->
        <div class="mt-4 p-4 bg-light rounded">
            <h5>About the APR (Adjusted Power Rating) System</h5>
            <p class="mb-2">Rankings are calculated using weighted individual match results from dual matches only (no tournaments).</p>
            <div class="row">
                <div class="col-md-6">
                    <strong>Flight Weights:</strong>
                    <ul class="mb-0">
                        <li>1 Singles / 1 Doubles: 1.00</li>
                        <li>2 Singles: 0.75</li>
                        <li>2 Doubles: 0.50</li>
                        <li>3 Singles / 3 Doubles: 0.25</li>
                        <li>4 Singles / 4 Doubles: 0.10</li>
                    </ul>
                </div>
                <div class="col-md-6">
                    <strong>Formula:</strong>
                    <ul class="mb-0">
                        <li><strong>WWP</strong> = Weighted Wins / Total Weighted Matches</li>
                        <li><strong>OWP</strong> = Average WWP of Opponents</li>
                        <li><strong>APR</strong> = (WWP &times; 0.35) + (OWP &times; 0.65)</li>
                    </ul>
                </div>
            </div>
        </div>
    </div>

    <footer>
        <div class="container text-center">
            <p class="mb-0">Oregon High School Tennis Rankings &bull; Data from TennisReporting.com</p>
        </div>
    </footer>

    <!-- jQuery -->
    <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>

    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>

    <!-- DataTables JS -->
    <script src="https://cdn.datatables.net/1.13.7/js/jquery.dataTables.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.7/js/dataTables.bootstrap5.min.js"></script>

    <script>
        // Rankings data
        const rankings = {rankings_json};

        // Initialize DataTable
        let table;

        $(document).ready(function() {{
            table = $('#rankingsTable').DataTable({{
                data: rankings,
                columns: [
                    {{
                        data: 'rank',
                        render: function(data, type, row) {{
                            if (type === 'display') {{
                                if (data === 1) return '<span class="rank-1">#1</span>';
                                if (data === 2) return '<span class="rank-2">#2</span>';
                                if (data === 3) return '<span class="rank-3">#3</span>';
                                return '#' + data;
                            }}
                            return data;
                        }}
                    }},
                    {{ data: 'school_name' }},
                    {{ data: 'city' }},
                    {{
                        data: 'classification',
                        render: function(data, type, row) {{
                            if (type === 'display' && data) {{
                                let badgeClass = 'bg-secondary';
                                if (data === '6A') badgeClass = 'badge-6a';
                                else if (data === '5A') badgeClass = 'badge-5a';
                                else if (data.includes('4A')) badgeClass = 'badge-4a';
                                return '<span class="badge ' + badgeClass + '">' + data + '</span>';
                            }}
                            return data || '-';
                        }}
                    }},
                    {{ data: 'record' }},
                    {{
                        data: 'apr',
                        render: function(data, type, row) {{
                            if (type === 'display') {{
                                let colorClass = 'apr-mid';
                                if (data >= 0.6) colorClass = 'apr-high';
                                else if (data < 0.4) colorClass = 'apr-low';
                                return '<span class="' + colorClass + '">' + data.toFixed(4) + '</span>';
                            }}
                            return data;
                        }}
                    }},
                    {{
                        data: 'wwp',
                        render: function(data, type) {{
                            return type === 'display' ? (data * 100).toFixed(1) + '%' : data;
                        }}
                    }},
                    {{
                        data: 'owp',
                        render: function(data, type) {{
                            return type === 'display' ? (data * 100).toFixed(1) + '%' : data;
                        }}
                    }},
                    {{ data: 'year' }},
                    {{ data: 'gender' }}
                ],
                order: [[5, 'desc']],
                pageLength: 25,
                lengthMenu: [[10, 25, 50, 100, -1], [10, 25, 50, 100, "All"]],
                dom: 'lrtip',
                language: {{
                    emptyTable: "No rankings match your filters"
                }}
            }});

            // Custom filtering
            $.fn.dataTable.ext.search.push(function(settings, data, dataIndex) {{
                const yearFilter = $('#yearFilter').val();
                const genderFilter = $('#genderFilter').val();
                const classFilter = $('#classFilter').val();

                const rowYear = data[8];
                const rowGender = data[9];
                const rowClass = data[3];

                if (yearFilter && rowYear !== yearFilter) return false;
                if (genderFilter && rowGender !== genderFilter) return false;
                if (classFilter && !rowClass.includes(classFilter)) return false;

                return true;
            }});

            // Filter event handlers
            $('#yearFilter, #genderFilter, #classFilter').on('change', function() {{
                table.draw();
            }});

            // Search box
            $('#searchBox').on('keyup', function() {{
                table.search(this.value).draw();
            }});

            // Set default filters (most recent year, Boys)
            $('#yearFilter').val('{years[0]}');
            $('#genderFilter').val('Boys');
            table.draw();
        }});
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

    print("Building rankings...")
    rankings = build_rankings(data_dir, master_school_list)

    print("Generating HTML dashboard...")
    html = generate_html(rankings)

    with open(output_file, 'w') as f:
        f.write(html)

    print(f"\nDashboard saved to {output_file}")
    print(f"Total rankings: {len(rankings)}")
    print("\nOpen index.html in your browser to view the rankings!")


if __name__ == '__main__':
    main()
