#!/usr/bin/env python3
"""Extract page text from captured legislative documents.

An unextracted PDF cannot be searched, cited or quoted -- it is bytes in a
bucket. document_pages takes either a project document or a reference document
since migration 052; this adds the third owner so Legistar attachments land in
the SAME page store that FTS and pgvector already index, rather than a second
place nothing reads from.
"""
from __future__ import annotations
import io, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from specindex.db import connect  # noqa: E402

def page_texts(body: bytes) -> list[str]:
    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader
    return [(p.extract_text() or "") for p in PdfReader(io.BytesIO(body)).pages]

def main() -> int:
    from google.cloud import storage
    bucket = storage.Client().bucket("specindex-ai-raw-documents")
    conn = connect(); cur = conn.cursor()
    cur.execute("""ALTER TABLE document_pages
                   ADD COLUMN IF NOT EXISTS legislative_document_id bigint
                   REFERENCES legislative_documents(id)""")
    cur.execute("""CREATE INDEX IF NOT EXISTS document_pages_legislative_idx
                   ON document_pages (legislative_document_id)
                   WHERE legislative_document_id IS NOT NULL""")
    # The one-owner CHECK from 052 predates this third owner and would reject
    # every row inserted here. Replaced rather than dropped: the invariant that
    # matters is still "exactly one owner", it just has three candidates now.
    cur.execute("ALTER TABLE document_pages DROP CONSTRAINT IF EXISTS document_pages_one_owner")
    cur.execute("""ALTER TABLE document_pages ADD CONSTRAINT document_pages_one_owner CHECK (
        (document_file_id IS NOT NULL)::int
      + (reference_document_id IS NOT NULL)::int
      + (legislative_document_id IS NOT NULL)::int = 1) NOT VALID""")
    conn.commit()

    cur.execute("""SELECT d.id, d.gcs_path, d.attachment_name
                   FROM legislative_documents d
                   WHERE NOT EXISTS (SELECT 1 FROM document_pages p
                                     WHERE p.legislative_document_id = d.id)
                   ORDER BY d.id""")
    rows = cur.fetchall()
    print(f"[scope] {len(rows)} documents needing extraction", flush=True)
    done = pages = 0; t0 = time.time()
    for i, (did, path, name) in enumerate(rows, 1):
        try:
            body = bucket.blob(path).download_as_bytes()
            texts = page_texts(body)
        except Exception as e:  # noqa: BLE001
            print(f"  [fail] {did} {type(e).__name__}", flush=True); continue
        kept = 0
        for n, t in enumerate(texts, 1):
            if not t.strip():
                continue
            cur.execute("""INSERT INTO document_pages
                           (legislative_document_id, page_number, raw_text, ocr_engine)
                           VALUES (%s,%s,%s,'native')""", (did, n, t))
            kept += 1
        conn.commit(); done += 1; pages += kept
        if i % 10 == 0 or i == len(rows):
            el = time.time()-t0; r = i/el if el else 0
            print(f"[{i}/{len(rows)}] docs={done} pages={pages:,} "
                  f"{r*60:.1f}/min ETA {(len(rows)-i)/r/60 if r else 0:.0f}m", flush=True)
    cur.execute("SELECT count(*) FROM document_pages WHERE legislative_document_id IS NOT NULL")
    print(f"\n[done] extracted={done} pages={pages:,}; readable downstream: {cur.fetchone()[0]:,}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
