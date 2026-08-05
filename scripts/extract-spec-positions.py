#!/usr/bin/env python3
"""Step 3 -- run spec-position extraction across the corpus and PERSIST it.

prove-the-wedge.py demonstrated the mechanism on 120 documents and wrote its
findings to a JSON file. That proved the claim and moved nothing: the
substitution ledger has 0 rows, position_score fires on 0.3% of projects, and
the row copy still says "no documents parsed yet" on records whose documents
we hold. This is the same script turned into a batch job that writes to the
database.

WHAT IT UNBLOCKS, all waiting on this one dependency:
    substitution_rulings   the moat table, currently empty
    position_score         45 of 100 points, currently inert
    the row's reason line  needs a real manufacturer or a real absence
    Phase 1.3 categories   stamped tags stay at 97.7% until extraction replaces them

RESUMABLE BY DESIGN. Documents already processed are skipped via
document_processing_status, so this can be killed and restarted without
redoing work or double-writing rulings. At corpus scale a job that cannot be
interrupted is a job that never finishes.

WRITES ARE CITED OR THEY DO NOT HAPPEN. substitution_rulings has a CHECK
constraint requiring document_file_id AND page_number > 0, so an uncited
finding is refused by the database rather than stored as an unattributable
claim about a named company.

Usage:
  python3 scripts/extract-spec-positions.py --limit 50 --dry-run
  python3 scripts/extract-spec-positions.py --limit 500
  python3 scripts/extract-spec-positions.py            # whole backlog
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from specindex import db, storage                    # noqa: E402
from specindex.progress import Progress              # noqa: E402
import document_classifier as dc                     # noqa: E402

SECTION_RE = re.compile(r"\bSECTION\s+((?:0[1-9]|[1-4]\d)\s?\d{2}\s?\d{2})\b", re.I)
BOD_HINT_RE = re.compile(
    r"basis\s+of\s+design|acceptable\s+manufacturers?|approved\s+manufacturers?"
    r"|manufacturers?\s*:|or\s+approved\s+equal|or\s+equal|substitution", re.I)

PROMPT = """You are reading one section of a construction specification or addendum.

Return STRICT JSON only (an OBJECT, not a list):
{
  "basis_of_design_manufacturer": string|null,
  "basis_of_design_product": string|null,
  "listed_alternates": [string],
  "or_equal_clause": true|false,
  "substitution_ruling": "approved"|"rejected"|"as_noted"|null,
  "displaced_manufacturer": string|null,
  "requesting_party": string|null,
  "evidence_quote": string|null,
  "csi_division": string|null
}

Rules that matter:
- basis_of_design_manufacturer is the manufacturer the schedule is BUILT AROUND.
- listed_alternates are manufacturers named as acceptable EQUALS. A different
  commercial position; never merge them with basis of design.
- substitution_ruling is set ONLY when this text rules on a substitution
  request. displaced_manufacturer is who the substitute would replace -- null
  unless actually named. Do not infer it.
- Return null rather than guessing. A cross-reference like "Section 09 06 00"
  is NOT a manufacturer. Owner, Architect, Engineer, Contractor are NOT
  manufacturers.
- evidence_quote must be copied VERBATIM and contain the manufacturer name. If
  you cannot quote it, return null for the manufacturer too.
- csi_division is the two-digit MasterFormat division of the PRODUCT, judged
  from what the product IS, not from any nearby section header -- in an
  amendment the nearest header is often unrelated. Trane air handler = 23;
  Armstrong ceiling tile = 09; Redi-Rock retaining wall = 32. Null if unsure.

