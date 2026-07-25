#!/usr/bin/env python3
"""Orchestrate nationwide commercial project capture.

Strategy (tiered — not every county portal is scraped individually):
  Tier 1: State economic development / governor press releases
  Tier 2: REBusinessOnline, BLDUP, ConstructConnect public news
  Tier 3: Major metro permit portals (Accela, ePermits) where accessible
  Tier 4: City/county planning commission agendas and developer announcements

Each state is captured to data/states/{code}.json, then merged via merge-national-corpus.py.

Usage:
  python3 scripts/migrate-georgia-to-states.py   # one-time GA migration
  python3 scripts/merge-national-corpus.py       # rebuild national JSON
  python3 scripts/capture-national-projects.py --merge-only
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATES_DIR = ROOT / "data" / "states"
MERGE = ROOT / "scripts" / "merge-national-corpus.py"

ALL_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
]

DATE_RANGE = "2026-04-26 to 2026-07-24 (last 90 days)"


def status() -> dict:
    covered = []
    missing = []
    counts: dict[str, int] = {}
    for code in ALL_STATES:
        path = STATES_DIR / f"{code.lower()}.json"
        if path.exists():
            import json
            data = json.loads(path.read_text())
            n = len(data.get("projects", []))
            counts[code] = n
            covered.append(code)
        else:
            missing.append(code)
    return {"covered": covered, "missing": missing, "counts": counts}


def merge() -> int:
    return subprocess.call([sys.executable, str(MERGE)])


def main() -> int:
    parser = argparse.ArgumentParser(description="National project capture orchestrator")
    parser.add_argument("--merge-only", action="store_true", help="Only run merge step")
    parser.add_argument("--status", action="store_true", help="Show coverage status")
    args = parser.parse_args()

    if args.status:
        s = status()
        print(f"Covered: {len(s['covered'])}/50 states")
        for code in sorted(s["counts"], key=lambda c: s["counts"][c], reverse=True):
            print(f"  {code}: {s['counts'][code]} projects")
        if s["missing"]:
            print(f"Missing: {', '.join(s['missing'])}")
        return 0

    if args.merge_only:
        return merge()

    s = status()
    print(f"States with data: {len(s['covered'])}/50")
    print(f"Date range: {DATE_RANGE}")
    print("Per-state files live in data/states/{code}.json")
    print("Run research agents or manual curation, then: --merge-only")
    return merge()


if __name__ == "__main__":
    raise SystemExit(main())
