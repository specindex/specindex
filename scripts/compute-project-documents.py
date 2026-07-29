#!/usr/bin/env python3
"""Populate project_documents from the checked-in data/documents/*/*.json
manifests, so the API/frontend can filter "has attached documents".

Three manifest shapes exist today, each parsed differently:
  - data/documents/georgia/manifest.json: {"projects": [{"project_id", "documents": [...]}]}
  - data/documents/fulton-county/index.json: {"project_documents": [{"project_id", ...}, ...]} (flat, one row per doc)
  - data/documents/new-jersey/manifest.json: {"by_project": {project_id: {"documents": [...]}}}

Slug prefixes are inconsistent with the DB on purpose-vs-accident: GA and
Fulton manifests use the bare project slug ("centennial-yards"), but
projects.project_id in Postgres is state-prefixed ("ga-centennial-yards")
-- confirmed live 2026-07-29 (ga-troup-county-data-center exists,
troup-county-data-center does not). NJ's manifest already writes
nj-prefixed ids, so it needs no rewrite. Fulton County is in Georgia, so
its entries get the same "ga-" prefix as the georgia/ manifest.

Usage:
    python3 scripts/compute-project-documents.py --dry-run
    python3 scripts/compute-project-documents.py --apply-migration
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "data" / "documents"


def _load(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def counts_from_georgia() -> Counter:
    data = _load(DOCS_DIR / "georgia" / "manifest.json")
    counts: Counter = Counter()
    if not data:
        return counts
    for p in data.get("projects", []):
        pid = p.get("project_id")
        n = len(p.get("documents") or [])
        if pid and n:
            counts[f"ga-{pid}"] += n
    return counts


def counts_from_fulton() -> Counter:
    data = _load(DOCS_DIR / "fulton-county" / "index.json")
    counts: Counter = Counter()
    if not data:
        return counts
    for doc in data.get("project_documents", []):
        pid = doc.get("project_id")
        if pid:
            counts[f"ga-{pid}"] += 1
    return counts


def counts_from_new_jersey() -> Counter:
    data = _load(DOCS_DIR / "new-jersey" / "manifest.json")
    counts: Counter = Counter()
    if not data:
        return counts
    for pid, p in (data.get("by_project") or {}).items():
        n = len(p.get("documents") or [])
        if n:
            counts[pid] += n  # already nj-prefixed in the manifest
    return counts


def all_counts() -> Counter:
    total: Counter = Counter()
    total.update(counts_from_georgia())
    total.update(counts_from_fulton())
    total.update(counts_from_new_jersey())
    return total


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", "postgresql://specindex:specindex@localhost:5432/specindex"),
    )
    ap.add_argument("--apply-migration", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="print what would be written, don't touch the DB")
    args = ap.parse_args()

    counts = all_counts()
    print(f"Found document counts for {len(counts)} project_id(s) across GA/Fulton/NJ manifests")

    if args.dry_run and not counts:
        print("(nothing to do)")
        return 0

    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(args.database_url)
    try:
        if args.apply_migration:
            with conn.cursor() as cur:
                migration = ROOT / "db" / "migrations" / "017_project_documents.sql"
                cur.execute(migration.read_text(encoding="utf-8"))
            conn.commit()

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT project_id, project_sk FROM projects WHERE project_id = ANY(%s)", (list(counts.keys()),))
            id_to_sk = {row["project_id"]: row["project_sk"] for row in cur.fetchall()}

        matched = {pid: n for pid, n in counts.items() if pid in id_to_sk}
        unmatched = [pid for pid in counts if pid not in id_to_sk]
        print(f"Matched {len(matched)}/{len(counts)} project_id(s) to a real project_sk")
        for pid in unmatched[:15]:
            print(f"  no DB match: {pid!r} ({counts[pid]} doc(s))")
        if len(unmatched) > 15:
            print(f"  ... and {len(unmatched) - 15} more unmatched")

        if args.dry_run:
            print("\n--dry-run: not writing to the database")
            for pid, n in sorted(matched.items(), key=lambda kv: -kv[1])[:10]:
                print(f"  {pid}: {n} document(s)")
            return 0

        with conn.cursor() as cur:
            for pid, n in matched.items():
                cur.execute(
                    """
                    INSERT INTO project_documents (project_sk, document_count, computed_at)
                    VALUES (%s, %s, now())
                    ON CONFLICT (project_sk) DO UPDATE SET
                        document_count = EXCLUDED.document_count,
                        computed_at = now()
                    """,
                    (id_to_sk[pid], n),
                )
        conn.commit()
        print(f"\nWrote document counts for {len(matched)} project(s)")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
