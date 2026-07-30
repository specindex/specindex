"""Phase-1 heuristic entity normalization batch (docs/architecture-2026/
01-data-platform.md P1). Reads projects.mentioned_brands, .owner,
.architect, .general_contractor and seeds the manufacturers/
general_contractors/people directory tables (migration 033) + their project
join tables.

Deviation from the roadmap doc's literal field list, verified against live
data before shipping (see [[feedback-specindex-data-pipeline]]'s
verify-before-building discipline): the doc names competitor_watch as a
fourth manufacturer source alongside mentioned_brands, but every row is
CSI-division category taxonomy ("elevators", "doors and hardware", "ff&e"
-- see lib/divisions.ts's own docstring: "Category keywords as they appear
in project records"), never a company name. A first real run against 500
live projects populated manufacturers with exactly that noise. Dropped
entirely rather than filtered, since there's no real signal in it to keep.

"Heuristic" means exactly that: lowercase + punctuation-strip + a small
legal-suffix stoplist, not fuzzy matching or LLM entity resolution. Expect
real near-duplicates ("ABC Construction" vs "ABC Construction LLC" only
collapse if the suffix strip catches it) until the P3 pg_trgm merge-proposal
batch and the P4 LLM-assisted resolution pass exist. Run repeatedly as new
projects/enrichment land -- every insert is ON CONFLICT DO NOTHING /
idempotent, so re-running is always safe, not just re-runnable once.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

import psycopg2
import psycopg2.extras

_LEGAL_SUFFIXES = re.compile(
    r"\b(inc|llc|ltd|co|corp|corporation|company|group|pllc|pc|llp)\.?\s*$",
    re.IGNORECASE,
)


def clean_display(raw: str) -> str:
    """Strips stray wrapping quote characters some source records carry
    literally in the field value (e.g. `"Denier Electric"` with the quotes
    as real characters, not JSON string delimiters) -- found in a live
    500-project test run against general_contractor."""
    return raw.strip().strip('"').strip("'").strip()


def normalize(raw: str) -> str | None:
    s = clean_display(raw).lower()
    s = re.sub(r"[^\w\s&/-]", "", s)
    s = _LEGAL_SUFFIXES.sub("", s).strip()
    s = re.sub(r"\s+", " ", s)
    return s or None


def is_firm_like(raw: str) -> bool:
    """Rough signal that a name string is a company, not an individual --
    used to decide whether a `people` row gets a firm_name. Not a claim
    this is reliable, just better than leaving every architect/owner
    string unclassified."""
    lowered = raw.lower()
    return bool(
        re.search(r"\b(inc|llc|ltd|co|corp|company|group|architects?|associates|partners|studio)\b", lowered)
    )


def upsert_manufacturer(cur, raw: str, state: str | None) -> int | None:
    norm = normalize(raw)
    if not norm:
        return None
    cur.execute(
        """
        INSERT INTO manufacturers (normalized_name, display_name, state)
        VALUES (%s, %s, %s)
        ON CONFLICT (normalized_name, state) DO UPDATE SET display_name = EXCLUDED.display_name
        RETURNING id
        """,
        (norm, clean_display(raw), state),
    )
    return cur.fetchone()[0]


def upsert_gc(cur, raw: str, state: str | None) -> int | None:
    norm = normalize(raw)
    if not norm:
        return None
    cur.execute(
        """
        INSERT INTO general_contractors (normalized_name, display_name, state)
        VALUES (%s, %s, %s)
        ON CONFLICT (normalized_name, state) DO UPDATE SET display_name = EXCLUDED.display_name
        RETURNING id
        """,
        (norm, clean_display(raw), state),
    )
    return cur.fetchone()[0]


def upsert_person(cur, raw: str, role: str, state: str | None) -> int | None:
    norm = normalize(raw)
    if not norm:
        return None
    firm = clean_display(raw) if is_firm_like(raw) else None
    cur.execute(
        """
        INSERT INTO people (normalized_name, display_name, firm_name, role, state)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (normalized_name, firm_name) DO UPDATE SET display_name = EXCLUDED.display_name
        RETURNING id
        """,
        (norm, clean_display(raw), firm, role, state),
    )
    return cur.fetchone()[0]


def process_project(cur, row: dict) -> dict:
    counts = {"manufacturers": 0, "gc": 0, "people": 0}
    sk = row["project_sk"]
    state = row["state"]

    for raw in row["mentioned_brands"] or []:
        mid = upsert_manufacturer(cur, raw, state)
        if mid is None:
            continue
        cur.execute(
            """
            INSERT INTO project_manufacturers (project_sk, manufacturer_id, source_field)
            VALUES (%s, %s, 'mentioned_brands') ON CONFLICT DO NOTHING
            """,
            (sk, mid),
        )
        counts["manufacturers"] += 1

    if row["general_contractor"]:
        gid = upsert_gc(cur, row["general_contractor"], state)
        if gid is not None:
            cur.execute(
                """
                INSERT INTO project_general_contractors (project_sk, general_contractor_id)
                VALUES (%s, %s) ON CONFLICT DO NOTHING
                """,
                (sk, gid),
            )
            counts["gc"] += 1

    for field, role in (("owner", "owner"), ("architect", "architect")):
        if row[field]:
            pid = upsert_person(cur, row[field], role, state)
            if pid is not None:
                cur.execute(
                    """
                    INSERT INTO project_people (project_sk, person_id, role)
                    VALUES (%s, %s, %s) ON CONFLICT DO NOTHING
                    """,
                    (sk, pid, role),
                )
                counts["people"] += 1

    return counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", "postgresql://specindex:specindex@localhost:5432/specindex"),
    )
    ap.add_argument("--limit", type=int, default=None, help="Cap projects processed this run (omit for all)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = psycopg2.connect(args.database_url)
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            query = """
                SELECT project_sk, state, mentioned_brands,
                       owner, architect, general_contractor
                FROM projects
            """
            if args.limit:
                query += " LIMIT %s"
                cur.execute(query, (args.limit,))
            else:
                cur.execute(query)
            rows = cur.fetchall()

        total = {"manufacturers": 0, "gc": 0, "people": 0}
        with conn.cursor() as cur:
            for i, row in enumerate(rows, 1):
                counts = process_project(cur, row)
                for k in total:
                    total[k] += counts[k]
                # Commits every 5000 rows instead of one commit at the very
                # end -- a 328K-row run held everything in a single
                # uncommitted transaction for its entire ~10+ hour runtime
                # in practice (confirmed live: entity tables were still
                # empty at 43% progress), meaning a crash anywhere lost
                # ALL progress, not just the unfinished tail, and nothing
                # was queryable until the whole run finished. --dry-run
                # still rolls back everything at the end, just via more,
                # smaller savepoint-free transactions.
                if not args.dry_run and i % 5000 == 0:
                    conn.commit()
                    print(f"  processed {i}/{len(rows)} projects... (committed)", file=sys.stderr)
                elif i % 5000 == 0:
                    print(f"  processed {i}/{len(rows)} projects...", file=sys.stderr)

        print(f"Processed {len(rows)} projects.")
        print(f"  manufacturer links: {total['manufacturers']}")
        print(f"  GC links: {total['gc']}")
        print(f"  people links: {total['people']}")

        if args.dry_run:
            conn.rollback()
            print("Dry run -- rolled back.")
        else:
            conn.commit()
            print("Committed.")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
