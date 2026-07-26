#!/usr/bin/env python3
"""Compute per-state data quality metrics and write them to Cloud SQL's
state_quality table (see db/migrations/005_state_quality.sql).

"Quality" here means field completeness (does a project have a city,
estimated value, general contractor, and opened/announced date) and
freshness (how old is the newest project we have for that state). A state
with low completeness usually means its wired source(s) have a sparse
schema (e.g. GA's Forsyth County source has no city/value/contractor
fields at all); a state with a large freshness_days usually means its pull
script hasn't run recently or the underlying source stopped updating.

Duplicate rate is deliberately not computed here -- see the migration file
for why.

Run this after any corpus reload (scripts/load-corpus-to-postgres.py) to
keep the table current -- it reads directly from the live `projects` table,
not from local JSON files.

Usage:
    python3 scripts/compute-state-quality.py --database-url postgresql://...
"""

from __future__ import annotations

import argparse
import os

import psycopg2
from psycopg2.extras import execute_values

QUALITY_QUERY = """
    SELECT
        state,
        COUNT(*) AS total_projects,
        100.0 * COUNT(*) FILTER (WHERE city IS NOT NULL AND city != '') / COUNT(*) AS pct_has_city,
        100.0 * COUNT(*) FILTER (WHERE estimated_value_usd IS NOT NULL) / COUNT(*) AS pct_has_value,
        100.0 * COUNT(*) FILTER (WHERE general_contractor IS NOT NULL AND general_contractor != '') / COUNT(*) AS pct_has_contractor,
        100.0 * COUNT(*) FILTER (WHERE opened_or_announced_date IS NOT NULL) / COUNT(*) AS pct_has_date,
        (CURRENT_DATE - MAX(opened_or_announced_date))::INTEGER AS freshness_days
    FROM projects
    WHERE state IS NOT NULL
    GROUP BY state
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--database-url",
        default=os.environ.get(
            "DATABASE_URL", "postgresql://specindex:specindex@localhost:5432/specindex"
        ),
    )
    ap.add_argument("--apply-migration", action="store_true", help="Run db/migrations/005_state_quality.sql first")
    args = ap.parse_args()

    conn = psycopg2.connect(args.database_url)
    try:
        with conn.cursor() as cur:
            if args.apply_migration:
                from pathlib import Path

                migration = Path(__file__).resolve().parents[1] / "db" / "migrations" / "005_state_quality.sql"
                cur.execute(migration.read_text(encoding="utf-8"))
                conn.commit()

            cur.execute(QUALITY_QUERY)
            rows = cur.fetchall()

            cur.execute("TRUNCATE state_quality")
            execute_values(
                cur,
                "INSERT INTO state_quality "
                "(state, total_projects, pct_has_city, pct_has_value, pct_has_contractor, pct_has_date, freshness_days) "
                "VALUES %s",
                rows,
                page_size=500,
            )
        conn.commit()
    finally:
        conn.close()

    print(f"Computed quality metrics for {len(rows)} states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
