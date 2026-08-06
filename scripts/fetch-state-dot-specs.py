#!/usr/bin/env python3
"""Capture every state DOT's Standard Specifications for construction.

WHY THIS EXISTS -- IT FELL OUT OF A BUG. The relevance filter rejected
`DOT2013.pdf` as "stale (2013 vs project 2026)". Downloading it showed what had
been thrown away: Georgia DOT's Standard Specifications, Construction of
Transportation Systems, 1,610 pages, 11.5MB, approved by the State
Transportation Board. It is the governing construction specification for every
GDOT project, and the 2013 edition still governs in 2026.

That is the single densest basis-of-design document class we have found, and
there are FIFTY of them -- one per state, public, stable, and needing no
crawler, no per-jurisdiction discovery and no meaningful search spend. A state
DOT spec book names materials, grades, test standards and approved-product
requirements across every division that matters for heavy civil and site work.

WHAT IT CHANGES ON THE RECORD PAGE. A Georgia project currently renders "no
manufacturer named in the 0 documents we hold". With the state spec book indexed
the page can state what the governing standard actually REQUIRES -- which is a
real answer to "is my product specified" for the whole class of state-funded
work, not a single project.

STILL NEVER A MANUFACTURER CLAIM. A standard specification states requirements,
approved-product lists and test methods. It does not say which manufacturer was
selected on a given job, and nothing downstream may present it as if it did.
This is Tier 1/Tier 2 material in the record-page sense -- requirements implied
by the governing standard -- and never Tier 3.

EDITIONS ARE NOT EXPIRIES. Do not apply recency filtering here. A 2013 edition
in force in 2026 is current, and treating its year as staleness is the exact bug
that hid this source in the first place.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

GCS_BUCKET = "specindex-ai-raw-documents"
UA = "Mozilla/5.0 SpecIndex-DocumentBot/1.0 (+https://specindex.ai)"

STATES = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
    "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho",
    "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana", "Maine",
    "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi",
    "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey",
    "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio",
    "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina",
    "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", "Virginia",
    "Washington", "West Virginia", "Wisconsin", "Wyoming",
]

# Title-page language of a genuine standard specification. Required before
# storing: a state DOT site will happily serve a 3-page "specification update
# memo" under a URL that looks identical to the 1,600-page book.
#
# `materials?` is singular-or-plural on purpose. The first version demanded
# "Construction and Materials Specifications" and so rejected Ohio DOT's
# 928-page "Construction and Material Specifications" -- a real spec book lost
# to one character. Same failure shape as the stale-year rule that hid this
# whole source: an over-tight rule returns a confident zero rather than an
# error.
SPEC_TITLE_RE = re.compile(
    r"standard\s+specifications?|specifications?\s+for\s+(?:road|highway|"
    r"bridge|construction)|construction\s+(?:and\s+materials?\s+)?specifications?|"
    r"materials?\s+(?:and\s+construction\s+)?specifications?",
    re.I,
)


def get(url: str, timeout: float = 180.0) -> tuple[int, bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, b"", ""
    except Exception:  # noqa: BLE001
        return 0, b"", ""


def first_pages_text(body: bytes, pages: int = 3) -> str:
    try:
        import io
        try:
            from pypdf import PdfReader
        except ImportError:
            from PyPDF2 import PdfReader
        r = PdfReader(io.BytesIO(body))
        return "\n".join((p.extract_text() or "") for p in r.pages[:pages]), len(r.pages)
    except Exception:  # noqa: BLE001
        return "", 0


def find_spec_urls(client, types, model: str, state: str) -> list[str]:
    prompt = (
        f"Search google for:\n"
        f"1. {state} Department of Transportation Standard Specifications for "
        f"Road and Bridge Construction, current edition\n"
        f"2. document links for me to download\n\n"
        "Output ONLY direct URLs ending in .pdf on the state DOT's own domain, "
        "one per line, max 4, no commentary. Prefer the complete book over "
        "individual sections or errata."
    )
    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())]),
    )
    return list(dict.fromkeys(re.findall(r"https?://[^\s\)\"'<>]+\.pdf", resp.text or "", re.I)))[:4]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--states", nargs="*", default=None)
    ap.add_argument("--model", default="gemini-3.6-flash")
    ap.add_argument("--min-pages", type=int, default=100,
                    help="a real spec book is hundreds of pages; below this it is a memo")
    ap.add_argument("--pause", type=float, default=1.5)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sentinel", default=None)
    args = ap.parse_args()

    from google import genai
    from google.genai import types

    client = genai.Client(
        vertexai=True,
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
    )

    bucket = None
    if not args.dry_run:
        from google.cloud import storage
        bucket = storage.Client().bucket(GCS_BUCKET)

    targets = args.states or STATES
    got = 0
    manifest: list[dict] = []

    for i, state in enumerate(targets, 1):
        try:
            urls = find_spec_urls(client, types, args.model, state)
        except Exception as e:  # noqa: BLE001
            print(f"[{state}] search error: {type(e).__name__}", flush=True)
            continue

        stored = False
        for u in urls:
            st, body, _ = get(u)
            time.sleep(args.pause)
            if st != 200 or not body[:5].startswith(b"%PDF"):
                continue
            text, pages = first_pages_text(body)
            # Both gates required: a spec book is long AND says what it is.
            # Length alone admits a 400-page bid-tab; title alone admits a memo.
            if pages < args.min_pages or not SPEC_TITLE_RE.search(text[:4000]):
                print(f"[{state}] skip ({pages}p, title mismatch): {u[:78]}", flush=True)
                continue

            print(f"[{state}] KEEP {pages:,}p {len(body)/1e6:.1f}MB {u[:70]}", flush=True)
            manifest.append({"state": state, "url": u, "pages": pages, "bytes": len(body)})
            got += 1
            stored = True
            if not args.dry_run:
                digest = hashlib.sha256(body).hexdigest()
                blob = bucket.blob(f"content/{digest}.pdf")
                if not blob.exists():
                    blob.upload_from_string(body, content_type="application/pdf")
            break
        if not stored:
            print(f"[{state}] no spec book found ({len(urls)} candidates)", flush=True)
        if i % 5 == 0:
            print(f"--- {i}/{len(targets)} states, {got} spec books ---", flush=True)

    out = ROOT / "data" / "raw" / "state_dot_specs.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    import json
    out.write_text(json.dumps(manifest, indent=2))
    total_pages = sum(m["pages"] for m in manifest)
    print(f"\n[done] {got}/{len(targets)} state DOT spec books, {total_pages:,} pages", flush=True)
    if args.sentinel:
        Path(args.sentinel).write_text(f"done {got} books\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
