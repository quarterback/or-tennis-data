#!/usr/bin/env python3
"""
Generate weekly rankings snapshot for Oregon HS tennis.

Reads the current processed rankings data and generates a weekly rankings
HTML page showing Power Index rankings for teams with 3+ dual matches.

Usage:
    python scripts/generate_weekly_rankings.py
    python scripts/generate_weekly_rankings.py --week 2026-04-07
"""

import json
import os
import argparse
from datetime import datetime, timedelta
from collections import defaultdict

MIN_MATCHES = 3
YEAR = 2026

def get_week_monday(date_str=None):
    """Get the Monday of the given week. Defaults to most recent Monday."""
    if date_str:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
    else:
        dt = datetime.now()
    # Go back to Monday
    monday = dt - timedelta(days=dt.weekday())
    return monday

def load_rankings(filepath):
    """Load processed rankings JSON."""
    with open(filepath, 'r') as f:
        return json.load(f)

def filter_rankings(rankings, year, min_matches, gender):
    """Filter rankings to a specific year, gender, and minimum match count."""
    filtered = []
    for r in rankings:
        if r['year'] != year:
            continue
        if r['gender'] != gender:
            continue
        if r['matches_played'] < min_matches:
            continue
        filtered.append(r)
    # Sort by power_index descending
    filtered.sort(key=lambda x: x['power_index'], reverse=True)
    # Assign weekly rank
    for i, r in enumerate(filtered):
        r['weekly_rank'] = i + 1
    return filtered

def classification_badge_class(classification):
    """Return CSS class for classification badge."""
    if '6A' in classification:
        return 'badge-6a'
    elif '5A' in classification:
        return 'badge-5a'
    else:
        return 'badge-4a'

def apr_class(apr):
    """Return CSS class for APR coloring."""
    if apr >= 0.6:
        return 'apr-high'
    elif apr >= 0.4:
        return 'apr-mid'
    return 'apr-low'

def generate_team_rows(teams):
    """Generate HTML table rows for a list of ranked teams."""
    rows = []
    for t in teams:
        rank = t['weekly_rank']
        rank_class = ''
        if rank == 1:
            rank_class = ' class="rank-1"'
        elif rank == 2:
            rank_class = ' class="rank-2"'
        elif rank == 3:
            rank_class = ' class="rank-3"'

        badge_cls = classification_badge_class(t.get('classification', ''))
        apr_cls = apr_class(t['apr'])

        # Movement indicator (not available for first week)
        pi_display = f"{t['power_index']:.4f}"

        row = f"""<tr>
  <td{rank_class}>{rank}</td>
  <td><span class="school-name">{t['school_name']}</span> <span class="badge {badge_cls}">{t.get('classification', '')}</span></td>
  <td>{t.get('city', '')}</td>
  <td>{t['record']}</td>
  <td>{t['matches_played']}</td>
  <td class="{apr_cls}">{t['apr']:.4f}</td>
  <td>{t['normalized_fws']:.4f}</td>
  <td class="power-index">{pi_display}</td>
  <td>{t.get('league', '')}</td>
</tr>"""
        rows.append(row)
    return '\n'.join(rows)