SECTION TEXT:
"""

_BUCKET = None


def fetch_bytes(url: str) -> bytes:
    """Authenticated GCS read. The public-HTTPS path 404s on any object whose
    stored url is already percent-encoded (quote() is not idempotent for '%'),
    which silently failed 120 of 120 documents on the first wedge run."""
    global _BUCKET
    import urllib.request  # noqa: PLC0415

    parts = urllib.parse.urlsplit(url)
    if parts.netloc == "storage.googleapis.com":
        seg = parts.path.lstrip("/").split("/", 1)
        if len(seg) == 2:
            if _BUCKET is None:
                _BUCKET = storage.bucket(seg[0])
            return _BUCKET.blob(urllib.parse.unquote(seg[1])).download_as_bytes()
    u = urllib.parse.urlunsplit(
        parts._replace(path=urllib.parse.quote(urllib.parse.unquote(parts.path))))
    req = urllib.request.Request(u, headers={"User-Agent": "specindex-spec/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def sections_with_pages(pages: list[str]) -> list[dict]:
    hits = []
    for i, txt in enumerate(pages, start=1):
        for m in SECTION_RE.finditer(txt or ""):
            hits.append((i, re.sub(r"\s+", " ", m.group(1)).strip()))
    out = []
    for idx, (page_no, sec) in enumerate(hits):
        end = hits[idx + 1][0] if idx + 1 < len(hits) else min(page_no + 12, len(pages))
        body = "\n".join(pages[page_no - 1:end])
        if BOD_HINT_RE.search(body):
            out.append({"section": sec, "page": page_no, "text": body[:18000]})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="documents to process, 0 = all")
    ap.add_argument("--max-sections", type=int, default=8, help="per document")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    from state_agent_pipeline.config import Settings  # noqa: PLC0415
    from specindex import models                      # noqa: PLC0415
    from google import genai                          # noqa: PLC0415
    from google.genai import types                    # noqa: PLC0415
    import fitz                                       # noqa: PLC0415

    st = Settings.from_env()
    model = models.model_for_step(9, st)
    client = genai.Client(vertexai=True, project=st.google_cloud_project,
                          location=st.google_cloud_location)
    conn = db.connect()
    cur = conn.cursor()

    # Only spec-bearing classes, and only documents not already done. The
    # skip is what makes this restartable.
    #
    # ORDERED BY VALUE, NOT RECENCY. An earlier version ordered by id DESC and
    # a 15-document dry run returned zero findings -- not because extraction
    # failed, but because the most recently registered documents are Accela
    # permit output (permits, certificates, letters) and NONE of the newest 40
    # PDFs classified as spec or addenda. Sampling by recency samples whatever
    # capture happened to finish last.
    #
    # Ranking by document class first means addenda drain before spec books
    # and spec books before everything else, so a partial run still returns the
    # highest-value findings -- the same ordering the work queue uses.
    cur.execute("""
        SELECT f.id, f.project_sk, f.title, f.url
        FROM project_document_files f
        LEFT JOIN document_processing_status s ON s.document_file_id = f.id
        WHERE f.url ILIKE '%%.pdf'
          AND s.structured_extraction_at IS NULL
    """)
    scored = []
    for r in cur.fetchall():
        cls = dc.classify(r[2] or "", "", "")
        if cls in (dc.SPEC_BOOK, dc.ADDENDA):
            scored.append((dc.rank_of(cls), r))
    scored.sort(key=lambda x: x[0])
    rows = [r for _, r in scored]
    if args.limit:
        rows = rows[: args.limit]
    print(f"[spec] model={model}  documents to process: {len(rows):,}", flush=True)

    prog = Progress(len(rows), "spec-extract", every=10)
    rulings = bod = alternates = failed = 0

    for fid, sk, title, url in rows:
        prog.tick(note=f"rulings={rulings} bod={bod}")
        try:
            doc = fitz.open(stream=fetch_bytes(url), filetype="pdf")
            pages = [doc[i].get_text() or "" for i in range(len(doc))]
            doc.close()
        except Exception as e:  # noqa: BLE001 -- one bad pdf must not end the run
            failed += 1
            continue

        for s in sections_with_pages(pages)[: args.max_sections]:
            try:
                r = client.models.generate_content(
                    model=model, contents=PROMPT + s["text"],
                    config=types.GenerateContentConfig(response_mime_type="application/json"))
                raw = (r.text or "{}").strip().removeprefix("```json").removesuffix("```")
                data = json.loads(raw)
                # Gemini sometimes answers with a LIST of section objects. One
                # such response crashed an entire 120-document run before this.
                if isinstance(data, list):
                    data = next((d for d in data if isinstance(d, dict)
                                 and d.get("basis_of_design_manufacturer")),
                                data[0] if data and isinstance(data[0], dict) else {})
                if not isinstance(data, dict):
                    continue
            except Exception:  # noqa: BLE001
                continue

            quote = (data.get("evidence_quote") or "").strip()
            mfr = (data.get("basis_of_design_manufacturer") or "").strip()
            div = (data.get("csi_division") or "").strip()[:2] or None
            # No quote, no row. An uncited claim about a named company is the
            # thing competitors already sell.
            if not quote:
                continue

            def write(manufacturer: str, ruling: str | None, displaced: str | None):
                cur.execute("""
                    INSERT INTO substitution_rulings
                      (project_sk, requesting_party, proposed_manufacturer,
                       proposed_product, displaced_manufacturer, ruling, ruling_date,
                       csi_section, csi_division, document_file_id, page_number,
                       source_url, quoted_text, confidence)
                    VALUES (%s,%s,%s,%s,%s,%s,NULL,%s,%s,%s,%s,%s,%s,'reported')
                    ON CONFLICT (project_sk, proposed_manufacturer, csi_section,
                                 document_file_id) DO NOTHING
                """, (sk, data.get("requesting_party"), manufacturer,
                      data.get("basis_of_design_product"), displaced,
                      ruling or "pending", s["section"], div, fid, s["page"],
                      url, quote[:1000]))

            if args.dry_run:
                if mfr:
                    bod += 1
                continue
            if mfr:
                write(mfr, data.get("substitution_ruling"),
                      data.get("displaced_manufacturer"))
                bod += 1
                rulings += cur.rowcount
            for alt in (data.get("listed_alternates") or [])[:6]:
                if alt and alt.strip():
                    write(alt.strip(), None, None)
                    alternates += 1
                    rulings += cur.rowcount

        if not args.dry_run:
            cur.execute("""
                INSERT INTO document_processing_status (document_file_id, structured_extraction_at)
                VALUES (%s, now())
                ON CONFLICT (document_file_id) DO UPDATE SET structured_extraction_at = now()
            """, (fid,))
            conn.commit()

    prog.done()
    print(f"\n=== SPEC POSITION EXTRACTION ===")
    print(f"  documents processed : {len(rows) - failed:,}")
    print(f"  fetch/parse failed  : {failed:,}")
    print(f"  basis-of-design     : {bod:,}")
    print(f"  listed alternates   : {alternates:,}")
    print(f"  ledger rows written : {rulings:,}")
    if args.dry_run:
        print("  DRY RUN -- nothing written")
        return 0
    cur.execute("SELECT count(*) FROM substitution_rulings")
    print(f"  substitution_rulings total: {cur.fetchone()[0]:,}")
    print("SPEC EXTRACTION COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
