#!/usr/bin/env python3
"""Pull attachments from Legistar legislative matters and hold them.

WHY THIS IS THE BIGGEST SINGLE LEVER AVAILABLE. NYC's Legistar client covers all
five boroughs, and after the 2026-08-06 relabel those are 212,985 in-window
projects with zero documents -- 43% of the entire gap. The NYC Council issued a
read token on request, and the data is the right SHAPE, not merely present:

    "310 East 4th Street, Block 373, Lot 8, Manhattan"     4 attachments
    "655 New York Ave, Block 4280, Lot 1, Brooklyn"        5 attachments
    "Malcolm X II Phase A, Block 2011, Lot 38, Manhattan"  5 attachments

Land-use matters carry the street address and the block/lot in the title, which
is the most directly matchable form to the permit records we already hold. 28
attachments across 5 sampled matters.

CAPTURE IS DELIBERATELY DECOUPLED FROM MATCHING. Nothing here decides which
project a document belongs to. Address matching is a real join with real failure
modes, and making capture depend on it would discard documents for projects not
yet ingested -- and a document never fetched is gone once the jurisdiction
rotates its site, while a held document with no project attached is an asset.
project_sk stays NULL until a separate, re-runnable matcher fills it.

SERVER-SIDE DATE FILTER, VERIFIED. `$filter=MatterIntroDate gt datetime'...'`
works and is used. Without it this pulls decades of legislative history to find
the 2025+ slice, which is both wasteful and rude to the host.

TOKENS ARE PER-JURISDICTION AND NEVER LOGGED. NYC requires one; most clients do
not. The token goes in the query string because that is the only interface
Legistar offers, so it must never reach a log line -- every printed URL here is
scrubbed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from specindex.db import connect  # noqa: E402

API = "https://webapi.legistar.com/v1"
GCS_BUCKET = "specindex-ai-raw-documents"
UA = "Mozilla/5.0 SpecIndex-DocumentBot/1.0 (+https://specindex.ai)"

# Slugs proven live on 2026-08-06. NYC needs a token; the rest are open.
DEFAULT_SLUGS = [
    "nyc", "lacounty", "miamidade", "columbus", "cincinnatioh",
    "harriscountytx", "clark", "kingcounty", "sacramento", "denver",
    "erie", "hennepinmn", "riversidecountyca",
]

# Land-use / construction signal in a matter title. A city council's docket is
# mostly proclamations, appointments and budget items; those carry attachments
# too, and storing them buries the documents that matter.
RELEVANT_MATTER = re.compile(
    r"\bblock\b|\blot\b|zoning|rezon|land use|ULURP|site plan|"
    r"special permit|variance|construction|development|building|"
    r"landmark|subdivision|plat\b|street|avenue|boulevard|road\b|drive\b",
    re.I,
)


# Attachment-level exclusions. The MATTER filter is necessarily loose -- a
# land-use item is found by words like "zoning" and "landmark" -- but the same
# words appear on the SUBCOMMITTEE CALENDAR attached to every one of those
# matters. In a 30-matter sample the identical calendar PDF came back 7 times
# under 7 URLs. A calendar is not a project document, and storing it 7 times
# buries the approval letter that is.
_SKIP_ATTACHMENT = re.compile(
    r"^calendar\b|meeting\s+calendar|agenda\s+of|minutes\b|"
    r"roll\s+call|attendance|hearing\s+notice\s+only",
    re.I,
)


def scrub(u: str) -> str:
    """Never let a token reach a log line."""
    return re.sub(r"token=[^&]+", "token=***", u)


def api_get(path: str, token: str | None, params: dict | None = None) -> list | dict | None:
    q = dict(params or {})
    if token:
        q["token"] = token
    url = f"{API}/{path}"
    if q:
        url += "?" + urllib.parse.urlencode(q, safe="$' ")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except Exception as e:  # noqa: BLE001
        print(f"    [api-error] {type(e).__name__} {scrub(url)[:110]}", flush=True)
        return None


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read()
    except Exception:  # noqa: BLE001
        return b""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slugs", nargs="*", default=DEFAULT_SLUGS)
    ap.add_argument("--since", default="2025-01-01")
    ap.add_argument("--max-matters", type=int, default=800, help="per jurisdiction")
    ap.add_argument("--pause", type=float, default=0.35)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sentinel", default=None)
    args = ap.parse_args()

    bucket = None
    if not args.dry_run:
        from google.cloud import storage
        bucket = storage.Client().bucket(GCS_BUCKET)
    conn = connect()
    cur = conn.cursor()

    grand_docs = 0
    for slug in args.slugs:
        token = os.environ.get(f"LEGISTAR_TOKEN_{slug.upper()}")
        matters = api_get(
            f"{slug}/matters", token,
            {"$top": args.max_matters,
             "$filter": f"MatterIntroDate gt datetime'{args.since}'",
             "$orderby": "MatterIntroDate desc"},
        )
        if not isinstance(matters, list) or not matters:
            print(f"[{slug}] no matters since {args.since}", flush=True)
            continue

        relevant = [m for m in matters if RELEVANT_MATTER.search(str(m.get("MatterTitle") or ""))]
        print(f"[{slug}] {len(matters)} matters since {args.since}, "
              f"{len(relevant)} land-use/construction flavoured", flush=True)

        docs = 0
        seen_sha: set[str] = set()
        for n, m in enumerate(relevant, 1):
            mid = m.get("MatterId")
            title = str(m.get("MatterTitle") or "")[:1000]
            mdate = (m.get("MatterIntroDate") or "")[:10] or None
            atts = api_get(f"{slug}/matters/{mid}/attachments", token)
            time.sleep(args.pause)
            if not isinstance(atts, list):
                continue
            for a in atts:
                link = a.get("MatterAttachmentHyperlink") or ""
                name = str(a.get("MatterAttachmentName") or "")[:500]
                if not link or _SKIP_ATTACHMENT.search(name):
                    continue
                cur.execute("SELECT 1 FROM legislative_documents WHERE url = %s", (link,))
                if cur.fetchone():
                    continue
                body = fetch_bytes(link)
                time.sleep(args.pause)
                # Content check, never status: Legistar's View.ashx returns 200
                # and an HTML error page for a withdrawn attachment.
                if not body[:5].startswith(b"%PDF"):
                    continue
                digest_early = hashlib.sha256(body).hexdigest()
                # Dedupe on CONTENT, not URL. Legistar links the same PDF from
                # every matter it relates to, so URL-uniqueness alone stores one
                # document many times and inflates the count with copies.
                cur.execute(
                    "SELECT 1 FROM legislative_documents "
                    "WHERE content_sha256 = %s AND jurisdiction = %s",
                    (digest_early, slug),
                )
                if cur.fetchone():
                    continue
                if digest_early in seen_sha:
                    continue
                seen_sha.add(digest_early)
                docs += 1
                grand_docs += 1
                if args.dry_run:
                    print(f"    [would-store] {name[:56]} ({len(body):,}B)", flush=True)
                    continue
                digest = digest_early
                blob = bucket.blob(f"content/{digest}.pdf")
                if not blob.exists():
                    blob.upload_from_string(body, content_type="application/pdf")
                cur.execute(
                    """
                    INSERT INTO legislative_documents
                        (jurisdiction, matter_id, matter_title, matter_date,
                         attachment_name, url, gcs_path, content_sha256, byte_size)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (url) DO NOTHING
                    """,
                    (slug, mid, title, mdate, name, link,
                     f"content/{digest}.pdf", digest, len(body)),
                )
            if n % 25 == 0:
                conn.commit()
                print(f"  [{slug} {n}/{len(relevant)}] docs={docs}", flush=True)
        conn.commit()
        print(f"[{slug}] DONE docs={docs}", flush=True)

    # Assert the next step can see this.
    cur.execute("SELECT count(*), count(DISTINCT jurisdiction) FROM legislative_documents")
    total, juris = cur.fetchone()
    print(f"\n[done] stored this run={grand_docs}; table holds {total:,} documents "
          f"across {juris} jurisdictions", flush=True)
    # Dry runs store nothing by design, so an empty table is the CORRECT result
    # there -- firing the guard on it trains everyone to ignore the guard.
    if not args.dry_run and grand_docs and not total:
        print("STOP: stored documents are not readable back", file=sys.stderr)
        return 1
    if args.sentinel:
        Path(args.sentinel).write_text(f"done {grand_docs}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
