#!/usr/bin/env python3
"""Compute the lead score (intent + pipeline depth + engagement + territory
breadth + recency) and write it to lead_scores (migration 038). Mirrors
scripts/compute-project-scores.py's pattern exactly: pure functions per
component, each stored separately so the breakdown is visible, not just
the total (docs/architecture-2026/03-growth.md §3a).

  intent_score          (0-35): contact_submissions exists at all for this contact
  pipeline_depth_score  (0-25): user_tracked_projects count + stage mix
  engagement_score      (0-20): ask_log row count
  territory_score       (0-10): territory_states + categories array length
  recency_score         (0-100): exponential decay factor (125-day half-life,
                                  on the most recent of tracked-project/ask/
                                  demo activity), expressed as a percentage --
                                  NOT an additive component

  score = round((intent + pipeline_depth + engagement + territory) * decay)
  -- recency is multiplicative against the total, not additive (growth doc's
  own Gemini review flagged additive recency as a real flaw: a 6-month-old
  abandoned demo request would keep its full 35 intent points forever)

Reads crm_contacts (migration 026), user_tracked_projects, ask_log
(migration 036), user_profiles.

Usage:
    python3 scripts/compute-lead-scores.py --database-url postgresql://...
"""

from __future__ import annotations

import argparse
import math
import os
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

RECENCY_HALF_LIFE_DAYS = 125

STAGE_WEIGHTS = {"watching": 1, "contacted": 2, "quoted": 3, "won": 4, "lost": 1}


def intent_score(has_demo_request: bool) -> int:
    return 35 if has_demo_request else 0


def pipeline_depth_score(tracked_stages: list[str]) -> int:
    if not tracked_stages:
        return 0
    weighted = sum(STAGE_WEIGHTS.get(s, 1) for s in tracked_stages)
    # Same log-scale-and-cap shape as compute-project-scores.py's
    # value_score -- diminishing returns past a handful of tracked
    # projects, not a straight linear count.
    return round(25 * min(1.0, math.log10(weighted + 1) / math.log10(20)))


def engagement_score(ask_count: int) -> int:
    return round(20 * min(1.0, math.log10(ask_count + 1) / math.log10(10)))


def territory_score(territory_states: list[str], categories: list[str]) -> int:
    breadth = len(territory_states or []) + len(categories or [])
    return round(10 * min(1.0, breadth / 8))


def recency_decay(most_recent: datetime | None) -> float:
    """Multiplicative decay factor (0-1) applied to the TOTAL score, not an
    additive 0-10 component -- growth doc's own Gemini review flagged the
    additive design as a real flaw (a 6-month-old abandoned demo request
    would keep its full 35 intent points forever) and this was missed on
    first build; caught by a second review pass and fixed here."""
    if most_recent is None:
        return 0.0
    if most_recent.tzinfo is None:
        most_recent = most_recent.replace(tzinfo=timezone.utc)
    days_since = max(0, (datetime.now(timezone.utc) - most_recent).days)
    return math.exp(-days_since / RECENCY_HALF_LIFE_DAYS)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", "postgresql://specindex:specindex@localhost:5432/specindex"),
    )
    ap.add_argument("--apply-migration", action="store_true")
    args = ap.parse_args()

    conn = psycopg2.connect(args.database_url)
    try:
        if args.apply_migration:
            from pathlib import Path

            migration = Path(__file__).resolve().parents[1] / "db" / "migrations" / "038_p3_seams.sql"
            with conn.cursor() as cur:
                cur.execute(migration.read_text(encoding="utf-8"))
            conn.commit()

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT contact_key, territory_states, categories, demo_requested_at,
                       onboarded_at
                FROM crm_contacts
                """
            )
            contacts = cur.fetchall()

            # firebase_uid == contact_key for a real signed-in user (crm_contacts'
            # own COALESCE, see migration 026) -- synthetic "anon-<md5>" keys never
            # match a real firebase_uid, so tracked/ask activity naturally comes
            # back empty for them, which is correct (an anonymous demo-form lead
            # has no tracked pipeline or ask history to score).
            cur.execute(
                "SELECT firebase_uid, stage, updated_at FROM user_tracked_projects"
            )
            tracked_by_uid: dict[str, list[dict]] = {}
            for r in cur.fetchall():
                tracked_by_uid.setdefault(r["firebase_uid"], []).append(r)

            cur.execute("SELECT firebase_uid, count(*) AS n, max(asked_at) AS last_asked FROM ask_log GROUP BY firebase_uid")
            ask_by_uid = {r["firebase_uid"]: r for r in cur.fetchall()}

        rows_written = 0
        with conn.cursor() as cur:
            for c in contacts:
                key = c["contact_key"]
                tracked = tracked_by_uid.get(key, [])
                ask = ask_by_uid.get(key)

                i_score = intent_score(c["demo_requested_at"] is not None)
                p_score = pipeline_depth_score([t["stage"] for t in tracked])
                e_score = engagement_score(ask["n"] if ask else 0)
                t_score = territory_score(c["territory_states"] or [], c["categories"] or [])

                candidates = [c["demo_requested_at"]]
                if tracked:
                    candidates.append(max(t["updated_at"] for t in tracked))
                if ask:
                    candidates.append(ask["last_asked"])
                most_recent = max((d for d in candidates if d is not None), default=None)
                decay = recency_decay(most_recent)
                # recency_score stored as the decay factor expressed 0-100
                # (not a points component) -- the actual score impact is the
                # multiplication below, this column exists so a human can
                # still see "how stale is this lead" at a glance.
                r_score = round(100 * decay)

                total = round((i_score + p_score + e_score + t_score) * decay)

                cur.execute(
                    """
                    INSERT INTO lead_scores
                        (contact_key, score, intent_score, pipeline_depth_score,
                         engagement_score, territory_score, recency_score, computed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (contact_key) DO UPDATE SET
                        score = EXCLUDED.score,
                        intent_score = EXCLUDED.intent_score,
                        pipeline_depth_score = EXCLUDED.pipeline_depth_score,
                        engagement_score = EXCLUDED.engagement_score,
                        territory_score = EXCLUDED.territory_score,
                        recency_score = EXCLUDED.recency_score,
                        computed_at = now()
                    """,
                    (key, total, i_score, p_score, e_score, t_score, r_score),
                )
                rows_written += 1
        conn.commit()
        print(f"Wrote {rows_written} lead score(s).")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
