#!/usr/bin/env python3
"""Pull real SAM.gov solicitation attachments straight to GCS -- no local copy.

Step 7 of the ingestion pipeline (see docs/AGENT_STRATEGY.md's "Gemini-
Assisted County/State Source Discovery" section), for SAM.gov-sourced
projects specifically. SAM.gov's public bulk CSV extract (what
sam_gov_provider.py ingests) does not include attachment URLs -- this
script enriches each already-captured project by querying SAM.gov's
real, anonymous, no-API-key attachment API directly:

    GET https://sam.gov/api/prod/opps/v3/opportunities/{noticeId}/resources
    GET https://sam.gov/api/prod/opps/v3/opportunities/resources/files/{resourceId}/download

Verified live 2026-07-28 against a real GA project (Notice ID
58696058687545e3993280f21c168c42, "Renovate Bldg. 59D Robins AFB, GA"):
returns real structural drawings, bid abstracts, and site-visit
documents, all `"accessLevel":"public"`, no login/API key needed. The
download endpoint 303-redirects to a signed, time-limited S3 URL --
must follow the redirect, can't cache the pre-redirect URL.

Per Asif's explicit instruction (2026-07-28): documents are uploaded
directly to GCS, never staged through a local folder first.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RESOURCES_URL = "https://sam.gov/api/prod/opps/v3/opportunities/{notice_id}/resources?excludeDeleted=false"
DOWNLOAD_URL = "https://sam.gov/api/prod/opps/v3/opportunities/resources/files/{resource_id}/download"
USER_AGENT = "Mozilla/5.0 SpecIndex-DocumentBot/1.0 (+https://specindex.ai)"
GCS_BUCKET = "specindex-ai-raw-documents"


def _get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def extract_notice_id(project: dict[str, Any]) -> str | None:
    for src in project.get("sources", []):
        m = re.search(r"sam\.gov/workspace/contract/opp/([0-9a-f]{32})", src.get("url", ""))
        if m:
            return m.group(1)
    return None


def list_attachments(notice_id: str) -> list[dict[str, Any]]:
    try:
        body = json.loads(_get(RESOURCES_URL.format(notice_id=notice_id)))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
        print(f"  [error] resources lookup failed for {notice_id}: {e}", file=sys.stderr)
        return []
    results = body.get("_embedded", {}).get("opportunityAttachmentList", [])
    if not results:
        return []
    return [
        a
        for a in results[0].get("attachments", [])
        if a.get("type") == "file" and a.get("accessStatus") == "public" and a.get("fileExists") == "1"
    ]


def upload_attachment_to_gcs(bucket, project_id: str, attachment: dict[str, Any]) -> str:
    """Returns 'uploaded', 'skipped' (already in GCS), or 'error'."""
    resource_id = attachment["resourceId"]
    name = attachment.get("name") or f"{resource_id}.bin"
    blob_path = f"georgia/{project_id}/{name}"
    blob = bucket.blob(blob_path)
    if blob.exists():
        print(f"  [skip] already in GCS: {blob_path}", file=sys.stderr)
        return "skipped"

    req = urllib.request.Request(
        DOWNLOAD_URL.format(resource_id=resource_id) + f"?fn={urllib.parse.quote(name)}",
        headers={"User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        print(f"  [error] download failed for {name}: {e}", file=sys.stderr)
        return "error"

    content_type = "application/pdf" if name.lower().endswith(".pdf") else "application/octet-stream"
    blob.upload_from_string(data, content_type=content_type)
    print(f"  [uploaded] {blob_path} ({len(data):,} bytes)", file=sys.stderr)
    return "uploaded"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", default=str(ROOT / "data" / "states" / "ga.json"))
    parser.add_argument("--id-prefix", default="ga-sam", help="Only process projects whose id starts with this")
    parser.add_argument("--limit", type=int, default=0, help="Cap projects processed, 0 = no cap")
    parser.add_argument("--dry-run", action="store_true", help="List attachments found, don't upload")
    args = parser.parse_args(argv)

    data = json.loads(Path(args.state_file).read_text())
    projects = [p for p in data["projects"] if p["id"].startswith(args.id_prefix)]
    if args.limit:
        projects = projects[: args.limit]
    print(f"Processing {len(projects)} projects (prefix={args.id_prefix!r})", file=sys.stderr)

    bucket = None
    if not args.dry_run:
        from google.cloud import storage

        bucket = storage.Client().bucket(GCS_BUCKET)

    summary = {"projects_checked": 0, "projects_with_docs": 0, "files_uploaded": 0, "files_skipped_existing": 0}
    for project in projects:
        notice_id = extract_notice_id(project)
        summary["projects_checked"] += 1
        if not notice_id:
            continue
        attachments = list_attachments(notice_id)
        if not attachments:
            continue
        summary["projects_with_docs"] += 1
        print(f"{project['id']}: {len(attachments)} public attachment(s)", file=sys.stderr)
        if args.dry_run:
            for a in attachments:
                print(f"  - {a.get('name')} ({a.get('size', 0):,} bytes)", file=sys.stderr)
            continue
        for a in attachments:
            result = upload_attachment_to_gcs(bucket, project["id"], a)
            if result == "uploaded":
                summary["files_uploaded"] += 1
            elif result == "skipped":
                summary["files_skipped_existing"] += 1

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
