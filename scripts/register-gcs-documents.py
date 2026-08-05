#!/usr/bin/env python3
"""Register documents already sitting in GCS into project_document_files.

THE SEAM THIS CLOSES. fetch-sam-gov-documents.py and fetch-accela-documents.py
upload to GCS and touch the database ZERO times -- verified by grep, neither
file contains psycopg2, DATABASE_URL, or an INSERT. Meanwhile step 9
(extract-document-text.py) selects its work FROM project_document_files. So
every document those two scripts capture is invisible to text extraction, to
spec-book extraction, and to enrichment.

Measured 2026-08-05: 10,033 objects in GCS, 2,240 rows in the table. Roughly
78% of the captured corpus was unreachable by everything downstream. Capture
was never the bottleneck -- this was, and it presented as "extraction is slow"
rather than as an error, which is why it survived so long.

HOW PROJECTS ARE MATCHED. Path convention is
{state_dir}/{project_id}/{filename}, so the middle segment is the project id.
Two shapes exist:
  georgia/ga-sam-<hash>-<slug>/Attachment 1 - Specifications.pdf
  minnesota/mn-olmsted-accela-olmsted-o24-0042cb/Permit.pdf
Matching is by exact project_id first, then by longest-prefix, because SAM
folder names are TRUNCATED slugs of the opportunity title and do not always
round-trip. A blob whose project cannot be resolved is reported, never
guessed -- an unmatched document is a fixable gap, a mis-attributed one is
silent corruption of the citation graph that the whole product rests on.

IDEMPOTENT. UNIQUE (project_sk, url) plus ON CONFLICT DO NOTHING, so this can
be re-run after every capture batch without duplicating rows.

Usage:
  python3 scripts/register-gcs-documents.py --database-url ... --dry-run
  python3 scripts/register-gcs-documents.py --database-url ...
  python3 scripts/register-gcs-documents.py --database-url ... --prefix me/
"""
from __future__ import annotations

import argparse
import collections
import os
import sys
import urllib.parse
from pathlib import Path

GCS_BUCKET = "specindex-ai-raw-documents"
PUBLIC_BASE = f"https://storage.googleapis.com/{GCS_BUCKET}/"

CTYPE_BY_EXT = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".zip": "application/zip",
    ".dwg": "image/vnd.dwg",
    ".rvt": "application/octet-stream",
}


def gcs_client():
    from google.cloud import storage  # noqa: PLC0415

    key = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if key and Path(key).is_file():
        print(f"[gcs] using service-account key {Path(key).name}", file=sys.stderr)
    return storage.Client(project="specindex-ai")


def main() -> int:
    import psycopg2  # noqa: PLC0415

    ap = argparse.ArgumentParser()
    ap.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    ap.add_argument("--prefix", default="", help="restrict to a GCS prefix, e.g. me/")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    if not args.database_url:
        print("need --database-url or DATABASE_URL", file=sys.stderr)
        return 2

    conn = psycopg2.connect(args.database_url, connect_timeout=30)
    cur = conn.cursor()
    cur.execute("SELECT project_id, project_sk FROM projects")
    by_id: dict[str, int] = {pid: sk for pid, sk in cur.fetchall()}
    print(f"projects in db: {len(by_id):,}")

    # Longest-prefix fallback for truncated SAM folder slugs. Sorted longest
    # first so the most specific project id wins; a short id must never
    # swallow a longer one that shares its stem.
    ids_by_len = sorted(by_id, key=len, reverse=True)

    client = gcs_client()
    stats = collections.Counter()
    unmatched: collections.Counter = collections.Counter()
    rows: list[tuple] = []

    for blob in client.list_blobs(GCS_BUCKET, prefix=args.prefix or None):
        parts = blob.name.split("/")
        if len(parts) < 3:
            stats["skip-flat-path"] += 1     # content/{sha}.pdf -- already registered
            continue
        folder, filename = parts[1], parts[-1]
        if not filename:
            continue
        sk = by_id.get(folder)
        if sk is None:
            for pid in ids_by_len:
                if folder.startswith(pid):
                    sk = by_id[pid]
                    stats["match-prefix"] += 1
                    break
        else:
            stats["match-exact"] += 1
        if sk is None:
            stats["UNMATCHED"] += 1
            unmatched[folder] += 1
            continue

        ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
        rows.append((sk, filename[:400],
                     PUBLIC_BASE + urllib.parse.quote(blob.name),
                     CTYPE_BY_EXT.get(ext, blob.content_type or "application/octet-stream")))
        if args.limit and len(rows) >= args.limit:
            break

    print(f"\nblobs matched  : {stats['match-exact'] + stats['match-prefix']:,} "
          f"(exact {stats['match-exact']:,}, prefix {stats['match-prefix']:,})")
    print(f"blobs unmatched: {stats['UNMATCHED']:,} across {len(unmatched):,} folders")
    print(f"flat-path skips: {stats['skip-flat-path']:,}")
    if unmatched:
        print("top unmatched folders (report, never guess):")
        for f, n in unmatched.most_common(8):
            print(f"   {n:>5}  {f[:80]}")

    cur.execute("SELECT count(*) FROM project_document_files")
    before = cur.fetchone()[0]
    print(f"\nproject_document_files before: {before:,}")

    if args.dry_run:
        print(f"DRY RUN -- would insert up to {len(rows):,} rows")
        return 0

    ins = 0
    for i in range(0, len(rows), 500):
        chunk = rows[i:i + 500]
        cur.executemany(
            "INSERT INTO project_document_files (project_sk, title, url, content_type) "
            "VALUES (%s,%s,%s,%s) ON CONFLICT (project_sk, url) DO NOTHING", chunk)
        conn.commit()
        ins += len(chunk)
        if (i // 500) % 5 == 0:
            print(f"  ...{ins:,}/{len(rows):,}", flush=True)

    cur.execute("SELECT count(*) FROM project_document_files")
    after = cur.fetchone()[0]
    print(f"project_document_files after : {after:,}   (+{after - before:,})")
    # The count must never go DOWN. A decrease means something other than an
    # idempotent insert happened and is a stop-everything signal.
    if after < before:
        print("FATAL: row count DECREASED -- stop and investigate", file=sys.stderr)
        return 1
    print("REGISTRATION COMPLETE")  # sentinel
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
