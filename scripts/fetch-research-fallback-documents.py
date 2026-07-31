#!/usr/bin/env python3
"""Pull real documents found by step 6's research fallback straight to GCS.

Step 6c's remaining gap: `research-county-sources.py`'s step 6a grounded
call now also asks for a per-project "pullable document" claim (site
plans, PUD packets, permit applications, drawings -- see
docs/AGENT_STRATEGY.md step 6a, added 2026-07-31), but nothing pulled
those documents. This script closes that gap for the file shape used by
the `data/raw/il-*-research-fallback*.json` findings files: reads each
project's `pullable_documents` list, live-fetches every URL, and uploads
anything that's a real file straight to GCS -- no local copy, per Asif's
2026-07-28 GCS-only instruction (same rule `fetch-sam-gov-documents.py`
follows for SAM.gov attachments).

A "pullable_documents" URL in one of these files is a CLAIM, not a
verified fact -- confirmed live on McLean County, IL that these claims
are sometimes fabricated (3/3 first-pass OSF HFSRB URLs were 404s).
This script is itself the live-verification step for that claim: a URL
that 404s or isn't actually a document (HTML error page, login wall)
is logged as failed, never uploaded.

Usage:
  python3 scripts/fetch-research-fallback-documents.py \
      --findings-file data/raw/il-mclean-research-fallback.json \
      --state illinois
  python3 scripts/fetch-research-fallback-documents.py \
      --findings-file data/raw/il-kendall-research-fallback.json \
      --state illinois --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
GCS_BUCKET = "specindex-ai-raw-documents"
USER_AGENT = "Mozilla/5.0 SpecIndex-DocumentBot/1.0 (+https://specindex.ai)"

# Real documents are PDFs/DOCX/etc; anything served as text/html is an
# error page, login wall, or a portal landing page, not a document --
# reject it even if the HTTP status is 200.
REJECTED_CONTENT_TYPES = ("text/html",)


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "untitled-project"


def fetch(url: str, timeout: int = 30) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        content_type = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
        return resp.read(), content_type


def guess_filename(url: str, content_type: str, index: int) -> str:
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    if "." in tail and len(tail) < 100:
        return tail
    ext = ".pdf" if "pdf" in content_type else ".bin"
    return f"document-{index}{ext}"


def upload_to_gcs(bucket, state: str, county: str, project_slug: str, filename: str, data: bytes, content_type: str) -> str:
    blob_path = f"{state}/{county}/{project_slug}/{filename}"
    blob = bucket.blob(blob_path)
    if blob.exists():
        print(f"    [skip] already in GCS: {blob_path}", file=sys.stderr)
        return "skipped"
    blob.upload_from_string(data, content_type=content_type or "application/octet-stream")
    print(f"    [uploaded] {blob_path} ({len(data):,} bytes)", file=sys.stderr)
    return "uploaded"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--findings-file", required=True, help="A data/raw/*-research-fallback*.json file")
    parser.add_argument("--state", required=True, help="GCS folder name, e.g. illinois")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and validate, but don't upload")
    args = parser.parse_args(argv)

    findings = json.loads(Path(args.findings_file).read_text())
    county = findings.get("county", "unknown-county").lower()
    projects = findings.get("projects", [])
    if not projects and "new_project_not_in_broader_pass" in findings:
        projects = [findings["new_project_not_in_broader_pass"]]

    print(f"{args.findings_file}: {len(projects)} project(s), county={county}", file=sys.stderr)

    bucket = None
    if not args.dry_run:
        from google.cloud import storage

        bucket = storage.Client().bucket(GCS_BUCKET)

    summary = {"projects_checked": 0, "urls_claimed": 0, "verified_real": 0, "fabricated_or_dead": 0, "files_uploaded": 0, "files_skipped_existing": 0}
    for project in projects:
        docs = project.get("pullable_documents") or []
        summary["projects_checked"] += 1
        if not docs:
            continue
        name = project.get("name", "untitled")
        slug = slugify(name)
        print(f"{name}: {len(docs)} claimed document(s)", file=sys.stderr)
        for i, doc in enumerate(docs, start=1):
            url = doc.get("url")
            if not url:
                continue
            summary["urls_claimed"] += 1
            try:
                data, content_type = fetch(url)
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
                print(f"  [dead] {url} -- {e}", file=sys.stderr)
                summary["fabricated_or_dead"] += 1
                continue
            if content_type in REJECTED_CONTENT_TYPES:
                print(f"  [rejected] {url} -- served as {content_type}, not a real document", file=sys.stderr)
                summary["fabricated_or_dead"] += 1
                continue
            summary["verified_real"] += 1
            filename = guess_filename(url, content_type, i)
            print(f"  [real] {url} -- {content_type}, {len(data):,} bytes", file=sys.stderr)
            if args.dry_run:
                continue
            result = upload_to_gcs(bucket, args.state, county, slug, filename, data, content_type)
            if result == "uploaded":
                summary["files_uploaded"] += 1
            elif result == "skipped":
                summary["files_skipped_existing"] += 1

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
