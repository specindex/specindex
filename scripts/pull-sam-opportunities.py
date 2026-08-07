#!/usr/bin/env python3
"""A4 -- SAM.gov Get Opportunities v2. Federal construction spec books.

Verified live 2026-08-07: NAICS 236220 (commercial building construction)
returns ~357 solicitations in a 30-day window, and resourceLinks download to
real project manuals -- one sampled attachment was 4.8MB with PART 1/2/3 and
DIVISION headings.

TWO THINGS THE PROBE FOUND, both handled here:

  Attachment yield is uneven. The first opportunity had 13 resource links, the
  second had ZERO. "No documents posted" is a logged outcome, not a failure.

  Most attachments are not spec books. Of three sampled from one solicitation,
  two were small PDFs with no CSI structure -- wage determinations and notices.
  So every download is content-checked before it is stored, exactly as the
  portal adapters do.

resourceLinks come back WITHOUT the api key and need it appended per URL.
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, io, json, os, re, sys, time
import urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from specindex.db import connect  # noqa: E402

API = "https://api.sam.gov/opportunities/v2/search"
GCS_BUCKET = "specindex-ai-raw-documents"
UA = "SpecIndex-DocumentBot/1.0 (+https://specindex.ai)"
CSI_PARTS = re.compile(r"PART\s+[123]\s*[-–—]?\s*(GENERAL|PRODUCTS|EXECUTION)", re.I)
CSI_DIV = re.compile(r"\bDIVISION\s+\d{1,2}\b", re.I)


def get(url: str, timeout: float = 90) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception:  # noqa: BLE001
        return b""


def is_spec(body: bytes) -> bool:
    if not body[:5].startswith(b"%PDF"):
        return False
    try:
        from pypdf import PdfReader
        t = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(body)).pages[:60])
    except Exception:  # noqa: BLE001
        return False
    return bool(CSI_PARTS.search(t) or CSI_DIV.search(t))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--naics", default="236220")
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--pause", type=float, default=1.0)
    args = ap.parse_args()

    key = os.environ["SAM_API_KEY"]
    to = dt.date.today(); frm = to - dt.timedelta(days=args.days)
    from google.cloud import storage
    bucket = storage.Client().bucket(GCS_BUCKET)
    conn = connect(); cur = conn.cursor()

    q = urllib.parse.urlencode({"limit": args.limit, "postedFrom": frm.strftime("%m/%d/%Y"),
                                "postedTo": to.strftime("%m/%d/%Y"), "ptype": "o",
                                "ncode": args.naics, "api_key": key})
    data = json.loads(get(f"{API}?{q}") or b"{}")
    opps = data.get("opportunitiesData") or []
    print(f"[scope] {data.get('totalRecords', 0)} solicitations, pulling {len(opps)}", flush=True)

    stored = specs = nodocs = 0
    for i, o in enumerate(opps, 1):
        links = o.get("resourceLinks") or []
        if not links:
            nodocs += 1
            continue
        title = (o.get("title") or "")[:300]
        state = (o.get("placeOfPerformance") or {}).get("state", {}).get("code") or "US"
        nid = o.get("noticeId") or ""
        for l in links[:8]:
            u = l if "api_key" in l else l + ("&" if "?" in l else "?") + "api_key=" + key
            body = get(u)
            time.sleep(args.pause)
            if not is_spec(body):
                continue
            specs += 1
            digest = hashlib.sha256(body).hexdigest()
            path = f"specs/{state}/{nid[:24]}/specbook_{digest[:12]}.pdf"
            blob = bucket.blob(path)
            if not blob.exists():
                blob.metadata = {"source_url": l, "portal": "sam.gov", "doc_type": "specbook",
                                 "fetch_date": dt.date.today().isoformat(), "portal_state": state}
                blob.upload_from_string(body, content_type="application/pdf")
            cur.execute("""INSERT INTO reference_documents
                    (scope, scope_value, doc_kind, title, url, gcs_path, content_sha256,
                     byte_size, text_extracted, doc_type, spec_format)
                    VALUES ('state',%s,'sam_solicitation',%s,%s,%s,%s,%s,false,'specbook','CSI')
                    ON CONFLICT (url) DO NOTHING""",
                (state, title, l, path, digest, len(body)))
            stored += 1
            conn.commit()
            break
        if i % 20 == 0:
            print(f"  [{i}/{len(opps)}] spec docs={specs} no-docs={nodocs}", flush=True)
    print(f"\n[done] solicitations={len(opps)} with_spec_doc={specs} no_documents_posted={nodocs}")
    cur.execute("select count(*) from reference_documents where doc_kind='sam_solicitation'")
    print(f"[verify] SAM spec books readable downstream: {cur.fetchone()[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
