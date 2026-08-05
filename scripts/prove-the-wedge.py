#!/usr/bin/env python3
"""Produce the deliverable: project -> manufacturer -> spec position -> page.

THIS IS THE UNVALIDATED CLAIM. The company thesis is "we can tell you whether
you are basis of design, a listed alternate, or absent, with a page-level
citation." The corpus holds ~387 spec books and ~594 addenda, and
extract-spec-book.py has been run against exactly ONE document -- a VA
performance spec. Everything else built so far is infrastructure that produces
no sellable fact.

So this runs the whole chain on real documents and emits a table that is
either convincing or is not:

    project | manufacturer | basis_of_design / listed_alternate | doc | page

Twenty verified rows is the deliverable. A row without a page citation is not
a row -- it is the thing competitors already sell.

DESIGN NOTES
  * Documents are ranked with document_classifier, addenda and spec books
    first, because those are where basis-of-design lives.
  * Text extraction is native-only (PyMuPDF). 98.4% of pages measured carry a
    text layer, so OCR is not on the critical path for a 20-project proof and
    would only add cost and latency.
  * Gemini Pro (step 9 routing), not Flash: nothing downstream re-checks this
    output, so a wrong manufacturer name would ship unnoticed.
  * Every emitted row carries document + page. Rows without one are counted
    and reported separately rather than quietly dropped -- knowing how often
    extraction finds a manufacturer but cannot cite it is itself a finding.

Usage:
  python3 scripts/prove-the-wedge.py --limit 20 --out data/raw/wedge_proof.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from specindex import db, storage                     # noqa: E402
import document_classifier as dc                       # noqa: E402

# Section headers across ALL MasterFormat divisions.
#
# This deliberately no longer filters to 21-28. Restricting the HEADER pattern
# to MEP divisions did not restrict the FINDINGS to MEP -- it only meant a
# section could be examined solely when it happened to sit beneath an MEP
# header. That is how an Armstrong acoustic ceiling tile (Division 09) and a
# Redi-Rock retaining wall (Division 32) were discovered under fire-alarm and
# communications headers, and then tagged with them. The narrow pattern was
# the root cause of the mis-attribution, not just a symptom.
#
# Divisions 01-49 now match, the model classifies each finding from what the
# PRODUCT is, and the header is kept only as provenance.
SECTION_RE = re.compile(r"\bSECTION\s+((?:0[1-9]|[1-4]\d)\s?\d{2}\s?\d{2})\b", re.I)
BOD_HINT_RE = re.compile(
    r"basis\s+of\s+design|acceptable\s+manufacturers?|approved\s+manufacturers?"
    r"|manufacturers?\s*:|or\s+approved\s+equal|or\s+equal", re.I)

PROMPT = """You are reading one section of a construction specification.

Return STRICT JSON only:
{
  "basis_of_design_manufacturer": string|null,
  "basis_of_design_product": string|null,
  "listed_alternates": [string],
  "or_equal_clause": true|false,
  "evidence_quote": string|null,
  "csi_division": string|null
}

Rules that matter:
- basis_of_design_manufacturer is the manufacturer the schedule is BUILT
  AROUND -- typically named right after "Basis of Design" or as the first
  named manufacturer with a model number.
- listed_alternates are manufacturers named as acceptable EQUALS. They are a
  different commercial position and must not be merged with basis of design.
- Return null rather than guessing. A cross-reference like "Section 09 06 00"
  is NOT a manufacturer. Generic words (Owner, Architect, Engineer,
  Contractor) are NOT manufacturers.
- evidence_quote must be text copied VERBATIM from the section, short, and
  containing the manufacturer name. If you cannot quote it, return null for
  the manufacturer too.
- csi_division is the two-digit MasterFormat division the PRODUCT belongs to,
  judged from what the product IS -- not from any section header nearby. In an
  amendment the nearest header is frequently unrelated to the text under it.
  Examples: a Trane air handler is 23 (HVAC); an Armstrong acoustic ceiling
  tile is 09 (Finishes); a Redi-Rock MSE retaining wall is 32 (Exterior
  Improvements); a switchboard is 26 (Electrical). Return null if unsure --
  a wrong division puts a manufacturer in a trade they do not sell into.

