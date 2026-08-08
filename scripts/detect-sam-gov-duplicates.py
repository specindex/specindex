#!/usr/bin/env python3
"""Read-only detection of SAM.gov duplicate-amendment project rows.

Root cause (found 2026-08-07/08, fixed in sam_gov_provider.py): project ids
for SAM.gov-sourced projects were keyed on NoticeId, which SAM.gov mints
fresh for every amendment/repost of the same solicitation -- one VA
solicitation (Y1DZ Building 9A EHRM, Dublin GA) had 7 separate project rows,
each with a different partial document set. This script only SELECTs; it
makes no writes, so it's safe to run against production to measure how
widespread the problem is before anyone decides on a cleanup/merge pass.

Groups projects whose id matches the {state}-sam-{...} pattern and whose
name is identical, which is what NoticeId-keyed amendments of the same
solicitation look like (same title, different id suffix).

Usage:
    python3 scripts/detect-sam-gov-duplicates.py --database-url postgresql://...
"""

from __future__ import annotations

import argparse
import os

import psycopg2
import psycopg2.extras


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--database-url",
        default=os.environ.get(
            "DATABASE_URL", "postgresql://specindex:specindex@localhost:5432/specindex"
        ),
    )
    ap.add_argument(
        "--limit-groups", type=int, default=50,
        help="max duplicate groups to print in detail (default 50)",
    )
    args = ap.parse_args()

    conn = psycopg2.connect(args.database_url)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT p.name,
                       count(*)                    AS row_count,
                       array_agg(p.project_id ORDER BY p.project_id) AS project_ids,
                       coalesce(sum(d.n_docs), 0)   AS total_docs_across_rows
                FROM projects p
                LEFT JOIN (
                    SELECT project_sk, count(*) AS n_docs
                    FROM project_document_files GROUP BY project_sk
                ) d ON d.project_sk = p.project_sk
                WHERE p.project_id LIKE '%-sam-%'
                GROUP BY p.name
                HAVING count(*) > 1
                ORDER BY count(*) DESC
                """
            )
            groups = cur.fetchall()

        total_groups = len(groups)
        total_excess_rows = sum(g["row_count"] - 1 for g in groups)
        total_docs_scattered = sum(g["total_docs_across_rows"] for g in groups)

        print(f"SAM.gov duplicate-amendment groups found: {total_groups:,}")
        print(f"Excess rows (row_count - 1 summed across groups): {total_excess_rows:,}")
        print(f"Documents currently scattered across those duplicate rows: {total_docs_scattered:,}")
        print()
        print(f"Top {min(args.limit_groups, total_groups)} groups by row count:")
        for g in groups[: args.limit_groups]:
            print(f"  {g['row_count']}x  {g['total_docs_across_rows']:>4} docs total  {g['name'][:70]}")
            for pid in g["project_ids"]:
                print(f"        {pid}")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
