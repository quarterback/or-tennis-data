#!/usr/bin/env python3
"""Build the print-ready league seeding packet.

At a district seeding meeting somebody prints the season out and the committee
marks it up in the room. Until now that meant screenshotting the rankings table.
This writes one self-contained page per league that holds everything the meeting
argues about:

  1. Standings — league and overall record, Power Index, state and class rank.
  2. Head-to-head grid — who beat whom, by what flight score, on what date.
  3. A page per team — flight-by-flight record across all eight positions, plus
     the coach's submitted ladder (or the data-derived one, labelled as such).
  4. Scorecards — every league dual, flight by flight, with set scores.

Generated statically at build time rather than fetched live. The seeding meeting
is the one morning of the year this cannot be down, and after the merge step
`data/<year>/` already contains the coach-entered duals, so a static page built
on the existing cron is automatically current.

    python build_seeding_packet.py --year 2026
    python build_seeding_packet.py --year 2026 --league "Special District 1"

Outputs public/seeding/<year>/<slug>.html plus an index.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
RANKINGS = os.path.join(ROOT, "public", "data", "processed_rankings.json")
LINEUPS_DIR = os.path.join(ROOT, "public", "data", "lineups")
OUT_ROOT = os.path.join(ROOT, "public", "seeding")

SLOTS = ["S1", "S2", "S3", "S4", "D1", "D2", "D3", "D4"]
SLOT_LABEL = {"S1": "1S", "S2": "2S", "S3": "3S", "S4": "4S",
              "D1": "1D", "D2": "2D", "D3": "3D", "D4": "4D"}
GENDERS = {1: "Boys", 2: "Girls"}


def esc(value) -> str:
    return html.escape("" if value is None else str(value))


def slugify(*parts) -> str:
    joined = "-".join(str(p) for p in parts if p)
    return re.sub(r"-+", "-", re.sub(r"[^A-Za-z0-9]+", "-", joined)).strip("-").lower()


# ---------------------------------------------------------------------------
# Reading the season
# ---------------------------------------------------------------------------

def load_rankings(year: int) -> list[dict]:
    with open(RANKINGS, encoding="utf-8") as f:
        return [e for e in json.load(f) if int(e["year"]) == year]


def load_ladder(year: int, gender_id: int, school_id: int) -> dict | None:
    path = os.path.join(LINEUPS_DIR, str(year), f"{gender_id}{school_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def is_two_team(meet: dict) -> tuple[int, int] | None:
    schools = meet.get("schools") or {}
    winners = schools.get("winners") or []
    losers = schools.get("losers") or []
    if len(winners) != 1 or len(losers) != 1:
        return None
    return (winners[0].get("id"), losers[0].get("id"))


def load_duals(year: int, gender_id: int, school_ids: set[int]) -> list[dict]:
    """Every dual between two schools in this league, de-duplicated.

    The same dual appears in both schools' files, so it is keyed on
    (date, unordered pair) the way `dedupe_meets` does. Entered duals win, which
    is the same precedence the ranking pipeline applies.
    """
    seen: dict[tuple, dict] = {}
    for school_id in sorted(school_ids):
        path = os.path.join(DATA_DIR, str(year), f"school_{school_id}_gender_{gender_id}.json")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        for meet in doc.get("meets") or []:
            pair = is_two_team(meet)
            if not pair or pair[0] not in school_ids or pair[1] not in school_ids:
                continue
            date = (meet.get("meetDateTime") or "")[:10]
            key = (date, min(pair), max(pair))
            rank = (1 if meet.get("source") == "entered" else 0,
                    sum(len(v or []) for v in (meet.get("matches") or {}).values()))
            if key not in seen or rank > seen[key]["_rank"]:
                seen[key] = {**meet, "_rank": rank, "_date": date, "_pair": key[1:]}
    return sorted(seen.values(), key=lambda m: (m["_date"], m["_pair"]))


def meet_scores(meet: dict) -> dict[int, int]:
    out = {}
    for side in ("winners", "losers"):
        for s in (meet.get("schools") or {}).get(side) or []:
            out[s.get("id")] = s.get("score")
    return out


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

STYLE = """
  @page { size: letter portrait; margin: 0.5in; }
  * { box-sizing: border-box; }
  body { font-family: "Helvetica Neue", Arial, sans-serif; margin: 0; color: #111;
         background: #eee; font-size: 11px; }
  .page { width: 7.5in; min-height: 10in; padding: 0.2in; background: #fff;
          box-shadow: 0 1px 4px rgba(0,0,0,0.15); margin: 16px auto;
          page-break-after: always; }
  .page:last-child { page-break-after: auto; }
  .toolbar { max-width: 7.5in; margin: 12px auto 0; padding: 8px 12px; background: #fff;
             border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
             display: flex; gap: 12px; align-items: center; font-size: 12px; }
  .toolbar button { padding: 6px 12px; border: 1px solid #888; background: #f5f5f5;
                    border-radius: 3px; cursor: pointer; font-size: 12px; }
  @media print {
    body { background: #fff; }
    .page { margin: 0; box-shadow: none; }
    .toolbar { display: none; }
    /* Heat and status shading has to survive the printer, or the completeness
       line and the win/loss cells lose their meaning on paper. */
    * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  }
  h1 { margin: 0 0 2px; font-size: 17px; font-weight: 700; }
  h2 { margin: 18px 0 6px; font-size: 13px; font-weight: 700;
       border-bottom: 1px solid #ccc; padding-bottom: 3px; }
  h3 { margin: 14px 0 4px; font-size: 12px; font-weight: 700; }
  .sub { color: #555; font-size: 11px; margin: 0 0 10px; }
  table { border-collapse: collapse; width: 100%; font-size: 10px; }
  th, td { border: 1px solid #ddd; padding: 3px 5px; text-align: left; }
  th { background: #f2f2f2; font-size: 9px; text-transform: uppercase;
       letter-spacing: .03em; color: #444; }
  thead { display: table-header-group; }
  table { page-break-inside: avoid; }
  td.n, th.n { text-align: center; font-variant-numeric: tabular-nums; }
  .grid td { text-align: center; font-size: 9px; }
  .grid td.self { background: #333; }
  .grid td.win { background: #d8f0e0; }
  .grid td.loss { background: #f8dcdc; }
  .grid th.side { text-align: left; font-size: 9px; white-space: nowrap; }
  .note { font-size: 9px; color: #666; margin-top: 4px; }
  .completeness { border: 1px solid #ccc; background: #fafafa; padding: 8px 10px;
                  margin: 10px 0; font-size: 10px; }
  .completeness b { font-size: 11px; }
  .tag { display: inline-block; padding: 1px 6px; border-radius: 8px; font-size: 8px;
         font-weight: 700; vertical-align: 1px; }
  .tag.entered { background: #d8f0e0; color: #14532d; }
  .tag.scraped { background: #e8e8e8; color: #444; }
  .tag.contested { background: #f8dcdc; color: #7f1d1d; }
  .tag.coach { background: #dbeafe; color: #1e3a8a; }
  .tag.derived { background: #eee; color: #555; }
  .blank-line { border-bottom: 1px solid #999; height: 14px; }
  .bracket-slot { border: 1px solid #999; height: 20px; margin: 3px 0; padding: 2px 4px;
                  font-size: 9px; color: #999; }
"""


def render_standings(teams: list[dict]) -> str:
    rows = []
    for i, t in enumerate(teams, 1):
        rows.append(
            f"<tr><td class='n'>{i}</td><td>{esc(t['school_name'])}</td>"
            f"<td class='n'>{esc(t.get('league_record') or '')}</td>"
            f"<td class='n'>{esc(t.get('record') or '')}</td>"
            f"<td class='n'>{esc(t.get('total_flights_won'))}&ndash;"
            f"{esc((t.get('total_flights_played') or 0) - (t.get('total_flights_won') or 0))}</td>"
            f"<td class='n'>{t.get('power_index', 0):.4f}</td>"
            f"<td class='n'>{esc(t.get('rank') if t.get('rank') is not None else 'NR')}</td>"
            f"<td class='n'>{esc(t.get('class_rank') if t.get('class_rank') is not None else 'NR')}</td>"
            "</tr>")
    return (
        "<table><thead><tr><th class='n'>#</th><th>School</th><th class='n'>League</th>"
        "<th class='n'>Overall</th><th class='n'>Flights</th><th class='n'>Power Index</th>"
        "<th class='n'>State</th><th class='n'>Class</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
        "<p class='note'>League standings are ordered by Power Index. "
        "&ldquo;NR&rdquo; means fewer than three duals played, which is not enough "
        "to support a rank.</p>")


def short_name(name: str) -> str:
    """A grid-column-width name that still reads as the school.

    Truncating at a fixed width gives "RIVERSIDE (WES" and "TRINITY ACADEM".
    Dropping the parenthetical and cutting at a word boundary keeps it legible,
    which matters on a page someone reads across a table.
    """
    name = re.sub(r"\s*\(.*?\)", "", name).strip()
    if len(name) <= 18:
        return name
    words = name.split()
    out = words[0]
    for w in words[1:]:
        if len(out) + 1 + len(w) > 18:
            break
        out += " " + w
    return out[:18].rstrip()


def render_h2h(teams: list[dict], duals: list[dict]) -> str:
    ids = [t["school_id"] for t in teams]
    short = {t["school_id"]: short_name(t["school_name"]) for t in teams}

    played: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for meet in duals:
        a, b = meet["_pair"]
        played[(a, b)].append(meet)

    header = "".join(f"<th class='n'>{esc(short[i])}</th>" for i in ids)
    rows = []
    for a in ids:
        cells = []
        for b in ids:
            if a == b:
                cells.append("<td class='self'></td>")
                continue
            meets = played.get((min(a, b), max(a, b)), [])
            if not meets:
                cells.append("<td>&middot;</td>")
                continue
            parts, kind = [], ""
            for meet in meets:
                scores = meet_scores(meet)
                mine, theirs = scores.get(a), scores.get(b)
                if mine is None or theirs is None:
                    continue
                kind = "win" if mine > theirs else ("loss" if mine < theirs else "")
                parts.append(f"{mine}&ndash;{theirs}<br><span style='color:#777'>"
                             f"{esc(meet['_date'][5:])}</span>")
            cells.append(f"<td class='{kind}'>{'<hr>'.join(parts) or '&middot;'}</td>")
        rows.append(f"<tr><th class='side'>{esc(short[a])}</th>{''.join(cells)}</tr>")

    return (
        f"<table class='grid'><thead><tr><th class='side'></th>{header}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
        "<p class='note'>Read across: the row team's flight score first. "
        "Green is a win for the row team. A dot means the two have not met.</p>")


def render_team_page(team: dict, ladder: dict | None, duals: list[dict]) -> str:
    fb = team.get("flight_breakdown") or {}
    flight_rows = "".join(
        f"<tr><td>{SLOT_LABEL[s]}</td>"
        f"<td class='n'>{'&mdash;' if fb.get(s) is None else f'{fb[s]:.0f}%'}</td></tr>"
        for s in SLOTS)

    if ladder and ladder.get("ladder"):
        source = ("<span class='tag coach'>Coach ladder</span>"
                  if ladder.get("coach_submitted") else
                  "<span class='tag derived'>Data-derived order</span>")
        ladder_rows = "".join(
            f"<tr><td class='n'>{i}</td><td>{esc(p['name'])}</td>"
            f"<td class='n'>{esc(p.get('grade') or '')}</td>"
            f"<td class='n'>{esc(SLOT_LABEL.get(p.get('primary'), ''))}</td>"
            f"<td class='n'>{p['rec'][0]}&ndash;{p['rec'][1]}</td></tr>"
            for i, p in enumerate(ladder["ladder"][:14], 1))
        ladder_html = (
            f"<h3>Ladder {source}</h3>"
            "<table><thead><tr><th class='n'>#</th><th>Player</th><th class='n'>Gr</th>"
            "<th class='n'>Usual</th><th class='n'>Record</th></tr></thead>"
            f"<tbody>{ladder_rows}</tbody></table>")
    else:
        ladder_html = ("<h3>Ladder</h3><p class='note'>No ladder on file for this "
                       "team. Coaches submit one from the Lineups tool.</p>")

    results = "".join(
        f"<tr><td>{esc(meet['_date'])}</td>"
        f"<td>{esc(opponent_name(meet, team['school_id']))}</td>"
        f"<td class='n'>{esc(meet_scores(meet).get(team['school_id']))}&ndash;"
        f"{esc(next(v for k, v in meet_scores(meet).items() if k != team['school_id']))}</td>"
        f"<td class='n'>{source_tag(meet)}</td></tr>"
        for meet in duals if team["school_id"] in meet["_pair"])

    return f"""
    <div class="page">
      <h1>{esc(team['school_name'])}</h1>
      <p class="sub">{esc(team.get('classification'))} &middot; {esc(team.get('league'))}
        &middot; {esc(team.get('record'))} overall, {esc(team.get('league_record'))} in league
        &middot; Power Index {team.get('power_index', 0):.4f}</p>

      <h3>Flight win rate</h3>
      <table style="width:45%"><thead><tr><th>Position</th><th class='n'>Won</th></tr></thead>
        <tbody>{flight_rows}</tbody></table>
      <p class="note">A dash means the position was not contested this season.</p>

      {ladder_html}

      <h3>League results</h3>
      <table><thead><tr><th>Date</th><th>Opponent</th><th class='n'>Score</th>
        <th class='n'>Source</th></tr></thead><tbody>{results}</tbody></table>
    </div>"""


def opponent_name(meet: dict, school_id: int) -> str:
    for side in ("winners", "losers"):
        for s in (meet.get("schools") or {}).get(side) or []:
            if s.get("id") != school_id:
                return s.get("name") or ""
    return ""


def source_tag(meet: dict) -> str:
    if meet.get("contested"):
        return "<span class='tag contested'>Disputed</span>"
    if meet.get("source") == "entered":
        return "<span class='tag entered'>Coach</span>"
    return "<span class='tag scraped'>Imported</span>"


def render_scorecards(duals: list[dict]) -> str:
    """Every league dual as a printed card. This is what gets marked up."""
    cards = []
    for meet in duals:
        rows = []
        for match_type in ("Singles", "Doubles"):
            for line in sorted((meet.get("matches") or {}).get(match_type, []) or [],
                               key=lambda x: str(x.get("flight"))):
                slot = f"{match_type[0]}{line.get('flight')}"
                teams = line.get("matchTeams") or []
                names = []
                for t in teams:
                    names.append(" / ".join(
                        f"{(p.get('firstName') or '').strip()} {(p.get('lastName') or '').strip()}".strip()
                        for p in t.get("players") or []) or "&mdash;")
                score = ""
                if len(teams) == 2:
                    a, b = teams[0].get("id"), teams[1].get("id")
                    parts = []
                    for s in sorted(line.get("sets") or [], key=lambda x: x.get("number") or 0):
                        ga, gb = s.get(str(a)), s.get(str(b))
                        if ga is None or gb is None:
                            continue
                        seg = f"{ga}-{gb}"
                        if s.get("tie") is not None:
                            seg += f"({s['tie']})"
                        parts.append(seg)
                    score = ", ".join(parts)
                rows.append(
                    f"<tr><td>{esc(SLOT_LABEL.get(slot, slot))}</td>"
                    f"<td>{names[0] if names else ''}</td>"
                    f"<td>{names[1] if len(names) > 1 else ''}</td>"
                    f"<td class='n'>{esc(score)}</td></tr>")

        scores = meet_scores(meet)
        title = " vs ".join(
            f"{s.get('name')} {s.get('score')}"
            for side in ("winners", "losers")
            for s in (meet.get("schools") or {}).get(side) or [])
        cards.append(
            f"<h3>{esc(meet['_date'])} &middot; {esc(title)} {source_tag(meet)}</h3>"
            "<table><thead><tr><th>Pos</th><th>Home</th><th>Away</th>"
            "<th class='n'>Score</th></tr></thead>"
            f"<tbody>{''.join(rows) or '<tr><td colspan=4>No flight detail recorded.</td></tr>'}"
            "</tbody></table>")
        if not scores:
            continue
    return "".join(cards)


def render_bracket(teams: list[dict]) -> str:
    """A blank bracket seeded off the standings, for the room to fill in."""
    seeds = teams[:8]
    slots = "".join(
        f"<div class='bracket-slot'>{i}. {esc(t['school_name'])}</div>"
        for i, t in enumerate(seeds, 1))
    blanks = "".join("<div class='bracket-slot'>&nbsp;</div>" for _ in range(max(0, len(seeds) - 1)))
    return (f"<div style='display:flex;gap:24px'>"
            f"<div style='flex:1'><h3>Seeds</h3>{slots}</div>"
            f"<div style='flex:1'><h3>Draw</h3>{blanks}</div></div>"
            "<p class='note'>Seeds follow the Power Index order above. The draw is "
            "left blank for the committee.</p>")


def build_league(year: int, league: str, gender_id: int, entries: list[dict]) -> str | None:
    teams = sorted(
        [e for e in entries if e["league"] == league and e["gender"] == GENDERS[gender_id]],
        key=lambda e: (e["rank"] is None, e["rank"] if e["rank"] is not None else 999))
    if len(teams) < 2:
        return None

    school_ids = {t["school_id"] for t in teams}
    duals = load_duals(year, gender_id, school_ids)

    entered = sum(1 for m in duals if m.get("source") == "entered")
    contested = sum(1 for m in duals if m.get("contested"))
    # Count pairings met rather than duals against an expected total: leagues
    # play home-and-away, so a single round-robin is a floor, not a target, and
    # "57 of 55" reads like the page is broken.
    pairs_met = len({m["_pair"] for m in duals})
    total_pairs = len(teams) * (len(teams) - 1) // 2
    unmet = total_pairs - pairs_met
    completeness = (
        f"<div class='completeness'><b>{len(duals)}</b> league duals on file &middot; "
        f"{pairs_met} of {total_pairs} pairings have met"
        + (f", {unmet} still to play" if unmet > 0 else "")
        + f" &middot; {entered} reported by coaches, {len(duals) - entered} imported"
        + (f" &middot; <b>{contested} disputed</b>" if contested else "")
        + ".<br>A disputed result still counts; it is flagged so the committee "
          "knows to check it.</div>")

    team_pages = "".join(
        render_team_page(t, load_ladder(year, gender_id, t["school_id"]), duals)
        for t in teams)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(league)} {GENDERS[gender_id]} {year} — Seeding Packet</title>
<style>{STYLE}</style>
</head>
<body>
<div class="toolbar">
  <button onclick="window.print()">Print</button>
  <a href="../../coach.html">Report results</a>
  <a href="index.html">All packets</a>
  <span style="margin-left:auto;color:#666">Letter portrait &middot; print to PDF to share</span>
</div>

<div class="page">
  <h1>{esc(league)} &middot; {GENDERS[gender_id]}</h1>
  <p class="sub">{year} season seeding packet &middot; {esc(teams[0].get('classification'))}</p>
  {completeness}
  <h2>Standings</h2>
  {render_standings(teams)}
  <h2>Head to head</h2>
  {render_h2h(teams, duals)}
  <h2>Bracket</h2>
  {render_bracket(teams)}
</div>

{team_pages}

<div class="page">
  <h1>Scorecards</h1>
  <p class="sub">Every league dual, flight by flight.</p>
  {render_scorecards(duals)}
</div>
</body>
</html>"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--league", help="build one league only")
    args = ap.parse_args(argv)

    entries = load_rankings(args.year)
    if not entries:
        print(f"No ranking entries for {args.year}; nothing to build.")
        return 0

    out_dir = os.path.join(OUT_ROOT, str(args.year))
    os.makedirs(out_dir, exist_ok=True)

    leagues = sorted({e["league"] for e in entries if e.get("league")})
    if args.league:
        leagues = [l for l in leagues if l == args.league]
        if not leagues:
            print(f"No league named {args.league!r} in {args.year}", file=sys.stderr)
            return 1

    built = []
    for league in leagues:
        for gender_id in (1, 2):
            page = build_league(args.year, league, gender_id, entries)
            if not page:
                continue
            slug = slugify(league, GENDERS[gender_id])
            path = os.path.join(out_dir, f"{slug}.html")
            with open(path, "w", encoding="utf-8") as f:
                f.write(page)
            built.append((league, GENDERS[gender_id], f"{slug}.html"))

    index_rows = "".join(
        f"<tr><td>{esc(l)}</td><td>{esc(g)}</td>"
        f"<td><a href='{esc(href)}'>Open</a></td></tr>"
        for l, g, href in built)
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{args.year} Seeding Packets — Oregon HS Tennis</title>
<style>{STYLE}</style></head>
<body><div class="page">
<h1>{args.year} seeding packets</h1>
<p class="sub">One printable packet per league: standings, head to head, each
team's ladder and flight records, and every dual as a scorecard.</p>
<table><thead><tr><th>League</th><th>Gender</th><th></th></tr></thead>
<tbody>{index_rows}</tbody></table>
</div></body></html>""")

    print(f"seeding packets: wrote {len(built)} league pages to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
