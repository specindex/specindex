#!/usr/bin/env python3
"""Register portal spec books into project_document_files.

THE THIRD INSTANCE OF ONE SEAM. Portal spec books land in reference_documents,
but the record page counts project_document_files -- so Maine 3820 rendered
"Not determinable -- no documents held for this project" while holding the
document AND 16 classified divisions, 9 naming a manufacturer.

The page was not wrong. It read the table it has always read; the writer put the
row somewhere else. Same shape as the classifier reading substitution_rulings
while the data sat in project_csi_divisions, and as adapters writing JSON that
nothing loaded.

reference_documents stays the home for jurisdiction-scoped material -- a state
DOT standard specification governs every project in a state and belongs to none.
But a spec book for ONE named project is a project document, so it is registered
in both: the reference row keeps the extraction lineage, and the project row is
what the record page can see.
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from specindex.db import connect  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = connect(); cur = conn.cursor()
    cur.execute("SELECT count(*) FROM project_document_files"); before = cur.fetchone()[0]
    print(f"[before] project_document_files {before:,}", flush=True)

    cur.execute(
        """
        SELECT r.id, r.url, r.title, r.gcs_path, r.content_sha256, r.byte_size,
               p.project_sk
          FROM reference_documents r
          JOIN projects p ON p.project_id = r.scope_value
         WHERE r.scope = 'project'
        """
    )
    rows = cur.fetchall()
    print(f"[scope] {len(rows)} project-scoped spec books", flush=True)

    linked = 0
    for rid, url, title, gcs, sha, size, sk in rows:
        if args.dry_run:
            linked += 1
            continue
        cur.execute(
            """
            INSERT INTO project_document_files
                (project_sk, title, url, content_type, gcs_path, content_sha256,
                 doc_type, spec_format, fetched_at, computed_at)
            VALUES (%s,%s,%s,'application/pdf',%s,%s,'specbook','CSI', now(), now())
            ON CONFLICT (project_sk, url) DO UPDATE SET
                gcs_path = EXCLUDED.gcs_path,
                content_sha256 = EXCLUDED.content_sha256,
                computed_at = now()
            """,
            (sk, (title or "Project manual")[:500], url, gcs, sha),
        )
        linked += 1
    conn.commit()

    # project_documents is the CACHED count the record page reads. A row added to
    # project_document_files that never refreshes this cache is invisible -- the
    # same failure one level down.
    if not args.dry_run:
        cur.execute(
            """
            -- has_documents is a GENERATED column derived from document_count;
            -- writing it explicitly is rejected, and trying to would have meant
            -- the two could disagree.
            INSERT INTO project_documents (project_sk, document_count, computed_at)
            SELECT f.project_sk, count(*), now()
              FROM project_document_files f
             GROUP BY f.project_sk
            ON CONFLICT (project_sk) DO UPDATE SET
                document_count = EXCLUDED.document_count,
                computed_at = now()
            """
        )
        conn.commit()

    cur.execute("SELECT count(*) FROM project_document_files"); after = cur.fetchone()[0]
    cur.execute("""SELECT document_count FROM project_documents pd
                     JOIN projects p ON p.project_sk = pd.project_sk
                    WHERE p.project_id = 'me-portal-maine-vertical-3820'""")
    got = cur.fetchone()
    print(f"\n[after] project_document_files {after:,}  (+{after-before:,})  linked={linked}")
    print(f"[verify] Maine 3820 document_count = {got[0] if got else 0}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
