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

Also captures each county's prior project_count before refreshing, writing
it back as previous_project_count/delta (see
db/migrations/006_county_coverage_diff.sql) so the Insights dashboard can
show week-over-week movement, not just a point-in-time snapshot.

Usage:
    python3 scripts/compute-county-coverage.py --database-url postgresql://...
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_identity import classify_source as classify  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--database-url",
        default=os.environ.get(
            "DATABASE_URL", "postgresql://specindex:specindex@localhost:5432/specindex"
        ),
    )
    ap.add_argument(
        "--apply-migration",
        action="store_true",
        help="Run db/migrations/004_county_coverage.sql and 006_county_coverage_diff.sql first",
    )
    args = ap.parse_args()

    conn = psycopg2.connect(args.database_url)
    try:
        with conn.cursor() as cur:
            if args.apply_migration:
                from pathlib import Path

                migrations_dir = Path(__file__).resolve().parents[1] / "db" / "migrations"
                for name in ("004_county_coverage.sql", "006_county_coverage_diff.sql"):
                    cur.execute((migrations_dir / name).read_text(encoding="utf-8"))
                conn.commit()

            # Capture pre-refresh counts for week-over-week diffing before
            # they're wiped by the TRUNCATE below.
            cur.execute("SELECT state, county, project_count FROM county_coverage")
            previous_counts = {(state, county): count for state, county, count in cur.fetchall()}

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
                    previous_counts.get((state, county)),
                    (v["count"] - previous_counts[(state, county)])
                    if (state, county) in previous_counts
                    else None,
                )
                for (state, county), v in agg.items()
            ]

            cur.execute("TRUNCATE county_coverage")
            execute_values(
                cur,
                "INSERT INTO county_coverage "
                "(state, county, project_count, sources, coverage_type, previous_project_count, delta) "
                "VALUES %s",
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
