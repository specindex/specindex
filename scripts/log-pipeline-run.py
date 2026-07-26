#!/usr/bin/env python3
"""Log one pipeline run to Cloud SQL's pipeline_runs table (see
db/migrations/007_pipeline_runs.sql) -- called as the last step of
.github/workflows/pull-national.yml and pull-state.yml, using the same
Cloud SQL Proxy connection already open for the load/coverage/quality
steps in that run.

overall_status is derived from the --step outcomes: 'success' if every
step succeeded, 'failure' if every step failed, 'partial_failure'
otherwise -- this is what the ops dashboard sorts/colors by.

Usage:
    python3 scripts/log-pipeline-run.py \\
        --workflow pull-national --run-url https://github.com/.../runs/123 \\
        --projects-before 7252 --projects-after 7260 \\
        --top-movers "GA/Fulton: +5; NC/Wake: +3" \\
        --step pull_sam_ga=success --step rebuild_ga=success ...
"""

from __future__ import annotations

import argparse
import json
import os

import psycopg2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workflow", required=True)
    ap.add_argument("--run-url", default=None)
    ap.add_argument("--projects-before", type=int, default=None)
    ap.add_argument("--projects-after", type=int, default=None)
    ap.add_argument("--top-movers", default=None)
    ap.add_argument(
        "--step",
        action="append",
        default=[],
        metavar="NAME=OUTCOME",
        help="Repeatable. e.g. --step pull_sam_ga=success",
    )
    ap.add_argument(
        "--database-url",
        default=os.environ.get(
            "DATABASE_URL", "postgresql://specindex:specindex@localhost:5432/specindex"
        ),
    )
    ap.add_argument("--apply-migration", action="store_true")
    args = ap.parse_args()

    step_outcomes: dict[str, str] = {}
    for item in args.step:
        if "=" not in item:
            continue
        name, outcome = item.split("=", 1)
        step_outcomes[name] = outcome

    outcomes = set(step_outcomes.values())
    if outcomes and outcomes == {"success"}:
        overall = "success"
    elif outcomes and outcomes == {"failure"}:
        overall = "failure"
    else:
        overall = "partial_failure"

    conn = psycopg2.connect(args.database_url)
    try:
        with conn.cursor() as cur:
            if args.apply_migration:
                from pathlib import Path

                migration = (
                    Path(__file__).resolve().parents[1] / "db" / "migrations" / "007_pipeline_runs.sql"
                )
                cur.execute(migration.read_text(encoding="utf-8"))
                conn.commit()

            cur.execute(
                """
                INSERT INTO pipeline_runs
                    (workflow, run_url, projects_before, projects_after, step_outcomes, top_movers, overall_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    args.workflow,
                    args.run_url,
                    args.projects_before,
                    args.projects_after,
                    json.dumps(step_outcomes),
                    args.top_movers,
                    overall,
                ),
            )
        conn.commit()
    finally:
        conn.close()

    print(f"Logged {args.workflow} run: {overall}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
