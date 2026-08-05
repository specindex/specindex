#!/usr/bin/env python3
"""Capture owner design-standards documents into GCS (step 8 for the row-4 source).

A manifest is a list of URLs, not a corpus. This repo's specific recurring
failure is proving a document path is reachable and never pulling from it --
that is how the corpus sat at 55 PDFs while "document wins" were being
reported. harvest-owner-standards.py produces the manifest; this script is the
half that actually moves bytes.

Storage: gs://specindex-ai-raw-documents/owner-standards/{state}/{slug}/{filename}

Transfer concurrency is capped LOW on purpose. Measured uplink here is
~150-250 KB/s: Snohomish capture at --workers 8 produced 0 uploads and
OSError 65 "No route to host" in 4 minutes, while --workers 3 produced 8
uploads in 3.3 minutes with zero errors. Small independent probes parallelize
well; large transfers invert once uplink is the constraint.

Credentials: prefers the service-account key, because user ADC expires and the
resulting failure reads as "this source has no documents" rather than as an
auth error.

Usage:
  python3 scripts/fetch-owner-standards-documents.py \\
      --manifest data/raw/owner_standards_manifest.json --workers 3
  ... --mep-only          # Divisions 21-28 only
  ... --limit 25 --dry-run
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import re
import sys
import threading
import urllib.parse
import urllib.request
from pathlib import Path

GCS_BUCKET = "specindex-ai-raw-documents"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
DIV_OF_INTEREST = {"21", "22", "23", "26", "27", "28"}

# A real document, verified by what the server actually returned. Status 200 is
# not evidence -- government and .edu hosts answer unknown paths with 200 and an
# HTML error page, which would land in the bucket as a "document".
DOC_CTYPES = ("application/pdf", "officedocument", "msword", "application/zip", "octet-stream")
MIN_BYTES = 2048

_print_lock = threading.Lock()


def log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def gcs_bucket():
    from google.cloud import storage  # noqa: PLC0415

    key = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if key and Path(key).is_file():
        try:
            bucket = storage.Client(project="specindex-ai").bucket(GCS_BUCKET)
            # Object-level probe. bucket.exists() needs storage.buckets.get,
            # which this SA deliberately lacks, and would make a working key
            # look broken.
            bucket.blob("_healthcheck/probe.txt").exists()
            log(f"[gcs] using service-account key {Path(key).name}")
            return bucket
        except Exception as e:  # noqa: BLE001
            log(f"[gcs] SA key unusable ({type(e).__name__}); falling back to ADC")
            os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    return storage.Client(project="specindex-ai").bucket(GCS_BUCKET)


def filename_for(url: str) -> str:
    name = urllib.parse.unquote(urllib.parse.urlparse(url).path.rsplit("/", 1)[-1])
    name = re.sub(r"[^A-Za-z0-9._\- ]+", "_", name).strip() or "document"
    return name[:150]


def fetch_one(doc: dict, bucket, dry_run: bool) -> tuple[str, str, int]:
    """Returns (status, url, bytes). Never raises -- one bad URL must not end a run."""
    url = doc["url"]
    blob_path = (f"owner-standards/{slug(doc.get('state') or 'unknown')}/"
                 f"{slug(doc.get('institution') or 'unknown')}/{filename_for(url)}")
    try:
        if not dry_run and bucket.blob(blob_path).exists():
            return "skip-exists", url, 0
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as resp:
            ctype = (resp.headers.get("Content-Type") or "").lower()
            body = resp.read()
        # Verify by content, not by status. An HTML error page returned with
        # 200 must never be stored as a document.
        if not any(c in ctype for c in DOC_CTYPES):
            return f"reject-ctype:{ctype[:28]}", url, len(body)
        if len(body) < MIN_BYTES:
            return f"reject-tiny:{len(body)}B", url, len(body)
        if dry_run:
            return "would-upload", url, len(body)
        blob = bucket.blob(blob_path)
        blob.upload_from_string(body, content_type=ctype.split(";")[0])
        return "uploaded", url, len(body)
    except Exception as e:  # noqa: BLE001
        return f"error:{type(e).__name__}", url, 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=3,
                    help="KEEP LOW. ~3 saturates the measured uplink; 8 produced OSError 65.")
    ap.add_argument("--mep-only", action="store_true", help="Divisions 21-28 only")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    data = json.loads(args.manifest.read_text())
    docs = data.get("documents", [])
    if args.mep_only:
        docs = [d for d in docs if set(d.get("divisions") or []) & DIV_OF_INTEREST]
    # Manufacturer lists first -- an owner's standing list of acceptable
    # manufacturers is the highest-value artifact this source can yield.
    docs.sort(key=lambda d: (not d.get("manufacturer_list"), d.get("institution", "")))
    seen, uniq = set(), []
    for d in docs:
        if d["url"] not in seen:
            seen.add(d["url"])
            uniq.append(d)
    docs = uniq[: args.limit] if args.limit else uniq

    log(f"documents to fetch: {len(docs)}  (workers={args.workers}, dry_run={args.dry_run})")
    bucket = None if args.dry_run else gcs_bucket()

    tally: dict[str, int] = {}
    total_bytes = 0
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(fetch_one, d, bucket, args.dry_run) for d in docs]
        for i, f in enumerate(cf.as_completed(futs), 1):
            status, url, nbytes = f.result()
            key = status.split(":")[0]
            tally[key] = tally.get(key, 0) + 1
            total_bytes += nbytes
            if key in ("uploaded", "would-upload") or i % 25 == 0:
                log(f"  [{i}/{len(docs)}] {status:22s} {nbytes:>9,}B  {url[:78]}")
            if key.startswith("error") and "OSError" in status:
                log(f"  !! {status} -- uplink may be saturated; lower --workers")

    log("\n=== SUMMARY ===")
    for k, v in sorted(tally.items(), key=lambda kv: -kv[1]):
        log(f"  {k:26s} {v}")
    log(f"  total bytes {total_bytes:,}")
    log(f"  gs://{GCS_BUCKET}/owner-standards/")
    log("OWNER STANDARDS CAPTURE COMPLETE")  # sentinel for wait loops
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
