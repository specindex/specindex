#!/usr/bin/env python3
"""Register A3's captured spec books into Postgres and extract their text.

THE SEAM THIS CLOSES -- THE THIRD OF ITS KIND TODAY. run-portal-capture.py
writes documents to GCS and a CSV pull log. Neither is a database. So 145 spec
books, 1.26 GB, sat captured and invisible to the classifier, which reads
document_pages. Exactly the shape that left 78% of documents invisible
downstream, that kept project_csi_divisions empty behind a status flag, and that
had A1/A2/A5 writing JSON nothing loaded.

The rule earned three times over: after any pipeline step, assert the NEXT step
can see its output.

WHY reference_documents. These are state bid-portal spec books. They are not
tied to a project in our corpus -- a Missouri project manual describes a job we
have no permit row for -- so project_document_files, which requires a
project_sk, is the wrong home. reference_documents is scoped to a jurisdiction,
which is what these are.
"""
from __future__ import annotations
import argparse, csv, io, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from specindex.db import connect  # noqa: E402

GCS_BUCKET = "specindex-ai-raw-documents"


def page_texts(body: bytes) -> list[str]:
    """Extract page text, stripped of NUL bytes.

    PDF text extraction emits 0x00 from some encodings, and PostgreSQL text
    cannot hold a NUL -- psycopg raises before the insert, which aborted the run
    at document 13 of 177. Stripping is safe: a NUL carries no meaning in
    extracted prose, and losing the whole document to keep one is the worse
    trade.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader
    out = []
    for pg in PdfReader(io.BytesIO(body)).pages:
        txt = pg.extract_text() or ""
        out.append(txt.replace("\x00", ""))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=None, help="pull-log CSV; default newest")
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--max-pages", type=int, default=1200,
                    help="skip absurd books; a 5,000-page drawing set is not worth the extract")
    args = ap.parse_args()

    logdir = ROOT / "coverage" / "pull-log"
    logpath = Path(args.log) if args.log else max(logdir.glob("pull-*.csv"), key=lambda p: p.stat().st_mtime)
    rows = [r for r in csv.DictReader(open(logpath))
            if r.get("gcs_path") and r.get("spec_format") in ("CSI", "DOT SS/SP")]
    print(f"[scope] {logpath.name}: {len(rows)} confirmed spec documents", flush=True)

    from google.cloud import storage
    bucket = storage.Client().bucket(GCS_BUCKET)
    # Cloud SQL has dropped four long jobs today. Reconnect rather than lose
    # the run's progress.
    def db():
        for a in range(6):
            try:
                c = connect(); c.cursor().execute("SELECT 1"); return c
            except Exception:  # noqa: BLE001
                if a == 5:
                    raise
                time.sleep(5 * (a + 1))
        raise RuntimeError("unreachable")

    conn = db(); cur = conn.cursor()

    registered = extracted = pages_total = skipped = 0
    for i, r in enumerate(rows[: args.limit], 1):
        gcs = r["gcs_path"].replace(f"gs://{GCS_BUCKET}/", "")
        url = r["document_url"]
        cur.execute("SELECT id, text_extracted FROM reference_documents WHERE url = %s", (url,))
        got = cur.fetchone()
        if got and got[1]:
            skipped += 1
            continue

        # PATH REPAIR FOR MIGRATED OBJECTS. Multi-state adapters originally
        # wrote specs/UTAH, WASHINGTON/... and those objects were later moved to
        # specs/MULTI/. The pull log still records the pre-migration path, so a
        # straight read 404s -- and "GCS read failed NotFound" reads exactly like
        # a document that was never captured.
        candidates = [gcs]
        if "," in gcs or " " in gcs:
            parts = gcs.split("/")
            if len(parts) > 2:
                candidates.append("/".join([parts[0], "MULTI"] + parts[2:]))
        body = None
        for cand in candidates:
            try:
                body = bucket.blob(cand).download_as_bytes()
                gcs = cand
                break
            except Exception:  # noqa: BLE001
                continue
        if body is None:
            print(f"  [{i}] GCS object missing: {gcs[:70]}", flush=True)
            continue

        try:
            texts = page_texts(body)
        except Exception:  # noqa: BLE001
            texts = []
        if len(texts) > args.max_pages:
            print(f"  [{i}] {r['state']}: {len(texts)} pages, over cap -- registered without text",
                  flush=True)
            texts = []

        cur.execute(
            """
            INSERT INTO reference_documents
                (scope, scope_value, doc_kind, title, url, gcs_path,
                 page_count, byte_size, text_extracted, doc_type, spec_format)
            VALUES ('state', %s, 'portal_spec_book', %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (url) DO UPDATE SET
                gcs_path = EXCLUDED.gcs_path, page_count = EXCLUDED.page_count,
                byte_size = EXCLUDED.byte_size, text_extracted = EXCLUDED.text_extracted,
                doc_type = EXCLUDED.doc_type, spec_format = EXCLUDED.spec_format,
                fetched_at = now()
            RETURNING id
            """,
            ((r.get("state") or "")[:24], (r.get("project_name") or r.get("file_name") or "")[:500],
             url, gcs, len(texts) or None, r.get("file_size") or None,
             bool(texts), "specbook", r.get("spec_format")),
        )
        doc_id = cur.fetchone()[0]
        registered += 1

        if texts:
            cur.execute("DELETE FROM document_pages WHERE reference_document_id = %s", (doc_id,))
            kept = 0
            for n, t in enumerate(texts, 1):
                if not t.strip():
                    continue
                cur.execute(
                    """INSERT INTO document_pages
                       (reference_document_id, page_number, raw_text, ocr_engine)
                       VALUES (%s,%s,%s,'native')""", (doc_id, n, t))
                kept += 1
            extracted += 1
            pages_total += kept
        try:
            conn.commit()
        except Exception:  # noqa: BLE001
            print(f"  [{i}] connection lost -- reconnecting", flush=True)
            conn = db(); cur = conn.cursor()
        if i % 10 == 0:
            print(f"  [{i}/{min(len(rows), args.limit)}] registered={registered} "
                  f"pages={pages_total:,}", flush=True)

    # Assert the NEXT step can see this.
    cur.execute("SELECT count(*) FROM reference_documents WHERE doc_kind='portal_spec_book'")
    docs = cur.fetchone()[0]
    cur.execute("""SELECT count(*) FROM document_pages p
                    JOIN reference_documents r ON r.id = p.reference_document_id
                   WHERE r.doc_kind='portal_spec_book'""")
    pages = cur.fetchone()[0]
    print(f"\n[done] registered={registered} extracted={extracted} pages={pages_total:,} skipped={skipped}")
    print(f"[verify] classifier can see {docs} portal spec books, {pages:,} pages")
    if registered and not pages:
        print("STOP: registered documents but no page is readable", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
