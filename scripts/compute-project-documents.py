#!/usr/bin/env python3
"""Populate project_documents + project_document_files from the checked-in
data/documents/*/*.json manifests, so the API/frontend can filter "has
attached documents" (project_documents, aggregate count) and actually link
to them on the detail page (project_document_files, one row per file).

Three manifest shapes exist today, each parsed differently:
  - data/documents/georgia/manifest.json: {"projects": [{"project_id", "documents": [{"filename", "url", "content_type"}]}]}
  - data/documents/fulton-county/index.json: {"project_documents": [{"project_id", "title", "url", "content_type"}, ...]} (flat, one row per doc)
  - data/documents/new-jersey/manifest.json: {"by_project": {project_id: {"documents": [{"filename", "url", "content_type"}]}}}

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
import re
import sys
import urllib.parse
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "data" / "documents"

# project_id -> list of {"title", "url", "content_type"}
DocMap = dict[str, list[dict]]

# Deterministic, keyword-based classification -- no LLM involved, same
# discipline as the rest of this pipeline. Order matters: checked
# top-to-bottom, first match wins, so more specific categories (e.g.
# "structural") are listed before generic ones that might also match a
# structural doc's title (e.g. a "Structural Specifications" doc should
# land in structural_engineering, not specifications).
DOCUMENT_TYPE_KEYWORDS: list[tuple[str, list[str]]] = [
    ("structural_engineering", ["structural", "civil engineering", "mep", "calculations", "geotechnical"]),
    ("drawings_plans", ["drawing", "site plan", "floor plan", "blueprint", "elevation", "survey"]),
    ("specifications", ["specification", "spec book", "project manual"]),
    ("staff_report", ["staff report", "staff review", "memo"]),
    ("meeting_agenda", ["agenda", "minutes", "packet"]),
    ("permit_application", ["application", "permit form"]),
]


def classify_document_type(title: str) -> str:
    # Real filenames use underscores/hyphens in place of spaces at least as
    # often as they use spaces (e.g. "26-116-staff-report.pdf",
    # "Civil_Engineering_Facility_Requirements.pdf") -- normalize both to
    # spaces so phrase keywords like "staff report"/"civil engineering"
    # match regardless of separator style. Confirmed live 2026-07-29: both
    # of those real filenames fell through to "other" before this fix.
    haystack = re.sub(r"[_-]+", " ", title.lower())
    for doc_type, keywords in DOCUMENT_TYPE_KEYWORDS:
        if any(kw in haystack for kw in keywords):
            return doc_type
    return "other"


def _load(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def files_from_georgia() -> DocMap:
    data = _load(DOCS_DIR / "georgia" / "manifest.json")
    out: DocMap = defaultdict(list)
    if not data:
        return out
    for p in data.get("projects", []):
        pid = p.get("project_id")
        if not pid:
            continue
        for doc in p.get("documents") or []:
            url = doc.get("url")
            if not url:
                continue
            out[f"ga-{pid}"].append(
                {"title": doc.get("filename") or url, "url": url, "content_type": doc.get("content_type")}
            )
    return out


def files_from_fulton() -> DocMap:
    data = _load(DOCS_DIR / "fulton-county" / "index.json")
    out: DocMap = defaultdict(list)
    if not data:
        return out
    for doc in data.get("project_documents", []):
        pid = doc.get("project_id")
        url = doc.get("url")
        if not pid or not url:
            continue
        out[f"ga-{pid}"].append(
            {"title": doc.get("title") or url, "url": url, "content_type": doc.get("content_type")}
        )
    return out


def files_from_new_jersey() -> DocMap:
    data = _load(DOCS_DIR / "new-jersey" / "manifest.json")
    out: DocMap = defaultdict(list)
    if not data:
        return out
    for pid, p in (data.get("by_project") or {}).items():
        for doc in p.get("documents") or []:
            url = doc.get("url")
            if not url:
                continue
            out[pid].append(  # already nj-prefixed in the manifest
                {"title": doc.get("title") or doc.get("filename") or url, "url": url, "content_type": doc.get("content_type")}
            )
    return out


GCS_BUCKET = "specindex-ai-raw-documents"


def files_from_gcs() -> DocMap:
    """Scan the live GCS bucket directly instead of a local manifest --
    this is where every document pulled since the GCS-only mandate
    (2026-07-28: 'I don't want documents saved in my local folder only on
    Google Cloud Storage') actually lives: GA-SAM's 411 files plus the
    ongoing Gemini-driven step 7 backfill (data/pipeline/step7-backfill-
    state.json), none of which ever wrote a local manifest. Blob paths are
    `{state_dir}/{project_id}/{filename}` -- project_id is already the
    real corpus id (unlike the old GA/Fulton manifests, no prefix rewrite
    needed). Bucket made public 2026-07-29 so these URLs are directly
    clickable (storage.googleapis.com/... returns 200, verified live) --
    signed URLs would have required an API change to regenerate them
    per-request, not viable for a stored permanent column.
    """
    from google.cloud import storage

    out: DocMap = defaultdict(list)
    bucket = storage.Client().bucket(GCS_BUCKET)
    for blob in bucket.list_blobs():
        parts = blob.name.split("/", 2)
        if len(parts) != 3:
            continue  # not {state}/{project_id}/{filename} -- skip stray top-level objects
        _state_dir, project_id, filename = parts
        if filename == "manifest.json":
            continue  # per-project metadata sidecar, not a real document
        out[project_id].append(
            {
                "title": filename,
                # blob.name is a raw GCS object path built straight from the
                # real filename ("S02 - RFP Attachment 3.pdf") -- unescaped,
                # this 403/400s any HTTP client stricter than a browser.
                # Real bug found 2026-07-29: scripts/extract-document-text.py
                # rejected these outright ("URL can't contain control
                # characters") for every filename with a space in it.
                "url": f"https://storage.googleapis.com/{GCS_BUCKET}/{urllib.parse.quote(blob.name)}",
                "content_type": blob.content_type,
            }
        )
    return out


def all_files() -> DocMap:
    total: DocMap = defaultdict(list)
    for source in (files_from_georgia(), files_from_fulton(), files_from_new_jersey(), files_from_gcs()):
        for pid, docs in source.items():
            total[pid].extend(docs)
    for docs in total.values():
        for d in docs:
            d["document_type"] = classify_document_type(d["title"])
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

    files_by_pid = all_files()
    print(f"Found documents for {len(files_by_pid)} project_id(s) across GA/Fulton/NJ manifests")

    if args.dry_run and not files_by_pid:
        print("(nothing to do)")
        return 0

    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(args.database_url)
    try:
        if args.apply_migration:
            with conn.cursor() as cur:
                for name in (
                    "017_project_documents.sql",
                    "018_project_document_files.sql",
                    "019_project_document_files_gcs.sql",
                    "020_document_types.sql",
                ):
                    migration = ROOT / "db" / "migrations" / name
                    cur.execute(migration.read_text(encoding="utf-8"))
            conn.commit()

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT project_id, project_sk FROM projects WHERE project_id = ANY(%s)",
                (list(files_by_pid.keys()),),
            )
            id_to_sk = {row["project_id"]: row["project_sk"] for row in cur.fetchall()}

        matched = {pid: docs for pid, docs in files_by_pid.items() if pid in id_to_sk}
        unmatched = [pid for pid in files_by_pid if pid not in id_to_sk]
        print(f"Matched {len(matched)}/{len(files_by_pid)} project_id(s) to a real project_sk")
        for pid in unmatched[:15]:
            print(f"  no DB match: {pid!r} ({len(files_by_pid[pid])} doc(s))")
        if len(unmatched) > 15:
            print(f"  ... and {len(unmatched) - 15} more unmatched")

        if args.dry_run:
            print("\n--dry-run: not writing to the database")
            for pid, docs in sorted(matched.items(), key=lambda kv: -len(kv[1]))[:10]:
                print(f"  {pid}: {len(docs)} document(s)")
                for d in docs[:3]:
                    print(f"    - [{d['document_type']}] {d['title']} -> {d['url']}")
            return 0

        with conn.cursor() as cur:
            for pid, docs in matched.items():
                sk = id_to_sk[pid]
                cur.execute(
                    """
                    INSERT INTO project_documents (project_sk, document_count, computed_at)
                    VALUES (%s, %s, now())
                    ON CONFLICT (project_sk) DO UPDATE SET
                        document_count = EXCLUDED.document_count,
                        computed_at = now()
                    """,
                    (sk, len(docs)),
                )
                for d in docs:
                    cur.execute(
                        """
                        INSERT INTO project_document_files (project_sk, title, url, content_type, document_type)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (project_sk, url) DO UPDATE SET
                            title = EXCLUDED.title,
                            content_type = EXCLUDED.content_type,
                            document_type = EXCLUDED.document_type,
                            computed_at = now()
                        """,
                        (sk, d["title"], d["url"], d.get("content_type"), d["document_type"]),
                    )
        conn.commit()
        print(f"\nWrote document data for {len(matched)} project(s)")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
