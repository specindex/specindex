#!/usr/bin/env python3
"""Compute per-(state, county) project coverage and write it to Cloud SQL's
county_coverage table (see db/migrations/004_county_coverage.sql).

Source attribution isn't a stored column on `projects` -- it's derived here
from each project_id's prefix (e.g. "ga-fulton-...", "nc-mecklenburg-...",
"ga-dri-...", "ga-sam-...", falling back to "Prior research" for anything
that doesn't match a known prefix). "Deep" coverage means at least one
dedicated local permit feed (a specific city/county ArcGIS or Accela
source) contributed to that county; "thin" means only broad statewide or
federal sources did (DRI, USAspending, SAM.gov, hand-curated research).

Run this after any corpus reload (scripts/load-corpus-to-postgres.py) to
keep the coverage table current -- it reads directly from the live
`projects` table, not from local JSON files.

Usage:
    python3 scripts/compute-county-coverage.py --database-url postgresql://...
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict

import psycopg2
from psycopg2.extras import execute_values

# (prefix, label, is_dedicated_local) -- order matters, first match wins.
# Add a new tuple here whenever a new state/source-specific pull script is
# built; DRI-alike statewide filings and hand-curated research default to
# "thin" via the fallback at the bottom of classify().
SOURCE_PATTERNS: list[tuple[str, str, bool]] = [
    ("ga-fulton-", "Fulton County (ArcGIS)", True),
    ("ga-alpharetta-", "Alpharetta (ArcGIS)", True),
    ("ga-johnscreek-", "Johns Creek (ArcGIS)", True),
    ("ga-marietta-", "Marietta (ArcGIS)", True),
    ("ga-savannah-", "Savannah/SAGIS (ArcGIS)", True),
    ("ga-atlanta-", "Atlanta (Accela)", True),
    ("ga-gwinnett-", "Gwinnett (Accela)", True),
    ("ga-cobb-", "Cobb (Accela)", True),
    ("ga-dri-", "Georgia DRI (statewide)", False),
    ("nc-mecklenburg-", "Mecklenburg County (ArcGIS)", True),
    ("nc-wake-", "Wake County (ArcGIS)", True),
]

FEDERAL_HINT = re.compile(r"-(sam|usaspending)-", re.I)


def classify(project_id: str) -> tuple[str, bool]:
    """Return (source_label, is_dedicated_local)."""
    for prefix, label, is_local in SOURCE_PATTERNS:
        if project_id.startswith(prefix):
            return label, is_local
    if FEDERAL_HINT.search(project_id):
        return "Federal (SAM.gov / USAspending)", False
    return "Prior research", False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--database-url",
        default=os.environ.get(
            "DATABASE_URL", "postgresql://specindex:specindex@localhost:5432/specindex"
        ),
    )
    ap.add_argument("--apply-migration", action="store_true", help="Run db/migrations/004_county_coverage.sql first")
    args = ap.parse_args()

    conn = psycopg2.connect(args.database_url)
    try:
        with conn.cursor() as cur:
            if args.apply_migration:
                from pathlib import Path

                migration = Path(__file__).resolve().parents[1] / "db" / "migrations" / "004_county_coverage.sql"
                cur.execute(migration.read_text(encoding="utf-8"))
                conn.commit()

            cur.execute(
                "SELECT project_id, state, county FROM projects "
                "WHERE county IS NOT NULL AND county != '' AND state IS NOT NULL"
            )
            rows = cur.fetchall()

            agg: dict[tuple[str, str], dict] = defaultdict(
                lambda: {"count": 0, "sources": set(), "deep": False}
            )
            for project_id, state, county in rows:
                label, is_local = classify(project_id)
                key = (state, county)
                agg[key]["count"] += 1
                agg[key]["sources"].add(label)
                agg[key]["deep"] = agg[key]["deep"] or is_local

            coverage_rows = [
                (
                    state,
                    county,
                    v["count"],
                    sorted(v["sources"]),
                    "deep" if v["deep"] else "thin",
                )
                for (state, county), v in agg.items()
            ]

            cur.execute("TRUNCATE county_coverage")
            execute_values(
                cur,
                "INSERT INTO county_coverage (state, county, project_count, sources, coverage_type) VALUES %s",
                coverage_rows,
                page_size=500,
            )
        conn.commit()
    finally:
        conn.close()

    deep = sum(1 for r in coverage_rows if r[4] == "deep")
    print(f"Computed coverage for {len(coverage_rows)} (state, county) pairs across {len({r[0] for r in coverage_rows})} states")
    print(f"  deep: {deep}, thin: {len(coverage_rows) - deep}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
