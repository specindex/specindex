#!/usr/bin/env python3
"""Pipeline step 7/8: pull real Snohomish County WA (PDS) permit documents
straight to GCS -- no local copy of the binaries.

Snohomish County PDS Online Records (https://snoco.org/pdspublicrecords/)
is an OpenText Content Server repository fronted by an *unauthenticated*
SOAP proxy at https://snoco.org/pdspublicrecords/otws/otlinkerws.asmx.
No login, no API key, no CAPTCHA. The join key is PFN -- the county permit
file number ("25 103203 CBP") that WA-SNOHOMISH / WA-SNOHOMISH-REVIEW
already store as the project id suffix (wa-snohomish-pds-25-103203-cbp).

Two calls, both verified live 2026-08-03:

  search    POST otlinkerws.asmx  SOAPAction http://tempuri.org/GetData
            <hostUrl>recordsportal/search/100/2847417/{urlencoded OT query}</hostUrl>
            where the permit-number attribute is Attr_296923_2, i.e. the
            query is 'Attr_296923_2 : "25 103203 CBP"'. Returns an
            <Output><SearchResults> tree, one <SearchResult> per document
            with OTObject ("DataId=8875553&Version=1"), OTName (real
            filename), OTMIMEType, OTDataSize, and two useful description
            attributes: Attr_297142_3 ("Approved Building Plan Set",
            "Structural or Lateral Calculations", "Geotechnical Report"...)
            and Attr_297142_4 (review stage: "Approvals & Decisions",
            "1st Review"...).

  download  POST otlinkerws.asmx  SOAPAction http://tempuri.org/SaveFile
            <hostUrl>recordsportal/getnode/{DataId}</hostUrl>
            <docType>application%20pdf</docType>
            <fileName>{filename, lowercased}</fileName>
            -- this stages the file server-side, then
            GET https://snoco.org/pdspublicrecords/tDocs/{filename lowercased}
            returns the real bytes (confirmed %PDF-1.7, incl. a 17.8 MB
            approved plan set). The lowercasing is not cosmetic: the SOAP
            call writes the staged file under the lowercased name and the
            tDocs GET is case-sensitive.

Storage: gs://specindex-ai-raw-documents/washington/{project_id}/{filename}
-- the same {state}/{project_id}/{filename} layout fetch-sam-gov-documents.py
uses and that compute-project-documents.py's files_from_gcs() already scans,
so no parser change is needed anywhere downstream to get these into
project_documents / project_document_files. Per Asif's standing instruction
(2026-07-28) bytes go straight from the HTTP response into the upload call;
nothing is staged on local disk. Only a small JSON manifest is written
locally (data/documents/wa-snohomish/manifest.json) as the checked-in record
of what was pulled.

Credentials note: the GOOGLE_APPLICATION_CREDENTIALS service account
(claude-cloudsql@specindex-ai) has Cloud SQL + Vertex but *not*
storage.objects.create on this bucket (403, verified 2026-08-03), so
--credentials adc (the default) ignores it and uses the gcloud user ADC,
which does have access. Pass --credentials env to force the service account.

Document triage: a permit folder is 12-213 documents and most of the tail is
trivia (transaction statements, customer bills, inspection cards). Documents
are tiered by their PDS description (see DOC_TIERS) and only tiers 1-2 are
pulled by default -- plan sets, structural/geotech/energy calcs, civil and
architectural drawings, narratives, approval letters. --tiers 1,2,3 pulls
everything.

Usage:
    python3 scripts/fetch-snohomish-documents.py --limit 2 --dry-run
    python3 scripts/fetch-snohomish-documents.py --limit 2
    python3 scripts/fetch-snohomish-documents.py --limit 50 --max-docs-per-project 6
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import xml.sax.saxutils as saxutils
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ASMX = "https://snoco.org/pdspublicrecords/otws/otlinkerws.asmx"
TDOCS = "https://snoco.org/pdspublicrecords/tDocs/"
SEARCH_HOST = "recordsportal/search/100/2847417/"
PERMIT_ATTR = "Attr_296923_2"
GCS_BUCKET = "specindex-ai-raw-documents"
GCS_STATE_DIR = "washington"
MANIFEST_PATH = ROOT / "data" / "documents" / "wa-snohomish" / "manifest.json"
USER_AGENT = "Mozilla/5.0 SpecIndex-DocumentBot/1.0 (+https://specindex.ai)"

# id suffix -> PFN, e.g. wa-snohomish-pds-review-25-103203-cbp -> "25 103203 CBP"
PFN_RE = re.compile(r"-(\d{2})-(\d{4,7})-([a-z]{3})$")

# Tier 1: the real spec-window value -- drawings, plan sets, engineering
# calcs, geotech/environmental reports. Tier 2: contextual paperwork worth
# having (narratives, approval/correction letters, applications). Tier 3:
# transactional trivia (bills, receipts, inspection cards, generic
# "Report.pdf" transaction statements) -- skipped by default.
DOC_TIERS: list[tuple[int, list[str]]] = [
    (
        1,
        [
            "plan set", "plans", "plan", "drawing", "architectural", "civil",
            "structural", "lateral", "geotech", "soils", "energy", "calculation",
            "calcs", "landscape", "site development", "grading", "drainage",
            "stormwater", "mechanical", "plumbing", "electrical", "fire sprinkler",
            "fire alarm", "truss", "specification", "survey", "elevation",
            "septic", "critical area", "wetland", "traffic", "environmental",
        ],
    ),
    (
        2,
        [
            "narrative", "letter", "approval", "correction", "review comment",
            "application", "affidavit", "covenant", "easement", "agreement",
            "certificate", "notice of decision", "conditions", "checklist",
            "worksheet", "statement of special inspection", "special inspection",
        ],
    ),
]
TIER3_HINTS = [
    "customer bill", "transaction statement", "receipt", "invoice", "fee",
    "inspection card", "inspection record", "inspection history", "placard",
    "photo", "email", "correspondence", "label",
]


def _soap(action: str, body: str, timeout: float = 120.0) -> str:
    envelope = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
        ' xmlns:xsd="http://www.w3.org/2001/XMLSchema"'
        ' xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        f"<soap:Body>{body}</soap:Body></soap:Envelope>"
    )
    req = urllib.request.Request(
        ASMX,
        data=envelope.encode("utf-8"),
        headers={
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": f"http://tempuri.org/{action}",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def pfn_for(project_id: str) -> str | None:
    m = PFN_RE.search(project_id)
    if not m:
        return None
    return f"{m.group(1)} {m.group(2)} {m.group(3).upper()}"


def _text(node: ET.Element | None) -> str:
    return (node.text or "").strip() if node is not None else ""


def search_documents(pfn: str) -> list[dict[str, Any]]:
    """Returns one dict per document in the permit's OpenText folder."""
    query = urllib.parse.quote(f'{PERMIT_ATTR} : "{pfn}"', safe="")
    host = SEARCH_HOST + query
    body = f'<GetData xmlns="http://tempuri.org/"><hostUrl>{saxutils.escape(host)}</hostUrl></GetData>'
    raw = _soap("GetData", body)
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        print(f"  [error] unparseable search response for {pfn!r}: {e}", file=sys.stderr)
        return []
    results = root.find(".//SearchResults")
    if results is None:
        return []

    docs: list[dict[str, Any]] = []
    for r in results:
        obj = _text(r.find("OTObject"))  # "DataId=8875553&Version=1"
        m = re.search(r"DataId=(\d+)", obj)
        name = _text(r.find("OTName"))
        if not m or not name:
            continue
        size = _text(r.find("OTDataSize"))
        docs.append(
            {
                "object_id": m.group(1),
                "filename": name,
                "description": _text(r.find("Attr_297142_3")),
                "stage": _text(r.find("Attr_297142_4")),
                "folder_name": _text(r.find("Attr_296923_6")),
                "permit_status": _text(r.find("Attr_296923_16")),
                "mime_type": _text(r.find("OTMIMEType")) or "application/pdf",
                "reported_size": int(size) if size.isdigit() else None,
                "doc_date": _text(r.find("OTObjectDate")),
            }
        )
    return docs