SECTION TEXT:
"""


_BUCKET = None


def fetch_bytes(url: str) -> bytes:
    """Read via the AUTHENTICATED GCS client, falling back to public HTTPS.

    The first run of this script fetched every document over public HTTPS and
    got HTTPError on all 120, so extraction never ran and the result read as
    "the wedge found nothing" -- a false zero of exactly the kind this repo
    keeps producing.

    Reading the blob directly is the right call regardless of that failure:
    it does not depend on the object being publicly readable, it carries the
    service-account credential (user ADC expires, and its failure also reads
    as "no documents"), and it measured 125 KB/s against 66 KB/s for the
    public path -- 1.9x on the same objects.

    The public path is kept only as a fallback for rows whose url points
    somewhere other than our bucket.
    """
    global _BUCKET
    parts = urllib.parse.urlsplit(url)
    if parts.netloc == "storage.googleapis.com":
        # /{bucket}/{object...} -> object path, unquoted for the API.
        segments = parts.path.lstrip("/").split("/", 1)
        if len(segments) == 2:
            if _BUCKET is None:
                _BUCKET = storage.bucket(segments[0])
            blob_name = urllib.parse.unquote(segments[1])
            try:
                return _BUCKET.blob(blob_name).download_as_bytes()
            except Exception as e:  # noqa: BLE001 -- fall through, but say why
                print(f"      gcs read failed ({type(e).__name__}), trying https",
                      flush=True)
    u = urllib.parse.urlunsplit(parts._replace(path=urllib.parse.quote(parts.path)))
    req = urllib.request.Request(u, headers={"User-Agent": "specindex-wedge/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def pages_of(pdf_bytes: bytes) -> list[str]:
    import fitz  # noqa: PLC0415

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return [doc[i].get_text() or "" for i in range(len(doc))]
    finally:
        doc.close()


def sections_with_pages(pages: list[str]) -> list[dict]:
    """Slice into MasterFormat sections, carrying the PAGE NUMBER through.

    The page is the product. Extracting a manufacturer without knowing which
    page it came from produces exactly the uncitable claim we are trying to
    beat.
    """
    hits = []
    for i, txt in enumerate(pages, start=1):
        for m in SECTION_RE.finditer(txt or ""):
            hits.append((i, re.sub(r"\s+", " ", m.group(1)).strip()))
    out = []
    for idx, (page_no, sec) in enumerate(hits):
        end_page = hits[idx + 1][0] if idx + 1 < len(hits) else min(page_no + 12, len(pages))
        body = "\n".join(pages[page_no - 1:end_page])
        if BOD_HINT_RE.search(body):
            out.append({"section": sec, "page": page_no, "text": body[:18000]})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20, help="projects to prove")
    ap.add_argument("--max-docs", type=int, default=120)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    from state_agent_pipeline.config import Settings  # noqa: PLC0415
    from specindex import models                      # noqa: PLC0415
    from google import genai                          # noqa: PLC0415
    from google.genai import types                    # noqa: PLC0415

    st = Settings.from_env()
    model = models.model_for_step(9, st)
    client = genai.Client(vertexai=True, project=st.google_cloud_project,
                          location=st.google_cloud_location)
    print(f"[wedge] model={model}", flush=True)

    conn = db.connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT f.id, f.title, f.url, p.project_id, p.name
        FROM project_document_files f
        JOIN projects p ON p.project_sk = f.project_sk
        WHERE f.url ILIKE '%%.pdf'
        ORDER BY f.id DESC
        LIMIT 4000
    """)
    rows = cur.fetchall()
    ranked = []
    for fid, title, url, pid, pname in rows:
        cls = dc.classify(title or "", "", "")
        if cls in (dc.SPEC_BOOK, dc.ADDENDA):
            ranked.append((dc.rank_of(cls), fid, title, url, pid, pname, cls))
    ranked.sort(key=lambda r: r[0])
    print(f"[wedge] {len(ranked)} spec-book/addenda PDFs available", flush=True)

    findings, seen_projects, docs_tried = [], set(), 0
    no_citation = 0
    # Counted and REPORTED. The first run returned zero findings purely
    # because every fetch failed, and without this counter the output was
    # indistinguishable from "extraction found nothing" -- the difference
    # between a bug and a result.
    fetch_failures = 0
    no_sections = 0

    for rank, fid, title, url, pid, pname, cls in ranked:
        if len(seen_projects) >= args.limit or docs_tried >= args.max_docs:
            break
        docs_tried += 1
        try:
            pdf = fetch_bytes(url)
            pages = pages_of(pdf)
        except Exception as e:  # noqa: BLE001 -- one bad pdf must not end the run
            fetch_failures += 1
            print(f"  skip {title[:50]}: {type(e).__name__}", flush=True)
            continue
        secs = sections_with_pages(pages)
        if not secs:
            no_sections += 1
            continue
        print(f"  [{cls}] {title[:56]} -- {len(pages)}p, {len(secs)} candidate sections",
              flush=True)
        for s in secs[:6]:
            try:
                r = client.models.generate_content(
                    model=model, contents=PROMPT + s["text"],
                    config=types.GenerateContentConfig(response_mime_type="application/json"))
                data = json.loads((r.text or "{}").strip().removeprefix("```json").removesuffix("```"))
            except Exception as e:  # noqa: BLE001
                print(f"      model error: {type(e).__name__}", flush=True)
                continue
            bod = (data.get("basis_of_design_manufacturer") or "").strip()
            quote = (data.get("evidence_quote") or "").strip()
            alts = [a for a in (data.get("listed_alternates") or []) if a and a.strip()]
            if not bod and not alts:
                continue
            # A claim we cannot cite is the thing competitors already sell.
            if bod and not quote:
                no_citation += 1
                continue
            div = (data.get("csi_division") or "").strip()[:2]
            if bod:
                findings.append({
                    "project_id": pid, "project_name": pname,
                    "manufacturer": bod, "product": data.get("basis_of_design_product"),
                    "position": "basis_of_design",
                    # Derived from what the product IS. The nearby header is
                    # kept separately because in an amendment it is often
                    # unrelated -- Trane HVAC sat under a fire-detection
                    # header in the first run and was tagged 28 31 76.
                    "csi_division": div or None,
                    "nearby_section_header": s["section"],
                    "document": title, "document_url": url, "page": s["page"],
                    "or_equal": bool(data.get("or_equal_clause")),
                    "evidence": quote[:300], "doc_class": cls,
                })
                seen_projects.add(pid)
                print(f"      BOD {bod!r} -- Div {div or '??'} "
                      f"(header said {s['section']}) p.{s['page']}", flush=True)
            for a in alts[:6]:
                findings.append({
                    "project_id": pid, "project_name": pname,
                    "manufacturer": a.strip(), "product": None,
                    "position": "listed_alternate",
                    "csi_division": div or None,
                    "nearby_section_header": s["section"],
                    "document": title, "document_url": url, "page": s["page"],
                    "or_equal": bool(data.get("or_equal_clause")),
                    "evidence": quote[:300], "doc_class": cls,
                })
                seen_projects.add(pid)
            time.sleep(0.4)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(
        {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": model,
         "docs_tried": docs_tried, "projects": len(seen_projects),
         "fetch_failures": fetch_failures, "no_sections": no_sections,
         "dropped_uncitable": no_citation,
         "unique_findings": len(unique_keys),
         "findings": findings}, indent=2))

    # A finding is (manufacturer, document, page). SAM.gov serves the same
    # attachment under multiple notice ids -- one amendment appeared under five
    # project_ids -- so counting rows overstated the result 2x in the first
    # run. Report BOTH numbers: rows is what the ledger stores, unique is what
    # is true.
    unique_keys = {(f["manufacturer"].lower(), f["document"], f["page"])
                   for f in findings}
    bod_n = sum(1 for f in findings if f["position"] == "basis_of_design")
    unique_bod = len({(f["manufacturer"].lower(), f["document"], f["page"])
                      for f in findings if f["position"] == "basis_of_design"})
    reached = docs_tried - fetch_failures
    print(f"\n=== WEDGE PROOF ===")
    print(f"  documents tried      : {docs_tried}")
    print(f"  fetch FAILED         : {fetch_failures}   <- infrastructure, not a result")
    print(f"  documents parsed     : {reached}")
    print(f"  no MEP sections found: {no_sections}")
    print(f"  projects with a fact : {len(seen_projects)}")
    print(f"  basis-of-design rows : {bod_n}")
    print(f"  UNIQUE bod findings  : {unique_bod}   <- rows minus duplicate notice ids")
    print(f"  listed-alternate rows: {len(findings) - bod_n}")
    print(f"  dropped, uncitable   : {no_citation}")
    # A zero that comes from failed fetches says nothing about extraction, and
    # must never be reported as though it did.
    if reached == 0:
        print("\n  VERDICT: INCONCLUSIVE -- zero documents were successfully read.\n"
              "  This says NOTHING about whether extraction works. Fix fetching first.")
    elif not findings:
        print(f"\n  VERDICT: extraction ran on {reached} documents and found nothing.\n"
              "  That IS a real negative and worth investigating.")
    shown = set()
    for f in findings:
        k = (f["manufacturer"].lower(), f["document"], f["page"])
        if k in shown:
            continue
        shown.add(k)
        print(f"   {f['position']:<18} {f['manufacturer'][:24]:<24} "
              f"Div {str(f.get('csi_division') or '??'):<4} p.{f['page']:<4} "
              f"{f['document'][:44]}")
    print(f"\n  -> {args.out}")
    print("WEDGE PROOF COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
