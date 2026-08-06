#!/usr/bin/env python3
"""Register jurisdiction-level standards and extract their text.

THE GAP THIS CLOSES. fetch-state-dot-specs.py uploads spec books to GCS and
writes a manifest. Nothing else reads either one. A state DOT spec book sitting
in a bucket is invisible to every query in the product -- it is captured and
unusable, which is indistinguishable from never having fetched it. This repo has
already been bitten by exactly that shape: 78% of captured documents were
invisible downstream because capture never wrote to the database.

So this script is the seam, and it asserts the next step can see its output
rather than assuming it.

WHY A SEPARATE TABLE. project_document_files requires a project_sk. A state DOT
standard specification does not belong to one project -- it governs EVERY
state-funded project in that state, including ones not yet ingested. Forcing it
into a project row would either duplicate a 2,050-page book thousands of times
or attach it arbitrarily to one job. reference_documents holds documents scoped
to a JURISDICTION, and the record page joins on (state) rather than on project.

WHAT IT UNLOCKS. A Georgia project currently renders "no manufacturer named in
the 0 documents we hold". With GDOT's 2,050 pages indexed the page can state
what the governing standard REQUIRES -- materials, grades, test standards,
approved-product criteria by division. That is a real answer to "is my product
specified" for the whole class of state-funded work.

IT IS STILL NOT A MANUFACTURER CLAIM. A standard states requirements and
approved-product criteria. It does not say who was selected on a given job.
Tier 1/Tier 2 in the record-page sense, never Tier 3.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from specindex.db import connect  # noqa: E402

GCS_BUCKET = "specindex-ai-raw-documents"
UA = "Mozilla/5.0 SpecIndex-DocumentBot/1.0 (+https://specindex.ai)"

# Schema lives in db/migrations/052_reference_documents.sql, not here -- a
# script that CREATEs its own table drifts from the migration the moment either
# changes, and then two environments disagree about what the column is called.
DDL = "SELECT 1"

STATE_ABBR = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE",
    "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ",
    "New Mexico": "NM", "New York": "NY", "North Carolina": "NC",
    "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
    "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
    "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}


def fetch(url: str, timeout: float = 300.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception:  # noqa: BLE001
        return b""


def page_texts(body: bytes) -> list[str]:
    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader
    reader = PdfReader(io.BytesIO(body))
    return [(p.extract_text() or "") for p in reader.pages]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="data/raw/state_dot_specs.json")
    ap.add_argument("--doc-kind", default="dot_standard_specifications")
    ap.add_argument("--wait-sentinel", default=None,
                    help="poll for this file before starting (bounded)")
    ap.add_argument("--wait-minutes", type=int, default=180)
    ap.add_argument("--skip-extract", action="store_true")
    args = ap.parse_args()

    if args.wait_sentinel:
        s = Path(args.wait_sentinel)
        # Bounded wait: an unbounded loop on a sentinel that never appears is a
        # silent hang, and this repo has deadlocked on exactly that before.
        for i in range(args.wait_minutes * 2):
            if s.exists():
                print(f"[wait] sentinel found after {i//2} min", flush=True)
                break
            time.sleep(30)
        else:
            print(f"[wait] TIMEOUT after {args.wait_minutes} min -- "
                  f"proceeding with whatever the manifest holds", flush=True)

    mpath = ROOT / args.manifest
    if not mpath.exists():
        print(f"[error] no manifest at {mpath}", file=sys.stderr)
        return 1
    entries = json.loads(mpath.read_text())
    print(f"[scope] {len(entries)} reference documents in manifest", flush=True)

    from google.cloud import storage
    bucket = storage.Client().bucket(GCS_BUCKET)

    conn = connect()
    cur = conn.cursor()
    cur.execute(DDL)
    conn.commit()

    registered = extracted = pages_total = 0
    for e in entries:
        state = e.get("state", "")
        abbr = STATE_ABBR.get(state, state[:2].upper())
        url = e["url"]

        cur.execute("SELECT id, text_extracted FROM reference_documents WHERE url = %s", (url,))
        row = cur.fetchone()
        if row and row[1]:
            print(f"  [skip] {state}: already registered and extracted", flush=True)
            continue

        body = fetch(url)
        if not body[:5].startswith(b"%PDF"):
            print(f"  [fail] {state}: not a PDF on refetch", flush=True)
            continue

        digest = hashlib.sha256(body).hexdigest()
        blob_path = f"content/{digest}.pdf"
        blob = bucket.blob(blob_path)
        if not blob.exists():
            blob.upload_from_string(body, content_type="application/pdf")

        texts = [] if args.skip_extract else page_texts(body)
        n_pages = len(texts) if texts else e.get("pages", 0)

        cur.execute(
            """
            INSERT INTO reference_documents
                (scope, scope_value, doc_kind, title, url, gcs_path,
                 content_sha256, page_count, byte_size, text_extracted)
            VALUES ('state', %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (url) DO UPDATE SET
                gcs_path = EXCLUDED.gcs_path,
                content_sha256 = EXCLUDED.content_sha256,
                page_count = EXCLUDED.page_count,
                byte_size = EXCLUDED.byte_size,
                text_extracted = EXCLUDED.text_extracted,
                fetched_at = now()
            RETURNING id
            """,
            (abbr, args.doc_kind, f"{state} DOT Standard Specifications",
             url, blob_path, digest, n_pages, len(body), bool(texts)),
        )
        doc_id = cur.fetchone()[0]
        registered += 1

        if texts:
            cur.execute("DELETE FROM document_pages WHERE reference_document_id = %s", (doc_id,))
            kept = 0
            for i, t in enumerate(texts, 1):
                if not t.strip():
                    continue
                cur.execute(
                    """
                    INSERT INTO document_pages
                        (reference_document_id, page_number, raw_text, ocr_engine)
                    VALUES (%s, %s, %s, 'native')
                    """,
                    (doc_id, i, t),
                )
                kept += 1
            extracted += 1
            pages_total += kept
            print(f"  [ok] {state} ({abbr}): {n_pages:,} pages, {kept:,} with text", flush=True)
        conn.commit()

    # ASSERT THE NEXT STEP CAN SEE THIS. A registration that succeeds into a
    # place nothing reads from is indistinguishable from one that never ran.
    cur.execute("SELECT count(*) FROM reference_documents WHERE text_extracted")
    docs_visible = cur.fetchone()[0]
    cur.execute("""SELECT count(*) FROM document_pages
                   WHERE reference_document_id IS NOT NULL""")
    pages_visible = cur.fetchone()[0]
    print(f"\n[done] registered={registered} extracted={extracted} pages={pages_total:,}")
    print(f"[verify] readable downstream: {docs_visible} documents, {pages_visible:,} pages")
    if registered and not pages_visible:
        print("STOP: registered documents but no page is readable downstream", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
