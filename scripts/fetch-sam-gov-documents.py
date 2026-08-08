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



# GCS layout is {state}/{project_id}/{filename}, matching every other capture
# script. The state directory MUST be derived from the project, not hardcoded:
# this said "georgia" unconditionally, so NC documents landed under georgia/ and
# every one of the 2,390 SAM.gov projects across all 50 states would have piled
# into the same wrong folder.
STATE_DIRS = {
    "al": "alabama", "ak": "ak", "az": "arizona", "ar": "arkansas",
    "ca": "california", "co": "colorado", "ct": "ct", "de": "de",
    "fl": "florida", "ga": "georgia", "hi": "hi", "id": "idaho",
    "il": "illinois", "in": "indiana", "ia": "iowa", "ks": "kansas",
    "ky": "kentucky", "la": "louisiana", "me": "me", "md": "maryland",
    "ma": "massachusetts", "mi": "michigan", "mn": "minnesota",
    "ms": "ms", "mo": "missouri", "mt": "montana", "ne": "nebraska",
    "nv": "nv", "nh": "nh", "nj": "new-jersey", "nm": "new-mexico",
    "ny": "new-york", "nc": "north-carolina", "nd": "north-dakota",
    "oh": "ohio", "ok": "oklahoma", "or": "oregon", "pa": "pennsylvania",
    "ri": "ri", "sc": "south-carolina", "sd": "south-dakota",
    "tn": "tennessee", "tx": "texas", "ut": "utah", "vt": "vt",
    "va": "virginia", "wa": "washington", "wv": "west-virginia",
    "wi": "wisconsin", "wy": "wy",
}


def state_dir_for(project_id: str) -> str:
    """Derive the GCS state folder from the project id ({state}-sam-...)."""
    code = (project_id or "").split("-", 1)[0].lower()
    return STATE_DIRS.get(code, code or "unknown")


def upload_attachment_to_gcs(bucket, project_id: str, attachment: dict[str, Any]) -> str:
    """Returns 'uploaded', 'skipped' (already in GCS), or 'error'."""
    resource_id = attachment["resourceId"]
    name = attachment.get("name") or f"{resource_id}.bin"
    blob_path = f"{state_dir_for(project_id)}/{project_id}/{name}"
    blob = bucket.blob(blob_path)
    if blob.exists():
        print(f"  [skip] already in GCS: {blob_path}", file=sys.stderr)
        return "skipped"

    # The ?fn= hint is cosmetic (it only sets the download filename) but SAM
    # rejects the request outright when it contains characters quote() leaves
    # alone -- confirmed live 2026-08-04: names like
    # "... AHU cleaning SOW --5 Jun 2026.pdf" and "260427 SOW.pdf" returned
    # HTTP 400 Bad Request and were silently lost. quote() does not escape
    # "/" by default, so any name containing one breaks the query string.
    #
    # Retry without the hint rather than dropping the document: the resource_id
    # alone is what actually identifies the file.
    base = DOWNLOAD_URL.format(resource_id=resource_id)
    attempts = [
        f"{base}?fn={urllib.parse.quote(name, safe='')}",
        base,  # no filename hint at all
    ]
    data = None
    last_err: Exception | None = None
    for url in attempts:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
            break
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            last_err = e
            continue
    if data is None:
        print(f"  [error] download failed for {name}: {last_err}", file=sys.stderr)
        return "error"

    content_type = "application/pdf" if name.lower().endswith(".pdf") else "application/octet-stream"
    blob.upload_from_string(data, content_type=content_type)
    print(f"  [uploaded] {blob_path} ({len(data):,} bytes)", file=sys.stderr)
    return "uploaded"


def projects_from_db(limit: int = 0, only_missing: bool = True) -> list[dict[str, Any]]:
    """Select SAM projects from Postgres, shaped like the state-file records.

    WHY THIS EXISTS. The state files this script was written against have
    drifted from the database. On 2026-08-08 the whole crawl queue drained --
    50 of 50 crawl:sam items marked done, run reported success -- and document
    coverage did not move at all: 44.5% before and after, 2,592 documented
    projects before and after, 20,933 document rows before and after. Every
    item re-walked whatever data/states/{st}.json still contained, which had
    already been captured on 2026-08-05, found nothing new, and exited 0.

    A step that reads from a place the data no longer lives, and reports
    success either way, is the failure this repo keeps hitting. Reading from
    the same store the product serves from removes the drift entirely.

    only_missing skips projects that already hold documents. That is the whole
    point: 1,324 SAM projects have a parseable notice id and no documents, of
    which 946 are Solicitation or Combined Synopsis/Solicitation -- notice
    types that publish bid documents by definition.
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    from specindex import db  # noqa: PLC0415

    missing = ("""
           AND NOT EXISTS (SELECT 1 FROM project_document_files f
                            WHERE f.project_sk = p.project_sk)""" if only_missing else "")
    sql = f"""
        SELECT p.project_id,
               json_agg(json_build_object('url', s.source_url)) AS sources
          FROM projects p
          JOIN project_sources s ON s.project_sk = p.project_sk
         WHERE p.project_id LIKE '%%-sam-%%'
           AND s.source_url ~ 'sam\\.gov/workspace/contract/opp/[0-9a-f]{{32}}'
           {missing}
         GROUP BY p.project_id
         ORDER BY p.project_id
    """
    if limit:
        sql += f" LIMIT {int(limit)}"
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return [{"id": pid, "sources": srcs} for pid, srcs in cur.fetchall()]
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", default=str(ROOT / "data" / "states" / "ga.json"))
    parser.add_argument("--id-prefix", default="ga-sam", help="Only process projects whose id starts with this")
    parser.add_argument("--limit", type=int, default=0, help="Cap projects processed, 0 = no cap")
    parser.add_argument("--dry-run", action="store_true", help="List attachments found, don't upload")
    parser.add_argument("--from-db", action="store_true",
                        help="Select work from Postgres instead of a state file. Preferred: the "
                             "state files have drifted and re-walking them captures nothing.")
    parser.add_argument("--include-with-docs", action="store_true",
                        help="With --from-db, also re-check projects that already hold documents")
    args = parser.parse_args(argv)

    if args.from_db:
        projects = projects_from_db(limit=args.limit, only_missing=not args.include_with_docs)
        print(f"Processing {len(projects)} projects (from Postgres, "
              f"{'missing documents only' if not args.include_with_docs else 'all'})", file=sys.stderr)
    else:
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

    # FAIL LOUDLY ON A NO-OP. This exited 0 having captured nothing, 50 times
    # in a row, and the queue happily marked every item done -- coverage did
    # not move and nothing said so. "Assert the next step can see the output"
    # is a standing rule here; the cheapest version of it is refusing to call
    # a run successful when it selected work and produced none.
    #
    # Zero projects selected is fine and exits 0: it means the backlog is
    # drained, which is the goal. Selecting projects and uploading nothing new
    # is the case worth shouting about.
    if summary["projects_checked"] and not summary["files_uploaded"]:
        skipped = summary["files_skipped_existing"]
        if skipped:
            print(f"[verify] {summary['projects_checked']} projects checked, "
                  f"0 new files, {skipped} already held -- nothing new to capture",
                  file=sys.stderr)
            return 0
        print(f"::error::checked {summary['projects_checked']} projects and captured NOTHING "
              f"-- no new files and none already held. Either the notice ids are wrong or "
              f"SAM is refusing the attachment endpoint; this is not a successful run.",
              file=sys.stderr)
        return 1

    print(f"[verify] {summary['files_uploaded']} files uploaded across "
          f"{summary['projects_with_docs']} projects", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
