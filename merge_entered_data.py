#!/usr/bin/env python3
"""Merge coach-entered duals over the scraped TennisReporting data.

Reads the bundle written by `export_entered_meets.py` and rewrites
`data/<year>/school_<id>_gender_<g>.json` so the entered version of a dual
replaces the scraped one. After this runs, `generate_site.py` sees a single
merged season and needs to know nothing about where any of it came from.

Pure function of (scrape directory, bundle) — no database, no network. That is
deliberate: a Postgres outage during CI degrades to "the site builds from the
scrape alone" rather than failing the build, and the merge can be tested against
fixtures without provisioning anything.

Usage:
    python merge_entered_data.py --year 2027
    python merge_entered_data.py --year 2027 --dry-run    # report, write nothing

JV results are written to `data_jv/<year>/` rather than `data/<year>/`.
`build_rankings` globs `school_*_gender_*.json` and reads the gender from
`stem.split('_')[3]`, so a `_jv` filename suffix would parse cleanly and fold
sub-varsity results into the varsity rankings. A separate directory is the only
safe place for them.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from collections import defaultdict

from entered_shape import is_reserved_meet

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
JV_DATA_DIR = os.path.join(ROOT, "data_jv")
BUNDLE_DIR = os.path.join(ROOT, "entered")

# Scraped meetDateTime values are UTC and a late match can roll past local
# midnight, so the scraped date for a dual is sometimes one day after the date a
# coach enters. Treat a same-pair dual within a day as the same dual, and log
# every time the tolerance is what caught it — a systematic drift would mean the
# entered dates are wrong, not the scraped ones.
DATE_TOLERANCE_DAYS = 1


def meet_date(meet: dict) -> dt.date | None:
    raw = (meet.get("meetDateTime") or "")[:10]
    try:
        return dt.date.fromisoformat(raw)
    except ValueError:
        return None


def dual_pair(meet: dict) -> tuple[int, int] | None:
    """The unordered school pair, or None when this is not a two-team meet.

    Mirrors the shape test in `dedupe_meets` (generate_site.py:351) rather than
    `is_dual_match`: we only ever need to identify a dual we might be replacing,
    and the title heuristics there are about excluding tournaments from the
    rankings, which is a separate question.
    """
    schools = meet.get("schools") or {}
    winners = schools.get("winners") or []
    losers = schools.get("losers") or []
    if len(winners) != 1 or len(losers) != 1:
        return None
    a, b = winners[0].get("id"), losers[0].get("id")
    if a is None or b is None:
        return None
    return (min(a, b), max(a, b))


def _school_stub(meet: dict, school_id: int) -> dict:
    """The `school` block for a file we are creating from scratch."""
    for side in ("winners", "losers"):
        for s in (meet.get("schools") or {}).get(side, []) or []:
            if s.get("id") == school_id:
                return {"id": school_id, "name": s.get("name") or "", "logo": s.get("logo")}
    return {"id": school_id, "name": "", "logo": None}


def recompute_overall_record(meets: list[dict], school_id: int) -> dict:
    """Rebuild the `overallRecord` block from the merged meet list.

    TennisReporting supplies this field and `build_lineup_data.build_team` reads
    it straight through for display, so replacing a dual without touching it
    would leave the header contradicting the match log underneath.
    """
    win = loss = tie = 0
    for meet in meets:
        if dual_pair(meet) is None:
            continue
        schools = meet.get("schools") or {}
        mine = other = None
        for side in ("winners", "losers"):
            for s in schools.get(side) or []:
                if s.get("id") == school_id:
                    mine = s.get("score")
                else:
                    other = s.get("score")
        if mine is None or other is None:
            continue
        if mine > other:
            win += 1
        elif mine < other:
            loss += 1
        else:
            winner = meet.get("winnerSchoolId")
            if winner is None:
                tie += 1
            elif winner == school_id:
                win += 1
            else:
                loss += 1
    return {"win": win, "loss": loss, "tie": tie}


def _existing_files(base: str, year: int) -> list[str]:
    year_dir = os.path.join(base, str(year))
    if not os.path.isdir(year_dir):
        return []
    return [os.path.join(year_dir, n) for n in sorted(os.listdir(year_dir))
            if n.startswith("school_") and n.endswith(".json")]


def _file_key(base: str, path: str) -> tuple[str, int, int] | None:
    parts = os.path.splitext(os.path.basename(path))[0].split("_")
    try:
        return (base, int(parts[1]), int(parts[3]))
    except (IndexError, ValueError):
        return None


def _has_reserved_meet(path: str) -> bool:
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return False
    return any(is_reserved_meet(m) for m in doc.get("meets") or [])


def load_bundle(year: int) -> list[dict]:
    path = os.path.join(BUNDLE_DIR, str(year), "entered_meets.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        bundle = json.load(f)
    return bundle.get("meets") or []


def merge_year(year: int, dry_run: bool = False) -> dict:
    """Merge the year's bundle into the scrape. Returns a summary dict."""
    meets = load_bundle(year)
    stats = {
        "entered_meets": len(meets),
        "files_written": 0,
        "scraped_replaced": 0,
        "date_skew_matches": 0,
        "files_created": 0,
        "jv_meets": 0,
    }

    # An entered dual belongs in both schools' files, the same way the scraper
    # writes each meet into both sides.
    by_file: dict[tuple[str, int, int], list[dict]] = defaultdict(list)
    for meet in meets:
        gender_id = None
        for mt in ("Singles", "Doubles"):
            for line in (meet.get("matches") or {}).get(mt, []) or []:
                gender_id = line.get("genderId")
                break
            if gender_id:
                break
        if gender_id is None:
            print(f"  WARNING: meet {meet.get('id')} has no lines; skipped")
            continue
        base = JV_DATA_DIR if meet.get("level") == "jv" else DATA_DIR
        if base is JV_DATA_DIR:
            stats["jv_meets"] += 1
        pair = dual_pair(meet)
        if pair is None:
            print(f"  WARNING: meet {meet.get('id')} is not a two-team dual; skipped")
            continue
        for school_id in pair:
            by_file[(base, school_id, gender_id)].append(meet)

    # The overlay is fully derived from the bundle, so a file that still carries
    # a compiled meet has to be visited even when the bundle no longer mentions
    # it — otherwise voiding a dual in the database would leave it on the site
    # forever. Files with no entered data are untouched and stay byte-identical.
    for base in (DATA_DIR, JV_DATA_DIR):
        for path in _existing_files(base, year):
            key = _file_key(base, path)
            if key and key not in by_file and _has_reserved_meet(path):
                by_file[key] = []

    for (base, school_id, gender_id), entered in sorted(by_file.items(), key=lambda kv: kv[0][1:]):
        year_dir = os.path.join(base, str(year))
        path = os.path.join(year_dir, f"school_{school_id}_gender_{gender_id}.json")

        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
        else:
            doc = {
                "school": _school_stub(entered[0], school_id),
                "coaches": [],
                "overallRecord": {"win": 0, "loss": 0, "tie": 0},
                "meets": [],
            }
            stats["files_created"] += 1

        existing = doc.get("meets") or []

        # Drop anything we compiled on an earlier run. This is what makes the
        # merge idempotent: our own output is always regenerated from the bundle,
        # never accumulated.
        existing = [m for m in existing if not is_reserved_meet(m)]

        wanted = {}
        for meet in entered:
            d = meet_date(meet)
            pair = dual_pair(meet)
            if d and pair:
                wanted[pair] = d

        kept = []
        for meet in existing:
            pair = dual_pair(meet)
            d = meet_date(meet)
            if pair is not None and pair in wanted and d is not None:
                delta = abs((d - wanted[pair]).days)
                if delta <= DATE_TOLERANCE_DAYS:
                    stats["scraped_replaced"] += 1
                    if delta > 0:
                        stats["date_skew_matches"] += 1
                        print(
                            f"  date skew: school {school_id} vs {pair} — "
                            f"scraped {d}, entered {wanted[pair]}"
                        )
                    continue
            kept.append(meet)

        merged = kept + entered
        merged.sort(key=lambda m: ((m.get("meetDateTime") or ""), m.get("id") or 0))

        # A dual surviving twice would double-count in every metric, which is the
        # one failure here that corrupts silently. dedupe_meets would catch it on
        # load, but by then the bad file is committed.
        seen = {}
        for meet in merged:
            pair = dual_pair(meet)
            d = meet_date(meet)
            if pair is None or d is None:
                continue
            key = (d, pair)
            if key in seen:
                raise AssertionError(
                    f"{path}: two dual meets share {key} "
                    f"(ids {seen[key]} and {meet.get('id')})"
                )
            seen[key] = meet.get("id")

        doc["meets"] = merged
        doc["overallRecord"] = recompute_overall_record(merged, school_id)

        # Write only on a real change, so a build with nothing new leaves the
        # tree byte-identical and produces no commit. `indent=2` matches
        # fetch_data.save_school_data, keeping the git diff readable.
        rendered = json.dumps(doc, indent=2)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                if f.read() == rendered:
                    continue
        if not dry_run:
            os.makedirs(year_dir, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(rendered)
        stats["files_written"] += 1

    verb = "would write" if dry_run else "wrote"
    print(
        f"{year}: {stats['entered_meets']} entered duals, {verb} {stats['files_written']} "
        f"files ({stats['files_created']} new), replaced {stats['scraped_replaced']} "
        f"scraped duals ({stats['date_skew_matches']} matched only via the "
        f"±{DATE_TOLERANCE_DAYS}-day tolerance)"
    )
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would change without writing")
    args = ap.parse_args(argv)
    merge_year(args.year, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
