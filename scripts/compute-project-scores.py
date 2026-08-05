#!/usr/bin/env python3
"""Compute the project score and write it to Cloud SQL's project_scores table.

v2, 2026-08-05. v1 was value + recency + news, and measurement against the
live corpus found three things wrong with it:

  * NEWS WAS DEAD WEIGHT. news_score could contribute 25 of 100 points and was
    non-zero on FIVE projects out of 591,618. A quarter of the scale sat idle.
    Removed, and the points redistributed to signals that exist.

  * VALUE WAS COMPUTED ON CORRUPT INPUTS. Miami-Dade's value field reports
    $7,863,674,230 for "ALTER - INTERIOR - BEAUTY SALON-BARBER SHOP", and that
    row scored 70 -- the second-highest-scoring project in Florida. 84 projects
    corpus-wide claim over $1B. A score is a ranking, so one bad input does not
    just misprice a row, it puts it in front of a rep instead of real work.
    value_score now sanity-bounds its input and reports the rejection.

  * THE SCORE IGNORED WHAT WE SELL. SpecIndex sells spec POSITION -- is my
    brand basis of design, a listed alternate, or absent, and is the
    substitution window still open. v1 measured project size and age, which is
    what every incumbent already measures.

v2 formula (0-100):

  value_score     (0-30): log-scale on a SANITY-BOUNDED estimated_value_usd
  recency_score   (0-25): exponential decay from opened_or_announced_date
  position_score  (0-45): what we actually sell --
                            30  a basis-of-design manufacturer is NAMED in a
                                document we hold, with a page citation
                            +5  per additional cited finding, capped
                            10  documents held but no manufacturer named yet
                                (a real, sellable "determined absent")
                             0  no documents -- we cannot say anything

position_score is deliberately the largest component. It is also the only one
a competitor cannot copy from a permit feed.

NOTE ON THE CLOCK. recency still decays from the ANNOUNCED date, which is the
wrong clock for this product: what matters is time until the SUBSTITUTION
WINDOW closes. A project announced yesterday whose window shut is useless; an
older one closing next week is urgent. Substitution deadlines are not yet
extracted -- the clause language is present in addenda (proven 2026-08-05), so
this is the next extraction target and recency should be replaced by it, not
merely retuned.

Each component is stored separately so the breakdown is visible on the project
page -- the whole point of a transparent score is that a rep can see *why* a
project ranks where it does.

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

# Above this, the value is not a big project -- it is a broken field. The
# largest single US commercial construction projects run to a few billion, and
# a permit-level record almost never legitimately exceeds this. Miami-Dade
# reports $7.86B for a beauty-salon interior alteration.
VALUE_SANITY_MAX = 2_000_000_000
VALUE_SANITY_MIN = 1_000            # below this it is a fee, not a project cost

rejected_values = 0                 # counted and reported, never silent


def value_score(estimated_value_usd: int | None) -> int:
    """0-30. Rejects implausible inputs rather than ranking on them.

    A score is a ranking, so a corrupt value does not merely misprice one row
    -- it promotes that row above real work. Rejecting to 0 is the
    conservative choice: an unscored real project loses a few places, whereas
    a $7.86B beauty salon takes the top of the list.
    """
    global rejected_values
    if not estimated_value_usd or estimated_value_usd <= 0:
        return 0
    if estimated_value_usd > VALUE_SANITY_MAX or estimated_value_usd < VALUE_SANITY_MIN:
        rejected_values += 1
        return 0
    ratio = math.log10(estimated_value_usd + 1) / VALUE_CAP_LOG10
    return round(30 * min(1.0, ratio))


def recency_score(opened_or_announced_date: date | None) -> int:
    """0-25. See the module docstring: this is the WRONG CLOCK for this
    product and should become time-until-substitution-window-closes."""
    if not opened_or_announced_date:
        return 0
    days_since = max(0, (date.today() - opened_or_announced_date).days)
    decay = math.exp(-days_since / RECENCY_HALF_LIFE_DAYS)
    return round(25 * decay)


def position_score(bod_citations: int, documents_held: int) -> int:
    """0-45. The only component that reflects what SpecIndex actually sells.

    Citation COUNT is the tie-breaker, and it is deliberately a real quantity
    rather than a rounded band -- the previous score produced 82/76/75/75/75/75
    at the top of the list, where position within the ties was arbitrary.

    "Documents held but nobody named" scores 10 rather than 0 because that is
    a genuine, sellable finding -- a determined absence, not a gap. It is the
    answer a rep wants when asking "is anyone specified here yet".
    """
    if bod_citations > 0:
        return min(45, 30 + 5 * (bod_citations - 1))
    if documents_held > 0:
        return 10
    return 0


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
            # Scores EVERY project, not only those with a value. v1 left 71% of
            # the corpus unscored while the UI defaulted to sorting by score,
            # which silently buried the majority of the index.
            cur.execute(
                """
                SELECT p.project_sk,
                       p.estimated_value_usd,
                       p.opened_or_announced_date,
                       coalesce(d.n_docs, 0)      AS documents_held,
                       coalesce(b.n_citations, 0) AS bod_citations
                FROM projects p
                LEFT JOIN (
                    SELECT project_sk, count(*) AS n_docs
                    FROM project_document_files GROUP BY project_sk
                ) d ON d.project_sk = p.project_sk
                LEFT JOIN (
                    SELECT project_sk, count(*) AS n_citations
                    FROM substitution_rulings
                    WHERE document_file_id IS NOT NULL
                    GROUP BY project_sk
                ) b ON b.project_sk = p.project_sk
                """
            )
            projects = cur.fetchall()

        rows = []
        for p in projects:
            v = value_score(p["estimated_value_usd"])
            r = recency_score(p["opened_or_announced_date"])
            pos = position_score(p["bod_citations"], p["documents_held"])
            # news_score is retained in the table as 0 so the column and any
            # existing readers keep working; it is no longer computed. Dropping
            # the column belongs in its own migration, once nothing reads it.
            rows.append((p["project_sk"], v + r + pos, v, r, 0, pos))

        with conn.cursor() as cur:
            cur.execute("ALTER TABLE project_scores ADD COLUMN IF NOT EXISTS position_score INTEGER NOT NULL DEFAULT 0")
            conn.commit()
            cur.execute("TRUNCATE project_scores")
            execute_values(
                cur,
                "INSERT INTO project_scores (project_sk, score, value_score, recency_score, "
                "news_score, position_score) VALUES %s",
                rows,
                page_size=500,
            )
        conn.commit()
        scored = len(rows)
        with_pos = sum(1 for r in rows if r[5] > 0)
        print(f"scored {scored:,} projects (v1 scored 172,120 of 591,618)")
        print(f"  value rejected as implausible : {rejected_values:,}")
        print(f"  with a position signal        : {with_pos:,}")
    finally:
        conn.close()

    print(f"Computed scores for {len(rows)} projects")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
