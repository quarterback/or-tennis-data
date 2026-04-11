#!/usr/bin/env python3
"""
Generate weekly rankings for Oregon HS tennis.
Combines existing Power Index with 5 computer ranking algorithms.
Produces per-week HTML pages and an archive index.

Usage:
    python scripts/generate_weekly_rankings.py                  # current week only
    python scripts/generate_weekly_rankings.py --all            # all weeks through today
    python scripts/generate_weekly_rankings.py --week 2026-04-04  # specific week
"""

import json
import csv
import os
import sys
import shutil
import argparse
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from computer_rankings import run_all, ratings_to_ranks, composite_ranks

MIN_MATCHES = 3
YEAR = 2026
SEASON_START = datetime(2026, 3, 30)
SEASON_END = datetime(2026, 5, 16)


def get_week_saturday(date_str=None):
    if date_str:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
    else:
        dt = datetime.now()
    days_until_sat = (5 - dt.weekday()) % 7
    if days_until_sat == 0:
        return dt
    return dt - timedelta(days=(dt.weekday() + 2) % 7)


def first_saturday():
    d = SEASON_START
    while d.weekday() != 5:
        d += timedelta(days=1)
    return d


def get_week_num(sat_date):
    return max(1, ((sat_date - first_saturday()).days // 7) + 1)


def all_week_saturdays():
    """Return list of all Saturday dates from season start through today."""
    sats = []
    d = first_saturday()
    today = datetime.now()
    while d <= today and d <= SEASON_END:
        sats.append(d)
        d += timedelta(days=7)
    return sats


def is_dual_match(meet):
    title = meet.get('title', '')
    if any(x in title for x in ['State Championship', 'District', 'Tournament']):
        return False
    if 'Event' in title and '.' in title:
        return False
    schools = meet.get('schools', {})
    return len(schools.get('winners', [])) == 1 and len(schools.get('losers', [])) == 1


def load_school_info(project_root):
    info = {}
    path = os.path.join(project_root, 'master_school_list.csv')
    with open(path, 'r') as f:
        for row in csv.DictReader(f):
            if row['id']:
                info[int(row['id'])] = {
                    'name': row['name'],
                    'city': row['city'],
                    'classification': row.get('Classification', ''),
                    'league': row.get('League', ''),
                }
    return info


def load_2026_data(project_root):
    data = {}
    data_dir = os.path.join(project_root, 'data', '2026')
    for f in os.listdir(data_dir):
        if not f.endswith('.json'):
            continue
        parts = f.replace('.json', '').split('_')
        school_id = int(parts[1])
        gender_id = int(parts[3])
        with open(os.path.join(data_dir, f)) as fh:
            data[(school_id, gender_id)] = json.load(fh)
    return data


def extract_matches(raw_data, gender_id, cutoff_date=None):
    """
    Extract dual match results, optionally filtering by date.
    cutoff_date: datetime - only include matches on or before this date.
    """
    match_graph = defaultdict(list)
    match_list = []
    team_records = {}
    seen = set()

    cutoff_str = cutoff_date.strftime('%Y-%m-%d') if cutoff_date else None

    for (school_id, gid), data in raw_data.items():
        if gid != gender_id:
            continue

        school_name = data.get('school', {}).get('name', f'School {school_id}')
        if school_id not in team_records:
            team_records[school_id] = {'wins': 0, 'losses': 0, 'ties': 0, 'name': school_name}

        for meet in data.get('meets', []):
            if not is_dual_match(meet):
                continue

            date_str = meet.get('meetDateTime', '')[:10]
            if cutoff_str and date_str > cutoff_str:
                continue

            schools = meet.get('schools', {})
            winners = schools.get('winners', [])
            losers = schools.get('losers', [])

            my_score = opp_score = None
            opp_id = None
            for w in winners:
                if w['id'] == school_id:
                    my_score = w.get('score', 0)
                else:
                    opp_id = w['id']
                    opp_score = w.get('score', 0)
            for l in losers:
                if l['id'] == school_id:
                    my_score = l.get('score', 0)
                else:
                    opp_id = l['id']
                    opp_score = l.get('score', 0)

            if opp_id is None or my_score is None or opp_score is None:
                continue

            margin = my_score - opp_score
            won = my_score > opp_score
            match_graph[school_id].append((opp_id, won, margin))

            key = (date_str, min(school_id, opp_id), max(school_id, opp_id))
            if key not in seen:
                seen.add(key)
                match_list.append((date_str, school_id, opp_id, won, margin))

    for tid, matches in match_graph.items():
        rec = team_records.get(tid, {'wins': 0, 'losses': 0, 'ties': 0, 'name': ''})
        rec['wins'] = sum(1 for _, w, m in matches if w)
        rec['losses'] = sum(1 for _, w, m in matches if not w and m != 0)
        rec['ties'] = sum(1 for _, w, m in matches if m == 0 and not w)
        team_records[tid] = rec

    match_list.sort(key=lambda x: x[0])
    return match_graph, match_list, team_records


def build_weekly_rankings(raw_data, gender_id, school_info, pi_data, cutoff_date=None):
    match_graph, match_list, team_records = extract_matches(raw_data, gender_id, cutoff_date)

    eligible = {tid for tid, matches in match_graph.items() if len(matches) >= MIN_MATCHES}
    if not eligible:
        return []

    all_ratings = run_all(match_graph, match_list)
    all_ranks = {name: ratings_to_ranks(ratings) for name, ratings in all_ratings.items()}
    comp = composite_ranks(all_ranks, eligible)

    gender_label = 'Boys' if gender_id == 1 else 'Girls'
    pi_lookup = {}
    for r in pi_data:
        if r['year'] == YEAR and r['gender'] == gender_label:
            pi_lookup[r['school_id']] = r

    results = []
    for tid in eligible:
        pi = pi_lookup.get(tid, {})
        info = school_info.get(tid, {})
        rec = team_records.get(tid, {})
        c = comp.get(tid, {})
        w, l, t = rec.get('wins', 0), rec.get('losses', 0), rec.get('ties', 0)

        results.append({
            'school_id': tid,
            'school_name': rec.get('name', info.get('name', f'School {tid}')),
            'city': info.get('city', pi.get('city', '')),
            'classification': info.get('classification', pi.get('classification', '')),
            'league': info.get('league', pi.get('league', '')),
            'record': f"{w}-{l}-{t}",
            'wins': w, 'losses': l, 'ties': t,
            'matches': len(match_graph.get(tid, [])),
            'power_index': pi.get('power_index', 0),
            'composite_rank': c.get('composite', 999),
            'median_rank': c.get('median', 999),
            'std_dev': c.get('std', 0),
            'system_ranks': c.get('ranks', {}),
        })

    results.sort(key=lambda x: x['composite_rank'])
    for i, r in enumerate(results):
        r['rank'] = i + 1
    return results


def generate_week_html(boys, girls, week_date, week_num, systems, all_weeks=None, is_latest=False):
    """Generate HTML for a single week. all_weeks is list of (week_num, date_str) for archive nav."""
    week_label = week_date.strftime('%B %d, %Y')

    def team_rows(teams):
        rows = []
        for t in teams:
            rank = t['rank']
            rc = f' class="rank-{rank}"' if rank <= 3 else ''
            bc = 'badge-6a' if '6A' in t['classification'] else ('badge-5a' if '5A' in t['classification'] else 'badge-4a')
            sys_cells = ''.join(f'<td class="sys-rank">{t["system_ranks"].get(s, "-")}</td>' for s in systems)
            rows.append(f'<tr><td{rc}>{rank}</td>'
                        f'<td><span class="school-name">{t["school_name"]}</span> <span class="badge {bc}">{t["classification"]}</span></td>'
                        f'<td>{t["record"]}</td><td class="power-index">{t["power_index"]:.4f}</td>'
                        f'<td>{t["composite_rank"]:.1f}</td><td>{t["median_rank"]:.0f}</td><td>{t["std_dev"]:.1f}</td>'
                        f'{sys_cells}<td>{t["league"]}</td></tr>')
        return '\n'.join(rows)

    sys_headers = ''.join(f'<th title="{s} rank">{s}</th>' for s in systems)
    boys_rows = team_rows(boys)
    girls_rows = team_rows(girls)

    # Week navigation links
    week_nav = ''
    if all_weeks:
        links = []
        for wn, wdate in all_weeks:
            if wn == week_num:
                links.append(f'<span class="week-link active">Week {wn}</span>')
            else:
                links.append(f'<a class="week-link" href="weekly/week-{wn}.html">Week {wn}</a>')
        week_nav = '<div class="week-nav">' + ' '.join(links) + '</div>'

    # For archive pages, the relative path to root is ../
    # For the main weekly-rankings.html, it's ./
    prefix = '' if is_latest else '../'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Weekly Rankings - Week {week_num} - Oregon HS Tennis</title>
<link rel="icon" type="image/x-icon" href="{prefix}favicon.ico">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body {{ background: #f8f9fa; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
.navbar {{ background: #198754; }}
.navbar-brand {{ color: #fff !important; font-weight: 600; }}
.navbar .nav-link {{ color: rgba(255,255,255,0.8) !important; }}
.navbar .nav-link:hover {{ color: #fff !important; }}
.navbar .nav-link.active {{ color: #fff !important; font-weight: 600; }}
.week-header {{ background: #fff; border-bottom: 1px solid #dee2e6; padding: 24px 0; }}
.week-header h1 {{ font-size: 28px; font-weight: 700; margin: 0; }}
.week-header .sub {{ font-size: 15px; color: #6c757d; margin-top: 4px; }}
.week-header .meta {{ font-size: 13px; color: #adb5bd; margin-top: 4px; }}
.week-nav {{ text-align: center; margin: 16px 0; display: flex; gap: 4px; justify-content: center; flex-wrap: wrap; }}
.week-link {{ padding: 6px 14px; border: 1px solid #dee2e6; border-radius: 4px; text-decoration: none; color: #495057; font-size: 13px; font-weight: 500; }}
.week-link:hover {{ background: #e9ecef; }}
.week-link.active {{ background: #198754; color: #fff; border-color: #198754; }}
.table {{ font-size: 13px; }}
.table th {{ font-size: 11px; text-transform: uppercase; color: #6c757d; font-weight: 600; white-space: nowrap; cursor: pointer; }}
.table th:hover {{ color: #198754; }}
.rank-1 {{ color: #ffc107; font-weight: 700; }}
.rank-2 {{ color: #6c757d; font-weight: 700; }}
.rank-3 {{ color: #cd7f32; font-weight: 700; }}
.school-name {{ font-weight: 600; }}
.power-index {{ color: #0d6efd; font-weight: 700; }}
.sys-rank {{ text-align: center; color: #495057; }}
.badge-6a {{ background: #0d6efd; color: #fff; font-size: 10px; padding: 2px 6px; border-radius: 3px; }}
.badge-5a {{ background: #6f42c1; color: #fff; font-size: 10px; padding: 2px 6px; border-radius: 3px; }}
.badge-4a {{ background: #198754; color: #fff; font-size: 10px; padding: 2px 6px; border-radius: 3px; }}
.badge {{ vertical-align: middle; }}
.filter-bar {{ background: #fff; padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
.filter-bar label {{ font-size: 12px; font-weight: 600; color: #6c757d; margin-right: 6px; }}
.tab-btn {{ padding: 8px 20px; border: 1px solid #dee2e6; background: #fff; cursor: pointer; font-size: 14px; font-weight: 500; }}
.tab-btn.active {{ background: #198754; color: #fff; border-color: #198754; }}
.tab-btn:first-child {{ border-radius: 6px 0 0 6px; }}
.tab-btn:last-child {{ border-radius: 0 6px 6px 0; }}
.gender-tab {{ display: none; }}
.gender-tab.active {{ display: block; }}
.info {{ margin-top: 12px; padding: 10px 15px; background: #f8f9fa; border-radius: 4px; border-left: 3px solid #198754; font-size: 12px; color: #6c757d; }}
</style>
</head>
<body>

<nav class="navbar navbar-expand-lg">
<div class="container">
    <a class="navbar-brand" href="{prefix}index.html">Oregon HS Tennis</a>
    <div class="navbar-nav ms-auto">
        <a class="nav-link" href="{prefix}index.html">Rankings</a>
        <a class="nav-link active" href="{prefix}weekly-rankings.html">Weekly Rankings</a>
    </div>
</div>
</nav>

<div class="week-header">
<div class="container">
    <h1>Weekly Rankings &mdash; Week {week_num}</h1>
    <div class="sub">{week_label} &middot; {YEAR} Season</div>
    <div class="meta">{len(boys)} boys teams &middot; {len(girls)} girls teams &middot; Min. {MIN_MATCHES} dual matches</div>
</div>
</div>

<div class="container" style="margin-top: 20px;">

{week_nav}

<div style="text-align: center; margin-bottom: 20px;">
    <button class="tab-btn active" onclick="showGender('boys', this)">Boys</button>
    <button class="tab-btn" onclick="showGender('girls', this)">Girls</button>
</div>

<div id="boys-tab" class="gender-tab active">
<div class="filter-bar">
    <label>Classification:</label>
    <select id="boys-cf" onchange="filterRows('boys')">
        <option value="">All</option><option value="6A">6A</option><option value="5A">5A</option><option value="4A/3A/2A/1A">4A/3A/2A/1A</option>
    </select>
</div>
<div class="table-responsive">
<table class="table table-sm table-hover" id="boys-table">
<thead><tr>
    <th>Rank</th><th>School</th><th>Record</th><th title="Power Index">PI</th>
    <th title="Average rank across all systems (lower=better)">Composite</th>
    <th title="Median rank across systems">Median</th>
    <th title="Standard deviation - how much systems disagree">Spread</th>
    {sys_headers}
    <th>League</th>
</tr></thead>
<tbody>{boys_rows}</tbody>
</table>
</div>
</div>

<div id="girls-tab" class="gender-tab">
<div class="filter-bar">
    <label>Classification:</label>
    <select id="girls-cf" onchange="filterRows('girls')">
        <option value="">All</option><option value="6A">6A</option><option value="5A">5A</option><option value="4A/3A/2A/1A">4A/3A/2A/1A</option>
    </select>
</div>
<div class="table-responsive">
<table class="table table-sm table-hover" id="girls-table">
<thead><tr>
    <th>Rank</th><th>School</th><th>Record</th><th title="Power Index">PI</th>
    <th title="Average rank across all systems (lower=better)">Composite</th>
    <th title="Median rank across systems">Median</th>
    <th title="Standard deviation - how much systems disagree">Spread</th>
    {sys_headers}
    <th>League</th>
</tr></thead>
<tbody>{girls_rows}</tbody>
</table>
</div>
</div>

<div class="info">
<strong>How it works:</strong> Five independent computer ranking systems each produce their own team ordering.
The <strong>Composite</strong> rank is each team's average rank across all systems. <strong>Spread</strong> measures disagreement &mdash;
low spread means consensus, high spread means the team is controversial.<br><br>
<strong>Elo</strong> &mdash; game-by-game rating updates, flight margin weighted.
<strong>Colley</strong> &mdash; pure W/L, opponent-adjusted (no margins).
<strong>Massey</strong> &mdash; least-squares on flight margins, capped at &plusmn;6.
<strong>PageRank</strong> &mdash; authority in the win/loss graph.
<strong>Win-Score</strong> &mdash; each win earns the opponent's win percentage.<br><br>
<strong>PI</strong> (Power Index) = 50% APR + 50% FWS, from the main rankings page. Shown for reference.
</div>

<div style="text-align: center; margin: 24px 0; font-size: 12px; color: #adb5bd;">
    Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}
</div>
</div>

<script>
function showGender(g, btn) {{
    document.querySelectorAll('.gender-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(g + '-tab').classList.add('active');
    btn.classList.add('active');
}}
function filterRows(g) {{
    const cv = document.getElementById(g + '-cf').value;
    const rows = document.querySelectorAll('#' + g + '-table tbody tr');
    let n = 0;
    rows.forEach(r => {{
        const match = !cv || r.querySelectorAll('td')[1].innerHTML.includes(cv);
        r.style.display = match ? '' : 'none';
        if (match) {{ n++; r.querySelectorAll('td')[0].textContent = n; }}
    }});
}}
document.querySelectorAll('table thead th').forEach((th, ci) => {{
    th.addEventListener('click', function() {{
        const table = this.closest('table');
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const dir = this.dataset.sd === 'd' ? 'a' : 'd';
        rows.sort((a, b) => {{
            let av = a.querySelectorAll('td')[ci].textContent.trim();
            let bv = b.querySelectorAll('td')[ci].textContent.trim();
            const an = parseFloat(av), bn = parseFloat(bv);
            if (!isNaN(an) && !isNaN(bn)) return dir === 'a' ? an - bn : bn - an;
            return dir === 'a' ? av.localeCompare(bv) : bv.localeCompare(av);
        }});
        rows.forEach((r, i) => {{ tbody.appendChild(r); r.querySelectorAll('td')[0].textContent = i + 1; }});
        this.dataset.sd = dir;
    }});
}});
</script>
</body>
</html>"""
    return html


def main():
    parser = argparse.ArgumentParser(description='Generate weekly tennis rankings')
    parser.add_argument('--week', type=str, default=None, help='Saturday date YYYY-MM-DD')
    parser.add_argument('--all', action='store_true', help='Generate all weeks through today')
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Load data once
    school_info = load_school_info(project_root)
    raw_data = load_2026_data(project_root)
    pi_path = os.path.join(project_root, 'public', 'data', 'processed_rankings.json')
    with open(pi_path) as f:
        pi_data = json.load(f)
    print(f"Loaded {len(raw_data)} data files")

    systems = ['Elo', 'Colley', 'Massey', 'PageRank', 'Win-Score']

    # Determine which weeks to generate
    if args.all:
        weeks = all_week_saturdays()
    elif args.week:
        weeks = [datetime.strptime(args.week, '%Y-%m-%d')]
    else:
        weeks = [get_week_saturday()]

    # Build list of all weeks for navigation
    all_sats = all_week_saturdays()
    all_weeks_nav = [(get_week_num(s), s.strftime('%Y-%m-%d')) for s in all_sats]

    # Create output directories
    weekly_dir = os.path.join(project_root, 'public', 'weekly')
    os.makedirs(weekly_dir, exist_ok=True)
    snap_dir = os.path.join(project_root, 'public', 'data', 'weekly')
    os.makedirs(snap_dir, exist_ok=True)

    latest_html = None
    for week_date in weeks:
        week_num = get_week_num(week_date)
        print(f"\nWeek {week_num}: {week_date.strftime('%Y-%m-%d')}")

        boys = build_weekly_rankings(raw_data, 1, school_info, pi_data, cutoff_date=week_date)
        girls = build_weekly_rankings(raw_data, 2, school_info, pi_data, cutoff_date=week_date)
        print(f"  Boys: {len(boys)} teams | Girls: {len(girls)} teams")

        # Generate archive page (relative paths go up one level)
        archive_html = generate_week_html(boys, girls, week_date, week_num, systems, all_weeks_nav, is_latest=False)
        archive_path = os.path.join(weekly_dir, f'week-{week_num}.html')
        with open(archive_path, 'w') as f:
            f.write(archive_html)
        print(f"  Archive: {archive_path}")

        # Save JSON snapshot
        snap = {
            'week': week_date.strftime('%Y-%m-%d'),
            'week_num': week_num,
            'generated': datetime.now().isoformat(),
            'systems': systems,
            'boys': boys,
            'girls': girls,
        }
        snap_path = os.path.join(snap_dir, f"{week_date.strftime('%Y-%m-%d')}.json")
        with open(snap_path, 'w') as f:
            json.dump(snap, f)

        # Track latest for main page
        latest_html = generate_week_html(boys, girls, week_date, week_num, systems, all_weeks_nav, is_latest=True)

    # Write latest week as main weekly-rankings.html
    if latest_html:
        main_path = os.path.join(project_root, 'public', 'weekly-rankings.html')
        with open(main_path, 'w') as f:
            f.write(latest_html)
        print(f"\nLatest: {main_path}")


if __name__ == '__main__':
    main()