def generate_html(boys, girls, week_monday, week_num):
    """Generate the weekly rankings HTML page."""
    week_label = week_monday.strftime('%B %d, %Y')
    week_end = week_monday + timedelta(days=6)
    week_end_label = week_end.strftime('%B %d, %Y')

    boys_rows = generate_team_rows(boys)
    girls_rows = generate_team_rows(girls)

    boys_count = len(boys)
    girls_count = len(girls)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Weekly Rankings - Oregon HS Tennis</title>
    <meta name="description" content="Oregon High School Tennis Weekly Power Index Rankings for the week of {week_label}.">
    <link rel="icon" type="image/x-icon" href="favicon.ico">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.datatables.net/1.13.7/css/dataTables.bootstrap5.min.css" rel="stylesheet">
    <style>
        body {{ background: #f8f9fa; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        .navbar {{ background: #198754; }}
        .navbar-brand {{ color: #fff !important; font-weight: 600; }}
        .navbar .nav-link {{ color: rgba(255,255,255,0.8) !important; }}
        .navbar .nav-link:hover {{ color: #fff !important; }}
        .navbar .nav-link.active {{ color: #fff !important; font-weight: 600; }}
        .week-header {{ background: #fff; border-bottom: 1px solid #dee2e6; padding: 24px 0; }}
        .week-header h1 {{ font-size: 28px; font-weight: 700; margin: 0; }}
        .week-header .week-date {{ font-size: 16px; color: #6c757d; margin-top: 4px; }}
        .week-header .week-meta {{ font-size: 13px; color: #adb5bd; margin-top: 4px; }}
        .gender-section {{ margin-top: 24px; }}
        .gender-title {{ font-size: 20px; font-weight: 700; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 2px solid #198754; }}
        .table {{ font-size: 13px; }}
        .table th {{ font-size: 11px; text-transform: uppercase; color: #6c757d; font-weight: 600; cursor: pointer; white-space: nowrap; }}
        .table th:hover {{ color: #198754; }}
        .rank-1 {{ color: #ffc107; font-weight: 700; }}
        .rank-2 {{ color: #6c757d; font-weight: 700; }}
        .rank-3 {{ color: #cd7f32; font-weight: 700; }}
        .school-name {{ font-weight: 600; }}
        .apr-high {{ color: #198754; font-weight: 600; }}
        .apr-mid {{ color: #6c757d; }}
        .apr-low {{ color: #dc3545; }}
        .power-index {{ color: #0d6efd; font-weight: 700; }}
        .badge-6a {{ background: #0d6efd; color: #fff; font-size: 10px; padding: 2px 6px; border-radius: 3px; }}
        .badge-5a {{ background: #6f42c1; color: #fff; font-size: 10px; padding: 2px 6px; border-radius: 3px; }}
        .badge-4a {{ background: #198754; color: #fff; font-size: 10px; padding: 2px 6px; border-radius: 3px; }}
        .badge {{ vertical-align: middle; }}
        .filter-bar {{ background: #fff; padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
        .filter-bar label {{ font-size: 12px; font-weight: 600; color: #6c757d; margin-right: 6px; }}
        .filter-bar select {{ font-size: 13px; }}
        .formula-footer {{ margin-top: 12px; padding: 10px 15px; background: #f8f9fa; border-radius: 4px; border-left: 3px solid #198754; font-size: 12px; color: #6c757d; }}
        .back-link {{ color: #198754; text-decoration: none; font-weight: 500; }}
        .back-link:hover {{ text-decoration: underline; }}
        .tab-btn {{ padding: 8px 20px; border: 1px solid #dee2e6; background: #fff; cursor: pointer; font-size: 14px; font-weight: 500; }}
        .tab-btn.active {{ background: #198754; color: #fff; border-color: #198754; }}
        .tab-btn:first-child {{ border-radius: 6px 0 0 6px; }}
        .tab-btn:last-child {{ border-radius: 0 6px 6px 0; }}
        .gender-tab {{ display: none; }}
        .gender-tab.active {{ display: block; }}
    </style>
</head>
<body>

<nav class="navbar navbar-expand-lg">
    <div class="container">
        <a class="navbar-brand" href="index.html">Oregon HS Tennis</a>
        <div class="navbar-nav ms-auto">
            <a class="nav-link" href="index.html">Rankings</a>
            <a class="nav-link active" href="weekly-rankings.html">Weekly Rankings</a>
        </div>
    </div>
</nav>

<div class="week-header">
    <div class="container">
        <h1>Weekly Rankings</h1>
        <div class="week-date">Week of {week_label} &mdash; {week_end_label}</div>
        <div class="week-meta">{YEAR} Season &middot; Week {week_num} &middot; Min. {MIN_MATCHES} dual matches &middot; {boys_count} boys teams &middot; {girls_count} girls teams</div>
    </div>
</div>

<div class="container" style="margin-top: 20px;">

    <div style="text-align: center; margin-bottom: 20px;">
        <button class="tab-btn active" onclick="showGender('boys', this)">Boys</button>
        <button class="tab-btn" onclick="showGender('girls', this)">Girls</button>
    </div>

    <div id="boys-tab" class="gender-tab active">
        <div class="filter-bar">
            <label>Classification:</label>
            <select id="boys-class-filter" onchange="filterTable('boys')">
                <option value="">All</option>
                <option value="6A">6A</option>
                <option value="5A">5A</option>
                <option value="4A/3A/2A/1A">4A/3A/2A/1A</option>
            </select>
            <label style="margin-left: 16px;">League:</label>
            <select id="boys-league-filter" onchange="filterTable('boys')">
                <option value="">All</option>
            </select>
        </div>
        <div class="table-responsive">
            <table class="table table-sm table-hover" id="boys-table">
                <thead>
                    <tr>
                        <th style="width: 50px;">Rank</th>
                        <th>School</th>
                        <th>City</th>
                        <th>Record</th>
                        <th>Matches</th>
                        <th title="Adjusted Power Rating: (WP x 0.25) + (OWP x 0.50) + (OOWP x 0.25)">APR</th>
                        <th title="Normalized Flight Weighted Score (0-1)">FWS</th>
                        <th title="Power Index: (APR x 0.50) + (FWS x 0.50)">PI</th>
                        <th>League</th>
                    </tr>
                </thead>
                <tbody>
                    {boys_rows}
                </tbody>
            </table>
        </div>
    </div>

    <div id="girls-tab" class="gender-tab">
        <div class="filter-bar">
            <label>Classification:</label>
            <select id="girls-class-filter" onchange="filterTable('girls')">
                <option value="">All</option>
                <option value="6A">6A</option>
                <option value="5A">5A</option>
                <option value="4A/3A/2A/1A">4A/3A/2A/1A</option>
            </select>
            <label style="margin-left: 16px;">League:</label>
            <select id="girls-league-filter" onchange="filterTable('girls')">
                <option value="">All</option>
            </select>
        </div>
        <div class="table-responsive">
            <table class="table table-sm table-hover" id="girls-table">
                <thead>
                    <tr>
                        <th style="width: 50px;">Rank</th>
                        <th>School</th>
                        <th>City</th>
                        <th>Record</th>
                        <th>Matches</th>
                        <th title="Adjusted Power Rating: (WP x 0.25) + (OWP x 0.50) + (OOWP x 0.25)">APR</th>
                        <th title="Normalized Flight Weighted Score (0-1)">FWS</th>
                        <th title="Power Index: (APR x 0.50) + (FWS x 0.50)">PI</th>
                        <th>League</th>
                    </tr>
                </thead>
                <tbody>
                    {girls_rows}
                </tbody>
            </table>
        </div>
    </div>

    <div class="formula-footer">
        <strong>Power Index</strong> = (APR &times; 0.50) + (FWS &times; 0.50)<br>
        <strong>APR</strong> (Adjusted Power Rating) = (WP &times; 0.25) + (OWP &times; 0.50) + (OOWP &times; 0.25) &mdash; RPI-style strength of schedule<br>
        <strong>FWS</strong> (Flight Weighted Score) = weighted flight wins per match, normalized 0&ndash;1 &mdash; rewards depth across all flights<br>
        <strong>Minimum {MIN_MATCHES} dual matches</strong> required to appear in weekly rankings.
    </div>

    <div style="text-align: center; margin: 24px 0; font-size: 12px; color: #adb5bd;">
        Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} &middot; Data from <a href="https://tennisreporting.com" style="color: #adb5bd;">TennisReporting</a>
    </div>
</div>

<script>
function showGender(gender, btn) {{
    document.querySelectorAll('.gender-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(gender + '-tab').classList.add('active');
    btn.classList.add('active');
}}

function filterTable(gender) {{
    const classVal = document.getElementById(gender + '-class-filter').value;
    const leagueVal = document.getElementById(gender + '-league-filter').value;
    const table = document.getElementById(gender + '-table');
    const rows = table.querySelectorAll('tbody tr');
    let visibleRank = 0;
    rows.forEach(row => {{
        const cells = row.querySelectorAll('td');
        const schoolCell = cells[1].innerHTML;
        const leagueCell = cells[8].textContent.trim();
        let classMatch = true;
        let leagueMatch = true;
        if (classVal) {{
            classMatch = schoolCell.includes(classVal);
        }}
        if (leagueVal) {{
            leagueMatch = leagueCell === leagueVal;
        }}
        if (classMatch && leagueMatch) {{
            row.style.display = '';
            visibleRank++;
            cells[0].textContent = visibleRank;
        }} else {{
            row.style.display = 'none';
        }}
    }});
}}

// Populate league filter dropdowns
function populateLeagues(gender) {{
    const table = document.getElementById(gender + '-table');
    const rows = table.querySelectorAll('tbody tr');
    const leagues = new Set();
    rows.forEach(row => {{
        const league = row.querySelectorAll('td')[8].textContent.trim();
        if (league) leagues.add(league);
    }});
    const select = document.getElementById(gender + '-league-filter');
    [...leagues].sort().forEach(l => {{
        const opt = document.createElement('option');
        opt.value = l;
        opt.textContent = l;
        select.appendChild(opt);
    }});
}}

// Column sorting
document.querySelectorAll('table thead th').forEach((th, colIdx) => {{
    th.addEventListener('click', function() {{
        const table = this.closest('table');
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const isNumeric = [0, 3, 4, 5, 6, 7].includes(colIdx);
        const currentDir = this.dataset.sortDir || 'asc';
        const newDir = currentDir === 'asc' ? 'desc' : 'asc';

        rows.sort((a, b) => {{
            let aVal = a.querySelectorAll('td')[colIdx].textContent.trim();
            let bVal = b.querySelectorAll('td')[colIdx].textContent.trim();
            if (isNumeric) {{
                // Handle records like "5-2-0"
                if (colIdx === 3) {{
                    const aParts = aVal.split('-').map(Number);
                    const bParts = bVal.split('-').map(Number);
                    aVal = aParts[0] - (aParts[1] || 0);
                    bVal = bParts[0] - (bParts[1] || 0);
                }} else {{
                    aVal = parseFloat(aVal) || 0;
                    bVal = parseFloat(bVal) || 0;
                }}
                return newDir === 'asc' ? aVal - bVal : bVal - aVal;
            }}
            return newDir === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
        }});

        rows.forEach(r => tbody.appendChild(r));
        // Re-number ranks
        rows.forEach((r, i) => {{
            if (r.style.display !== 'none') {{
                r.querySelectorAll('td')[0].textContent = i + 1;
            }}
        }});
        this.dataset.sortDir = newDir;
    }});
}});

populateLeagues('boys');
populateLeagues('girls');
</script>

</body>
</html>"""
    return html


def main():
    parser = argparse.ArgumentParser(description='Generate weekly tennis rankings')
    parser.add_argument('--week', type=str, default=None, help='Monday date (YYYY-MM-DD). Defaults to most recent Monday.')
    parser.add_argument('--data', type=str, default='public/data/processed_rankings.json', help='Path to processed rankings JSON')
    parser.add_argument('--output', type=str, default='weekly-rankings.html', help='Output HTML file')
    args = parser.parse_args()

    week_monday = get_week_monday(args.week)

    # Calculate week number (Week 1 = first Monday on or after April 1)
    season_start = datetime(YEAR, 4, 1)
    season_start_monday = season_start - timedelta(days=season_start.weekday())
    if season_start_monday < season_start:
        season_start_monday += timedelta(days=7)
    week_num = max(1, ((week_monday - season_start_monday).days // 7) + 1)

    print(f"Generating weekly rankings for week of {week_monday.strftime('%Y-%m-%d')} (Week {week_num})")

    # Load rankings
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    data_path = os.path.join(project_root, args.data)

    if not os.path.exists(data_path):
        print(f"Error: {data_path} not found. Run generate_site.py first.")
        return

    rankings = load_rankings(data_path)
    print(f"Loaded {len(rankings)} total ranking entries")

    # Filter to 2026 with minimum matches
    boys = filter_rankings(rankings, YEAR, MIN_MATCHES, 'Boys')
    girls = filter_rankings(rankings, YEAR, MIN_MATCHES, 'Girls')
    print(f"Boys: {len(boys)} teams with {MIN_MATCHES}+ matches")
    print(f"Girls: {len(girls)} teams with {MIN_MATCHES}+ matches")

    # Generate HTML
    html = generate_html(boys, girls, week_monday, week_num)

    output_path = os.path.join(project_root, args.output)
    with open(output_path, 'w') as f:
        f.write(html)
    print(f"Written to {output_path}")

    # Also save snapshot data
    snapshot_dir = os.path.join(project_root, 'public', 'data', 'weekly')
    os.makedirs(snapshot_dir, exist_ok=True)
    snapshot = {
        'week': week_monday.strftime('%Y-%m-%d'),
        'week_num': week_num,
        'generated': datetime.now().isoformat(),
        'boys': boys,
        'girls': girls,
    }
    snapshot_path = os.path.join(snapshot_dir, f"{week_monday.strftime('%Y-%m-%d')}.json")
    with open(snapshot_path, 'w') as f:
        json.dump(snapshot, f, indent=2)
    print(f"Snapshot saved to {snapshot_path}")


if __name__ == '__main__':
    main()
