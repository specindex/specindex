#!/usr/bin/env python3
"""Fetch documents from data/documents/*/*.json manifests, live-verify each
URL, and store a durable copy in GCS -- content-hash-addressed so the same
file (referenced by multiple projects, or re-fetched on a later run) is
never uploaded twice.

Companion to compute-project-documents.py, which only ever wrote the
original external URL straight into project_document_files -- exactly the
kind of link that rots. Confirmed live 2026-07-29: a Teachers Village
document pointed at an Invest Atlanta page that had since moved/been
removed (404 on a real user click), with no way to know it had gone dead
until someone actually clicked it. This script is what makes the
"Documents" section resilient to that going forward: every URL is
live-checked before being trusted, and once fetched we serve our own copy
instead of depending on the source page staying put.

Storage layout: gs://specindex-ai-raw-documents/content/{sha256}{ext} --
content-addressed, not project/title-addressed, so dedup is by actual
bytes (two projects citing the same PDF, or a re-run over already-fetched
documents) rather than by path guessing. Explicitly requested 2026-07-29:
"don't want to overpay for storage of documents if its duplicated."

Serving: api/main.py's GET /v1/documents/{id} streams the GCS object
directly (proxied through Cloud Run, not a signed-URL redirect -- the
service account has roles/editor but not iam.serviceAccounts.signBlob,
and proxying avoids needing that extra IAM grant for a v1. Revisit as a
scaling optimization once document traffic/file sizes justify it).

Per the existing GCS-only convention (see docs/AGENT_STRATEGY.md step 7):
never stages through local disk -- downloaded bytes go straight from the
HTTP response into the upload call.

Usage:
    python3 scripts/fetch-and-store-documents.py --dry-run
    python3 scripts/fetch-and-store-documents.py --apply-migration --limit 20
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import mimetypes
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GCS_BUCKET = "specindex-ai-raw-documents"
USER_AGENT = "Mozilla/5.0 SpecIndex-DocumentBot/1.0 (+https://specindex.ai)"

# compute-project-documents.py's filename isn't a valid module identifier
# (hyphens) -- load it by path instead of duplicating its three manifest
# parsers (files_from_georgia/fulton/new_jersey), which this script reuses
# as-is to build the same project_id -> [{"title","url","content_type"}]
# map compute-project-documents.py already knows how to produce.
_spec = importlib.util.spec_from_file_location(
    "compute_project_documents", ROOT / "scripts" / "compute-project-documents.py"
)
compute_project_documents = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(compute_project_documents)


def url_resolves(url: str, timeout: float = 8.0) -> bool:
    """Same idea as enrich-project-details.py's url_resolves() -- never
    trust a URL that hasn't actually been checked this run."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except Exception:  # noqa: BLE001 -- any failure means "don't trust this link"
        return False


def fetch(url: str, timeout: float = 30.0) -> tuple[bytes, str | None]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(), resp.headers.get("Content-Type")


def store_in_gcs(bucket, data: bytes, content_type: str | None, title: str) -> tuple[str, str]:
    """Uploads content-addressed by sha256, skipping if already present.
    Returns (gcs_path, sha256_hex)."""
    digest = hashlib.sha256(data).hexdigest()
    ext = mimetypes.guess_extension((content_type or "").split(";")[0].strip()) or ""
    if not ext and "." in title:
        ext = "." + title.rsplit(".", 1)[-1][:8]
    blob_path = f"content/{digest}{ext}"
    blob = bucket.blob(blob_path)
    if not blob.exists():
        blob.upload_from_string(data, content_type=content_type or "application/octet-stream")
        print(f"  [uploaded] {blob_path} ({len(data):,} bytes)", file=sys.stderr)
    else:
        print(f"  [dedup] content already in GCS: {blob_path}", file=sys.stderr)
    return blob_path, digest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", "postgresql://specindex:specindex@localhost:5432/specindex"),
    )
    ap.add_argument("--apply-migration", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="live-check URLs, don't fetch/upload/write")
    ap.add_argument("--limit", type=int, default=0, help="cap documents processed, 0 = no cap")
    ap.add_argument("--project-id", default=None, help="only process this one project_id (e.g. ga-teachers-village-atlanta)")
    args = ap.parse_args()

    files_by_pid = compute_project_documents.all_files()
    all_docs: list[tuple[str, dict[str, Any]]] = [
        (pid, doc) for pid, docs in files_by_pid.items() for doc in docs
    ]
    if args.project_id:
        all_docs = [(pid, doc) for pid, doc in all_docs if pid == args.project_id]
    if args.limit:
        all_docs = all_docs[: args.limit]
    print(f"Checking {len(all_docs)} document(s)", file=sys.stderr)

    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(args.database_url)
    bucket = None
    try:
        if args.apply_migration and not args.dry_run:
            with conn.cursor() as cur:
                cur.execute((ROOT / "db" / "migrations" / "019_project_document_files_gcs.sql").read_text())
            conn.commit()

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            pids = list({pid for pid, _ in all_docs})
            cur.execute("SELECT project_id, project_sk FROM projects WHERE project_id = ANY(%s)", (pids,))
            id_to_sk = {row["project_id"]: row["project_sk"] for row in cur.fetchall()}

        if not args.dry_run:
            from google.cloud import storage

            bucket = storage.Client().bucket(GCS_BUCKET)

        summary = {"checked": 0, "dead_links": 0, "fetched": 0, "deduped": 0, "no_project_match": 0}
        with conn.cursor() as cur:
            for pid, doc in all_docs:
                summary["checked"] += 1
                url, title = doc["url"], doc["title"]
                if pid not in id_to_sk:
                    summary["no_project_match"] += 1
                    continue
                if not url_resolves(url):
                    summary["dead_links"] += 1
                    print(f"  [dead] {pid}: {title!r} -> {url}", file=sys.stderr)
                    continue
                if args.dry_run:
                    print(f"  [live] {pid}: {title!r} -> {url}", file=sys.stderr)
                    continue

                try:
                    data, resp_content_type = fetch(url)
                except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
                    print(f"  [error] fetch failed for {pid} {title!r}: {e}", file=sys.stderr)
                    continue

                content_type = doc.get("content_type") or resp_content_type
                gcs_path, digest = store_in_gcs(bucket, data, content_type, title)
                summary["fetched"] += 1

                sk = id_to_sk[pid]
                cur.execute(
                    """
                    INSERT INTO project_document_files (project_sk, title, url, content_type, gcs_path, content_sha256, fetched_at, computed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, now(), now())
                    ON CONFLICT (project_sk, url) DO UPDATE SET
                        title = EXCLUDED.title,
                        content_type = EXCLUDED.content_type,
                        gcs_path = EXCLUDED.gcs_path,
                        content_sha256 = EXCLUDED.content_sha256,
                        fetched_at = now(),
                        computed_at = now()
                    """,
                    (sk, title, url, content_type, gcs_path, digest),
                )
        if not args.dry_run:
            conn.commit()
        print(f"\nSummary: {summary}", file=sys.stderr)
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