def tier_for(doc: dict[str, Any]) -> int:
    haystack = f"{doc.get('description', '')} {doc.get('filename', '')}".lower()
    haystack = re.sub(r"[_\-]+", " ", haystack)
    for hint in TIER3_HINTS:
        if hint in haystack:
            return 3
    for tier, keywords in DOC_TIERS:
        if any(kw in haystack for kw in keywords):
            return tier
    return 3


def download(doc: dict[str, Any], timeout: float = 300.0) -> bytes:
    """SaveFile stages the object server-side under the lowercased filename,
    then a plain GET on /tDocs/ returns the bytes."""
    low = doc["filename"].lower()
    body = (
        '<SaveFile xmlns="http://tempuri.org/">'
        f'<hostUrl>{saxutils.escape("recordsportal/getnode/" + doc["object_id"])}</hostUrl>'
        "<docType>application%20pdf</docType>"
        f"<fileName>{saxutils.escape(low)}</fileName>"
        "</SaveFile>"
    )
    _soap("SaveFile", body, timeout=timeout)
    # Filenames coming out of AMANDA contain '+' as a word separator
    # ("...CBP+Architectural_Plan+8.2.2021..."). Percent-encoding it (the
    # urllib default) 404s against tDocs on some of those, so try the
    # literal-'+' form as a fallback before giving up -- real 404 seen live
    # 2026-08-03 on 431751_21102878CBP+Architectural_Plan+....pdf.
    candidates = [urllib.parse.quote(low), urllib.parse.quote(low, safe="+")]
    last_error: Exception | None = None
    for candidate in dict.fromkeys(candidates):
        req = urllib.request.Request(TDOCS + candidate, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            last_error = e
            if e.code != 404:
                raise
    raise last_error if last_error else RuntimeError("no download candidate tried")


def gcs_bucket(mode: str):
    if mode == "adc":
        # The step-8 service account is Cloud SQL + Vertex only; it 403s on
        # storage.objects.create for this bucket. Dropping the env var makes
        # google-cloud-storage fall back to the gcloud user ADC.
        os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    from google.cloud import storage

    return storage.Client(project="specindex-ai").bucket(GCS_BUCKET)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state-file", default=str(ROOT / "data" / "states" / "wa.json"))
    ap.add_argument("--id-prefix", default="wa-snohomish", help="only process projects whose id starts with this")
    ap.add_argument("--limit", type=int, default=0, help="cap projects processed, 0 = no cap")
    ap.add_argument("--offset", type=int, default=0, help="skip this many projects first (resume)")
    ap.add_argument("--max-docs-per-project", type=int, default=4)
    # 15 MB by default, not "everything": measured live 2026-08-03, snoco.org
    # serves the big approved plan sets at a trickle (a 52 MB set was still
    # streaming after 13 minutes). Bounding per-document size buys breadth
    # across many permits instead of hours spent on a handful of giants --
    # raise it for a targeted deep pull on specific projects.
    ap.add_argument("--max-bytes-per-doc", type=int, default=15 * 1024 * 1024)
    ap.add_argument("--tiers", default="1,2", help="comma-separated document tiers to pull (see DOC_TIERS)")
    ap.add_argument("--sleep", type=float, default=1.0, help="seconds between requests to snoco.org")
    ap.add_argument("--max-consecutive-errors", type=int, default=8, help="stop early if the server starts failing")
    ap.add_argument("--credentials", choices=["adc", "env"], default="adc")
    # Parallel shards (disjoint --offset windows) must not write the same
    # manifest concurrently -- give each its own and merge after.
    ap.add_argument("--manifest-path", default=str(MANIFEST_PATH))
    ap.add_argument("--dry-run", action="store_true", help="search only; list documents, upload nothing")
    args = ap.parse_args(argv)

    wanted_tiers = {int(t) for t in args.tiers.split(",") if t.strip()}
    data = json.loads(Path(args.state_file).read_text())
    projects = [p for p in data["projects"] if p["id"].startswith(args.id_prefix)]
    projects = projects[args.offset :]
    if args.limit:
        projects = projects[: args.limit]
    print(f"Processing {len(projects)} project(s) (prefix={args.id_prefix!r}, tiers={sorted(wanted_tiers)})", file=sys.stderr)

    bucket = None if args.dry_run else gcs_bucket(args.credentials)

    manifest_path = Path(args.manifest_path)
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    by_project: dict[str, Any] = manifest.get("by_project", {})

    summary = {
        "projects_attempted": 0,
        "projects_with_docs_found": 0,
        "projects_with_docs_captured": 0,
        "docs_found": 0,
        "docs_selected": 0,
        "docs_uploaded": 0,
        "docs_skipped_existing": 0,
        "docs_skipped_tier": 0,
        "docs_skipped_cap": 0,
        "docs_skipped_too_large": 0,
        "errors": 0,
        "bytes_uploaded": 0,
    }
    consecutive_errors = 0

    for project in projects:
        pid = project["id"]
        pfn = pfn_for(pid)
        summary["projects_attempted"] += 1
        if not pfn:
            print(f"  [skip] {pid}: no PFN parseable from id", file=sys.stderr)
            continue
        try:
            docs = search_documents(pfn)
            consecutive_errors = 0
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
            summary["errors"] += 1
            consecutive_errors += 1
            print(f"  [error] search failed for {pfn}: {e}", file=sys.stderr)
            if consecutive_errors >= args.max_consecutive_errors:
                print("  [abort] too many consecutive errors -- stopping early", file=sys.stderr)
                break
            time.sleep(args.sleep)
            continue
        time.sleep(args.sleep)

        summary["docs_found"] += len(docs)
        if not docs:
            continue
        summary["projects_with_docs_found"] += 1

        for d in docs:
            d["tier"] = tier_for(d)
        selected = [d for d in docs if d["tier"] in wanted_tiers]
        summary["docs_skipped_tier"] += len(docs) - len(selected)
        # Size-filter *before* the per-project cap, so oversized plan sets
        # don't eat the budget and then get skipped, leaving the project
        # with nothing.
        oversized = [d for d in selected if (d.get("reported_size") or 0) > args.max_bytes_per_doc]
        if oversized:
            summary["docs_skipped_too_large"] += len(oversized)
            selected = [d for d in selected if d not in oversized]
        selected.sort(key=lambda d: (d["tier"], -(d.get("reported_size") or 0)))
        if args.max_docs_per_project and len(selected) > args.max_docs_per_project:
            summary["docs_skipped_cap"] += len(selected) - args.max_docs_per_project
            selected = selected[: args.max_docs_per_project]
        summary["docs_selected"] += len(selected)

        print(f"{pid} (PFN {pfn}): {len(docs)} doc(s) in folder, {len(selected)} selected", file=sys.stderr)
        if args.dry_run:
            for d in selected:
                print(f"    - [t{d['tier']}] {d['description']!r} {d['filename']} ({d.get('reported_size') or 0:,} B)", file=sys.stderr)
            continue

        entry = by_project.setdefault(pid, {"pfn": pfn, "documents": []})
        entry["folder_name"] = docs[0].get("folder_name") or entry.get("folder_name")
        entry["permit_status"] = docs[0].get("permit_status") or entry.get("permit_status")
        entry["documents_in_folder"] = len(docs)
        have = {doc["filename"] for doc in entry["documents"]}
        captured_any = False

        for d in selected:
            if d["filename"] in have:
                summary["docs_skipped_existing"] += 1
                captured_any = True
                continue
            if d.get("reported_size") and d["reported_size"] > args.max_bytes_per_doc:
                summary["docs_skipped_too_large"] += 1
                print(f"    [skip] too large ({d['reported_size']:,} B): {d['filename']}", file=sys.stderr)
                continue

            blob_path = f"{GCS_STATE_DIR}/{pid}/{d['filename']}"
            blob = bucket.blob(blob_path)
            if blob.exists():
                summary["docs_skipped_existing"] += 1
                captured_any = True
                continue
            started = time.monotonic()
            try:
                payload = download(d)
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
                summary["errors"] += 1
                # A 404 is a per-file quirk (odd staged filename), not the
                # server pushing back -- don't let a run of them trip the
                # throttling circuit-breaker.
                if not (isinstance(e, urllib.error.HTTPError) and e.code == 404):
                    consecutive_errors += 1
                print(f"    [error] download failed for {d['filename']}: {e}", file=sys.stderr)
                if consecutive_errors >= args.max_consecutive_errors:
                    print("  [abort] too many consecutive errors -- stopping early", file=sys.stderr)
                    break
                time.sleep(args.sleep)
                continue
            consecutive_errors = 0
            time.sleep(args.sleep)

            if not payload:
                summary["errors"] += 1
                continue
            try:
                # Plan sets run 20-50 MB; the client's 120s default timeout
                # (and its 100MB single-shot chunk) reliably RetryErrors on
                # those over a home uplink -- verified live 2026-08-03 on a
                # 52 MB approved plan set. Chunked resumable upload with a
                # long per-chunk timeout instead.
                blob.chunk_size = 8 * 1024 * 1024
                blob.upload_from_string(payload, content_type=d["mime_type"], timeout=600)
            except Exception as e:  # noqa: BLE001 -- upload failures shouldn't kill the run
                summary["errors"] += 1
                print(f"    [error] upload failed for {d['filename']}: {e}", file=sys.stderr)
                continue
            digest = hashlib.sha256(payload).hexdigest()
            summary["docs_uploaded"] += 1
            summary["bytes_uploaded"] += len(payload)
            captured_any = True
            print(
                f"    [uploaded] {blob_path} ({len(payload):,} B, {time.monotonic() - started:.1f}s)",
                file=sys.stderr,
            )
            entry["documents"].append(
                {
                    "filename": d["filename"],
                    "title": d["description"] or d["filename"],
                    "url": f"https://storage.googleapis.com/{GCS_BUCKET}/{urllib.parse.quote(blob_path)}",
                    "gcs_path": blob_path,
                    "content_type": d["mime_type"],
                    "size_bytes": len(payload),
                    "content_sha256": digest,
                    "tier": d["tier"],
                    "pds_stage": d["stage"],
                    "pds_object_id": d["object_id"],
                    "doc_date": d["doc_date"],
                }
            )
        if captured_any:
            summary["projects_with_docs_captured"] += 1

        if not args.dry_run:
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "source": "Snohomish County WA PDS Online Records (OpenText Content Server SOAP proxy)",
                        "endpoint": ASMX,
                        "gcs_prefix": f"gs://{GCS_BUCKET}/{GCS_STATE_DIR}/",
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "by_project": by_project,
                    },
                    indent=2,
                )
                + "\n"
            )
        if consecutive_errors >= args.max_consecutive_errors:
            break

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
