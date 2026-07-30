"""Fuzzy-matching merge-proposal batch job (docs/architecture-2026/
01-data-platform.md P3). Uses pg_trgm similarity() over each entity
directory table's normalized_name (scoped by state, since manufacturers/
GCs sharing a common name across states are legitimately different
companies -- migration 033's UNIQUE (normalized_name, state) already
encodes this).

PROPOSAL, not auto-merge, by default -- this is a batch that flags likely
duplicates for a human to confirm, not one that silently rewrites the
directory. --apply actually merges (reassigns every join-table row from
the duplicate to the canonical entity, records the mapping in
entity_aliases so a future ingestion run doesn't recreate the duplicate
under the old name, then deletes the now-empty duplicate row) -- run
without it first, review the proposals, then re-run with --apply once
they look right.

Usage:
    python3 scripts/find-entity-duplicates.py --database-url postgresql://...
    python3 scripts/find-entity-duplicates.py --apply --min-similarity 0.7
"""

from __future__ import annotations

import argparse
import json
import os

import psycopg2
import psycopg2.extras

ENTITY_CONFIG = {
    "manufacturer": {
        "table": "manufacturers",
        "join_table": "project_manufacturers",
        "join_fk": "manufacturer_id",
    },
    "general_contractor": {
        "table": "general_contractors",
        "join_table": "project_general_contractors",
        "join_fk": "general_contractor_id",
    },
    "person": {
        "table": "people",
        "join_table": "project_people",
        "join_fk": "person_id",
    },
}


def find_candidates(cur, entity_type: str, min_similarity: float) -> list[dict]:
    cfg = ENTITY_CONFIG[entity_type]
    table = cfg["table"]
    # Self-join on trigram similarity, same state (or both NULL), a.id <
    # b.id to avoid reporting each pair twice and never a row with itself.
    # Excludes pairs already resolved via entity_aliases in either direction.
    cur.execute(
        f"""
        SELECT a.id AS id_a, a.display_name AS name_a, a.state AS state_a,
               b.id AS id_b, b.display_name AS name_b, b.state AS state_b,
               similarity(a.normalized_name, b.normalized_name) AS sim
        FROM {table} a
        JOIN {table} b
          ON a.id < b.id
         AND a.normalized_name %% b.normalized_name
         AND (a.state = b.state OR (a.state IS NULL AND b.state IS NULL))
        WHERE similarity(a.normalized_name, b.normalized_name) >= %s
          AND NOT EXISTS (
              SELECT 1 FROM entity_aliases ea
              WHERE ea.entity_type = %s
                AND ((ea.deprecated_id = a.id AND ea.canonical_id = b.id)
                  OR (ea.deprecated_id = b.id AND ea.canonical_id = a.id))
          )
        ORDER BY sim DESC
        """,
        (min_similarity, entity_type),
    )
    return [dict(r) for r in cur.fetchall()]


def apply_merge(cur, entity_type: str, deprecated_id: int, canonical_id: int) -> None:
    """Canonical = the LOWER id (older, presumably first-seen entity) --
    an arbitrary but consistent tie-break; deprecated_id always merges
    INTO canonical_id, never the reverse, so re-running find_candidates
    after a merge can't propose merging the same pair backwards."""
    cfg = ENTITY_CONFIG[entity_type]
    join_table, join_fk = cfg["join_table"], cfg["join_fk"]
    table = cfg["table"]

    if join_table == "project_manufacturers":
        # source_field is part of the PK -- ON CONFLICT DO NOTHING handles
        # a project that (rarely) already links to both entities under the
        # same source_field.
        cur.execute(
            f"""
            UPDATE {join_table} SET {join_fk} = %s
            WHERE {join_fk} = %s
              AND NOT EXISTS (
                  SELECT 1 FROM {join_table} x
                  WHERE x.project_sk = {join_table}.project_sk
                    AND x.{join_fk} = %s AND x.source_field = {join_table}.source_field
              )
            """,
            (canonical_id, deprecated_id, canonical_id),
        )
    elif join_table == "project_people":
        cur.execute(
            f"""
            UPDATE {join_table} SET {join_fk} = %s
            WHERE {join_fk} = %s
              AND NOT EXISTS (
                  SELECT 1 FROM {join_table} x
                  WHERE x.project_sk = {join_table}.project_sk
                    AND x.{join_fk} = %s AND x.role = {join_table}.role
              )
            """,
            (canonical_id, deprecated_id, canonical_id),
        )
    else:
        cur.execute(
            f"""
            UPDATE {join_table} SET {join_fk} = %s
            WHERE {join_fk} = %s
              AND NOT EXISTS (
                  SELECT 1 FROM {join_table} x
                  WHERE x.project_sk = {join_table}.project_sk AND x.{join_fk} = %s
              )
            """,
            (canonical_id, deprecated_id, canonical_id),
        )
    cur.execute(f"DELETE FROM {join_table} WHERE {join_fk} = %s", (deprecated_id,))

    cur.execute(
        "INSERT INTO entity_aliases (entity_type, deprecated_id, canonical_id) "
        "VALUES (%s, %s, %s) ON CONFLICT (entity_type, deprecated_id) DO NOTHING",
        (entity_type, deprecated_id, canonical_id),
    )
    cur.execute(f"DELETE FROM {table} WHERE id = %s", (deprecated_id,))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", "postgresql://specindex:specindex@localhost:5432/specindex"),
    )
    ap.add_argument("--min-similarity", type=float, default=0.6)
    ap.add_argument("--apply", action="store_true", help="Actually merge -- default is proposal-only")
    ap.add_argument("--limit", type=int, default=None, help="Cap proposals shown/applied per entity type")
    args = ap.parse_args()

    conn = psycopg2.connect(args.database_url)
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            all_proposals: dict[str, list[dict]] = {}
            for entity_type in ENTITY_CONFIG:
                candidates = find_candidates(cur, entity_type, args.min_similarity)
                if args.limit:
                    candidates = candidates[: args.limit]
                all_proposals[entity_type] = candidates
                print(f"{entity_type}: {len(candidates)} candidate pair(s)")
                for c in candidates[:20]:
                    print(f"  {c['sim']:.2f}  {c['name_a']!r} ({c['state_a']})  <->  {c['name_b']!r} ({c['state_b']})")

        if not args.apply:
            out_path = "data/entity_merge_proposals.json"
            with open(out_path, "w") as f:
                json.dump(all_proposals, f, indent=2, default=str)
            print(f"\nProposal-only run -- wrote {out_path}. Re-run with --apply to merge these.")
            return 0

        with conn.cursor() as cur:
            total_merged = 0
            for entity_type, candidates in all_proposals.items():
                for c in candidates:
                    # canonical = lower id (see apply_merge's docstring)
                    canonical, deprecated = sorted([c["id_a"], c["id_b"]])
                    apply_merge(cur, entity_type, deprecated, canonical)
                    total_merged += 1
        conn.commit()
        print(f"\nApplied {total_merged} merge(s).")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
