#!/usr/bin/env python3
"""Compute the project score (value + recency + news) and write it to
Cloud SQL's project_scores table (see db/migrations/013_project_scores.sql).

v1 formula -- simple, transparent, and meant to be adjusted once it's been
seen against real projects, not a final methodology (see
docs/PROJECT_PAGE_REDESIGN.md, open question #2):

  value_score   (0-40): log-scale on estimated_value_usd, capped at $500M
  recency_score (0-35): exponential decay from opened_or_announced_date,
                        ~125-day half-life
  news_score    (0-25): count of project_news rows, +8/article capped at 25

  score = value_score + recency_score + news_score  (0-100)

Each component is stored separately so the breakdown is visible on the
project page, not just the total -- the whole point of a transparent
score is that a rep can see *why* a project ranks where it does.

Usage:
    python3 scripts/compute-project-scores.py --database-url postgresql://...
"""

from __future__ import annotations

import argparse
import math
import os
from datetime import date

import psycopg2
import psycopg2.extras
from psycopg2.extras import execute_values

VALUE_CAP_LOG10 = math.log10(500_000_000)  # $500M treated as max-relevant
RECENCY_HALF_LIFE_DAYS = 125
NEWS_POINTS_PER_ARTICLE = 8


def value_score(estimated_value_usd: int | None) -> int:
    if not estimated_value_usd or estimated_value_usd <= 0:
        return 0
    ratio = math.log10(estimated_value_usd + 1) / VALUE_CAP_LOG10
    return round(40 * min(1.0, ratio))


def recency_score(opened_or_announced_date: date | None) -> int:
    if not opened_or_announced_date:
        return 0
    days_since = max(0, (date.today() - opened_or_announced_date).days)
    decay = math.exp(-days_since / RECENCY_HALF_LIFE_DAYS)
    return round(35 * decay)


def news_score(article_count: int) -> int:
    return min(25, article_count * NEWS_POINTS_PER_ARTICLE)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--database-url",
        default=os.environ.get(
            "DATABASE_URL", "postgresql://specindex:specindex@localhost:5432/specindex"
        ),
    )
    ap.add_argument("--apply-migration", action="store_true")
    args = ap.parse_args()

    conn = psycopg2.connect(args.database_url)
    try:
        with conn.cursor() as cur:
            if args.apply_migration:
                from pathlib import Path

                migration = (
                    Path(__file__).resolve().parents[1] / "db" / "migrations" / "013_project_scores.sql"
                )
                cur.execute(migration.read_text(encoding="utf-8"))
                conn.commit()

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT p.project_sk, p.estimated_value_usd, p.opened_or_announced_date,
                       count(n.id) AS news_count
                FROM projects p
                LEFT JOIN project_news n ON n.project_sk = p.project_sk
                GROUP BY p.project_sk, p.estimated_value_usd, p.opened_or_announced_date
                """
            )
            projects = cur.fetchall()

        rows = []
        for p in projects:
            v = value_score(p["estimated_value_usd"])
            r = recency_score(p["opened_or_announced_date"])
            n = news_score(p["news_count"])
            rows.append((p["project_sk"], v + r + n, v, r, n))

        with conn.cursor() as cur:
            cur.execute("TRUNCATE project_scores")
            execute_values(
                cur,
                "INSERT INTO project_scores (project_sk, score, value_score, recency_score, news_score) VALUES %s",
                rows,
                page_size=500,
            )
        conn.commit()
    finally:
        conn.close()

    print(f"Computed scores for {len(rows)} projects")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
