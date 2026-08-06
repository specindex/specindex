#!/usr/bin/env python3
"""Crawl a municipal CMS's meeting/event pages and capture every attached PDF.

WHY A CRAWLER RATHER THAN MORE SEARCHING. find-project-documents.py answers
"where are the documents for THIS project" and bills a grounded search query for
every project it asks about. Measured on the corpus, 494,327 in-window projects
hold zero documents, so sweeping them that way is roughly a $17,000 decision.

The distribution makes the alternative obvious:

    top   25 cities cover 80.5% of in-window zero-document projects
    top  100 cities cover 90.3%
    top  300 cities cover 96.6%

Documents are published per MEETING, not per project. One pass over a city's
planning-commission calendar captures the staff reports for every project that
city heard, at no per-project cost, and it keeps working for projects we have
not even ingested yet. Search is the fallback for the long tail; this is the
main line.

WHAT IT TARGETS. Drupal is the dominant US municipal CMS and exposes a sitemap
plus /events/<slug> pages that carry file attachments under
/sites/<site>/files/events/YYYY-MM/*.pdf. Detroit is the worked example: 9
sitemap pages, ~45,000 URLs, 3,320 /events/ URLs on page 1 alone, of which 340
were planning or zoning flavoured; sampling 6 of those found PDFs on 3, at ~3.3
PDFs each.

CAPTURE IS DELIBERATELY UNFILTERED BY PROJECT. Nothing here tries to decide
which project a PDF belongs to -- that is a separate matching step, and making
capture depend on it would throw away documents for projects we have not
ingested yet. A held document with no project attached is an asset; a document
never fetched is gone once the city rotates its site.

RATE LIMITING IS NOT OPTIONAL. A ban on a city domain is permanent loss of the
source, so requests are serialised behind a per-domain delay. This crawler is
slow on purpose.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

GCS_BUCKET = "specindex-ai-raw-documents"
USER_AGENT = "Mozilla/5.0 SpecIndex-DocumentBot/1.0 (+https://specindex.ai)"

# Slugs worth spending requests on. A city calendar is mostly police boards,
# budget hearings and community meetings; construction documents cluster in
# planning, zoning, historic-district and development bodies.
RELEVANT = re.compile(
    r"planning|zoning|commission|development|historic|design|"
    r"public-hearing|community-meeting|board-of-appeal|bseed|land-use",
    re.I,
)


def get(url: str, timeout: float = 45.0) -> tuple[int, bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, b"", ""
    except Exception:  # noqa: BLE001
        return 0, b"", ""


def sitemap_event_urls(base: str, pause: float, max_pages: int) -> list[str]:
    """Walk the Drupal sitemap index and return English /events/ URLs.

    Non-English locale prefixes (/es/, /bn/, /ar/) are dropped -- Detroit
    publishes the same event under several locales and the attachments are
    identical, so crawling them multiplies requests without adding documents.
    """
    status, body, _ = get(f"{base}/sitemap.xml")
    if status != 200:
        return []
    pages = re.findall(r"<loc>([^<]*sitemap\.xml[^<]*)</loc>", body.decode("utf-8", "ignore"))
    pages = pages[:max_pages] if pages else [f"{base}/sitemap.xml"]
    out: set[str] = set()
    for p in pages:
        time.sleep(pause)
        st, b, _ = get(p)
        if st != 200:
            continue
        for u in re.findall(r"<loc>([^<]+)</loc>", b.decode("utf-8", "ignore")):
            u = u.split('"')[0]
            if "/events/" not in u:
                continue
            path = urllib.parse.urlsplit(u).path
            if re.match(r"^/[a-z]{2}/events/", path):  # locale-prefixed duplicate
                continue
            out.add(u)
        print(f"  [sitemap] {p.rsplit('=', 1)[-1]}: {len(out):,} event URLs so far", flush=True)
    return sorted(out)


def pdf_links(page_html: bytes, base: str) -> list[str]:
    urls = set()
    for m in re.finditer(r'href="([^"]+\.pdf[^"]*)"', page_html.decode("utf-8", "ignore"), re.I):
        href = m.group(1)
        urls.add(href if href.startswith("http") else urllib.parse.urljoin(base, href))
    return sorted(urls)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="e.g. https://detroitmi.gov")
    ap.add_argument("--pause", type=float, default=1.5, help="seconds between requests")
    ap.add_argument("--max-events", type=int, default=1500)
    ap.add_argument("--max-sitemap-pages", type=int, default=9)
    ap.add_argument("--all-events", action="store_true",
                    help="crawl every event, not just planning/zoning-flavoured slugs")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sentinel", default=None)
    args = ap.parse_args()

    base = args.base.rstrip("/")
    print(f"[start] {base}", flush=True)

    events = sitemap_event_urls(base, args.pause, args.max_sitemap_pages)
    print(f"[events] {len(events):,} total", flush=True)
    if not args.all_events:
        events = [e for e in events if RELEVANT.search(e)]
        print(f"[events] {len(events):,} planning/zoning-flavoured", flush=True)
    events = events[: args.max_events]

    bucket = None
    if not args.dry_run:
        from google.cloud import storage
        bucket = storage.Client().bucket(GCS_BUCKET)
        import psycopg  # noqa: F401  (import here so --dry-run needs no DB)
        from specindex.db import connect
        conn = connect()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS municipal_documents (
                id            bigserial PRIMARY KEY,
                source_domain text NOT NULL,
                event_url     text NOT NULL,
                url           text NOT NULL UNIQUE,
                title         text,
                gcs_path      text,
                content_sha256 text,
                byte_size     bigint,
                fetched_at    timestamptz NOT NULL DEFAULT now()
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS municipal_documents_domain_idx "
                    "ON municipal_documents (source_domain)")
        conn.commit()

    domain = urllib.parse.urlsplit(base).netloc
    seen_pdf: set[str] = set()
    pages = docs = uploaded = 0
    t0 = time.time()

    for i, ev in enumerate(events, 1):
        time.sleep(args.pause)
        st, body, _ = get(ev)
        pages += 1
        if st != 200 or not body:
            continue
        for pu in pdf_links(body, base):
            if pu in seen_pdf:
                continue
            seen_pdf.add(pu)
            time.sleep(args.pause)
            pst, pbody, _ = get(pu)
            # Content check, not status check: a government host will happily
            # return 200 and an HTML landing page for a missing file.
            if pst != 200 or not pbody[:5].startswith(b"%PDF"):
                continue
            docs += 1
            title = urllib.parse.unquote(pu.rsplit("/", 1)[-1])[:500]
            if args.dry_run:
                print(f"  [would-store] {title[:80]} ({len(pbody):,}B)", flush=True)
                continue
            digest = hashlib.sha256(pbody).hexdigest()
            blob_path = f"content/{digest}.pdf"
            blob = bucket.blob(blob_path)
            if not blob.exists():
                blob.upload_from_string(pbody, content_type="application/pdf")
                uploaded += 1
            cur.execute(
                """
                INSERT INTO municipal_documents
                    (source_domain, event_url, url, title, gcs_path,
                     content_sha256, byte_size)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (url) DO UPDATE SET
                    gcs_path = EXCLUDED.gcs_path,
                    content_sha256 = EXCLUDED.content_sha256,
                    byte_size = EXCLUDED.byte_size,
                    fetched_at = now()
                """,
                (domain, ev, pu, title, blob_path, digest, len(pbody)),
            )
            conn.commit()

        if i % 25 == 0 or i == len(events):
            el = time.time() - t0
            rate = i / el if el else 0
            eta = (len(events) - i) / rate / 60 if rate else 0
            print(f"[{i}/{len(events)}] pdfs={docs} uploaded={uploaded} "
                  f"{rate*60:.1f} pages/min ETA {eta:.0f}m", flush=True)

    print(f"\n[done] {domain} events={pages} pdfs={docs} uploaded={uploaded}", flush=True)
    if args.sentinel:
        Path(args.sentinel).write_text(f"done {docs} pdfs\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
