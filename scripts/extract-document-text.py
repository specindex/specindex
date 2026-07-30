#!/usr/bin/env python3
"""Pipeline step 9: per-page text extraction for documents already pulled by
step 7 (docs/AGENT_STRATEGY.md already spoke for step 8 as project
enrichment, added 2026-07-29 -- text extraction slots in right after it).

Native text first (PyMuPDF, free, instant) -- most spec/RFP PDFs already
carry a real text layer. Only pages with no meaningful native text (drawing
sheets, scans) get rendered to an image and sent to Google Document AI.
Settled over a self-hosted PaddleOCR pipeline after a live head-to-head test
on a real VA drawing cover sheet (2026-07-29): comparable accuracy, but
Document AI read one dense small-print citation PaddleOCR garbled, and at
the corpus's real page volume it beats operating a CPU OCR worker pool.

Both project_document_files storage patterns are handled: rows with a
`url` (this session's public-bucket-direct-URL pattern) and rows with a
`gcs_path` (the other session's content-addressed pattern, same now-public
bucket, gs://specindex-ai-raw-documents/{gcs_path}) -- fetched the same way
since the whole bucket is public.

Usage:
    python3 scripts/extract-document-text.py --document-file-id 12345
    python3 scripts/extract-document-text.py --batch --limit 20 --state GA --document-type specifications,drawings_plans
    python3 scripts/extract-document-text.py --batch --limit 5 --dry-run
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

GCS_BUCKET = "specindex-ai-raw-documents"
NATIVE_MIN_CHARS = 20  # below this, treat the page as image-only and OCR it
DOCUMENT_AI_LOCATION = "us"

USER_AGENT = "SpecIndexDocumentBot/1.0 (+https://specindex.ai; research/archival)"


def _doc_ai_processor_name() -> str:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT_NUMBER") or os.environ.get("GOOGLE_CLOUD_PROJECT", "specindex-ai")
    processor_id = os.environ.get("DOCUMENT_AI_PROCESSOR_ID")
    if not processor_id:
        raise SystemExit(
            "DOCUMENT_AI_PROCESSOR_ID not set -- see the OCR_PROCESSOR created "
            "2026-07-29 (specindex-ocr-comparison-test, us region) or create a new one."
        )
    return f"projects/{project}/locations/{DOCUMENT_AI_LOCATION}/processors/{processor_id}"


def fetch_document_bytes(row: dict[str, Any]) -> bytes:
    if row.get("gcs_path"):
        url = f"https://storage.googleapis.com/{GCS_BUCKET}/{row['gcs_path']}"
    else:
        url = row["url"]
    # Real bug found 2026-07-29 running this against GA at scale: many
    # stored `url` values have literal unescaped spaces (GCS blob names
    # built straight from real filenames, e.g. "S02 - RFP Attachment
    # 3.pdf", by compute-project-documents.py's files_from_gcs() -- see
    # its fix in the same commit). urllib.request rejects those outright
    # ("URL can't contain control characters"). Quote just the path
    # component so this is safe on both already-good and already-bad
    # stored URLs -- quote() is idempotent on characters that don't need
    # escaping, so a clean URL passes through unchanged.
    parts = urllib.parse.urlsplit(url)
    url = urllib.parse.urlunsplit(parts._replace(path=urllib.parse.quote(parts.path)))
    # Real bug found 2026-07-30: batch of 100/100 uniform 404s, but the
    # exact same URL curled directly returned 200 immediately after.
    # step7-gemini-document-backfill.py (still running unattended in the
    # background) uploads new files to this same bucket concurrently --
    # if step9 requests a file within moments of it landing, GCS's edge
    # (Cache-Control: public, max-age=3600, confirmed live on a real
    # object's response headers) can cache the pre-upload "not found yet"
    # response for up to an hour, so every retry from the same edge kept
    # getting a stale 404 for an object that genuinely existed by then.
    # Cache-Control: no-cache forces revalidation against origin instead
    # of serving a cached miss; the bounded retry-on-404 below is a
    # defensive second line in case a request still lands mid-upload.
    for attempt in range(2):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Cache-Control": "no-cache"})
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 404 and attempt == 0:
                time.sleep(3)
                continue
            raise


def native_page_text(page) -> str:
    return page.get_text("text").strip()


def document_ai_ocr_page(client, processor_name: str, page_pdf_bytes: bytes) -> tuple[str, float]:
    from google.cloud import documentai_v1 as documentai

    raw_document = documentai.RawDocument(content=page_pdf_bytes, mime_type="application/pdf")
    request = documentai.ProcessRequest(name=processor_name, raw_document=raw_document)
    result = client.process_document(request=request)
    doc = result.document
    text = doc.text
    confs = [
        token.layout.confidence
        for page in doc.pages
        for token in page.tokens
        if token.layout and token.layout.confidence is not None
    ]
    avg_conf = sum(confs) / len(confs) if confs else None
    return text, avg_conf


def extract_document(fitz_module, client, processor_name: str, pdf_bytes: bytes) -> list[dict[str, Any]]:
    """Returns a list of {page_number, raw_text, ocr_engine, avg_confidence}."""
    doc = fitz_module.open(stream=pdf_bytes, filetype="pdf")
    pages_out: list[dict[str, Any]] = []
    for i, page in enumerate(doc):
        page_number = i + 1
        native_text = native_page_text(page)
        if len(native_text) >= NATIVE_MIN_CHARS:
            pages_out.append(
                {"page_number": page_number, "raw_text": native_text, "ocr_engine": "native", "avg_confidence": None}
            )
            continue

        # Render this single page to its own one-page PDF and send that to
        # Document AI -- keeps every call well under any per-request page
        # cap regardless of how large the source document is.
        single_page_doc = fitz_module.open()
        single_page_doc.insert_pdf(doc, from_page=i, to_page=i)
        page_pdf_bytes = single_page_doc.tobytes()
        single_page_doc.close()

        text, avg_conf = document_ai_ocr_page(client, processor_name, page_pdf_bytes)
        pages_out.append(
            {"page_number": page_number, "raw_text": text, "ocr_engine": "document_ai", "avg_confidence": avg_conf}
        )
    doc.close()
    return pages_out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--document-file-id", type=int, help="process one project_document_files.id")
    ap.add_argument("--batch", action="store_true", help="process not-yet-extracted documents instead of one id")
    ap.add_argument("--limit", type=int, default=20, help="--batch only: max documents this run")
    ap.add_argument("--state", help="--batch only: restrict to one state code, e.g. GA")
    ap.add_argument("--document-type", help="--batch only: comma-separated document_type values, e.g. specifications,drawings_plans")
    ap.add_argument("--delay", type=float, default=0.5, help="--batch only: seconds between documents")
    ap.add_argument(
        "--retry-errors",
        action="store_true",
        help="--batch only: include documents that previously failed (normally excluded, to avoid "
        "re-billing Document AI on a permanently-broken document every run) -- use after fixing a "
        "bug that caused a batch of transient failures",
    )
    ap.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", "postgresql://specindex:specindex@localhost:5432/specindex"),
    )
    ap.add_argument("--apply-migration", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="print what would be extracted, don't touch the DB")
    args = ap.parse_args()

    if not args.document_file_id and not args.batch:
        ap.error("pass --document-file-id or --batch")

    import fitz  # PyMuPDF
    import psycopg2
    import psycopg2.extras

    client = None
    processor_name = None
    if not args.dry_run:
        from google.cloud import documentai_v1 as documentai

        client = documentai.DocumentProcessorServiceClient(
            client_options={"api_endpoint": f"{DOCUMENT_AI_LOCATION}-documentai.googleapis.com"}
        )
        processor_name = _doc_ai_processor_name()

    conn = psycopg2.connect(args.database_url)
    try:
        if args.apply_migration:
            with conn.cursor() as cur:
                migration = Path(__file__).resolve().parents[1] / "db" / "migrations" / "022_document_pages.sql"
                cur.execute(migration.read_text(encoding="utf-8"))
            conn.commit()

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if args.document_file_id:
                cur.execute(
                    "SELECT id, url, gcs_path, title FROM project_document_files WHERE id = %s",
                    (args.document_file_id,),
                )
                candidates = cur.fetchall()
            else:
                clauses = ["dps.text_extracted_at IS NULL"]
                if not args.retry_errors:
                    clauses.append("dps.error IS NULL")
                params: list[Any] = []
                if args.state:
                    clauses.append("p.state = %s")
                    params.append(args.state.upper())
                if args.document_type:
                    types = [t.strip() for t in args.document_type.split(",") if t.strip()]
                    clauses.append("pdf.document_type = ANY(%s)")
                    params.append(types)
                where = " AND ".join(clauses)
                params.append(args.limit)
                cur.execute(
                    f"""
                    SELECT pdf.id, pdf.url, pdf.gcs_path, pdf.title
                    FROM project_document_files pdf
                    JOIN projects p ON p.project_sk = pdf.project_sk
                    LEFT JOIN document_processing_status dps ON dps.document_file_id = pdf.id
                    WHERE {where}
                    ORDER BY pdf.id
                    LIMIT %s
                    """,
                    params,
                )
                candidates = cur.fetchall()

        print(f"{len(candidates)} candidate document(s)\n")

        for row in candidates:
            print(f"[{row['id']}] {row['title']}")
            try:
                pdf_bytes = fetch_document_bytes(row)
                if args.dry_run:
                    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                    print(f"  {len(doc)} page(s), would extract (dry-run)")
                    doc.close()
                    continue

                pages = extract_document(fitz, client, processor_name, pdf_bytes)
                native_n = sum(1 for p in pages if p["ocr_engine"] == "native")
                ocr_n = len(pages) - native_n
                print(f"  {len(pages)} page(s): {native_n} native, {ocr_n} via Document AI")

                with conn.cursor() as cur:
                    for p in pages:
                        cur.execute(
                            """
                            INSERT INTO document_pages (document_file_id, page_number, raw_text, ocr_engine, avg_confidence)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (document_file_id, page_number) DO UPDATE SET
                                raw_text = EXCLUDED.raw_text,
                                ocr_engine = EXCLUDED.ocr_engine,
                                avg_confidence = EXCLUDED.avg_confidence,
                                extracted_at = now()
                            """,
                            (row["id"], p["page_number"], p["raw_text"], p["ocr_engine"], p["avg_confidence"]),
                        )
                    cur.execute(
                        """
                        INSERT INTO document_processing_status (document_file_id, text_extracted_at, page_count, error)
                        VALUES (%s, now(), %s, NULL)
                        ON CONFLICT (document_file_id) DO UPDATE SET
                            text_extracted_at = now(), page_count = EXCLUDED.page_count, error = NULL
                        """,
                        (row["id"], len(pages)),
                    )
                conn.commit()
            except Exception as e:  # noqa: BLE001 -- one bad document shouldn't kill the whole batch
                print(f"  FAILED ({row.get('gcs_path') or row.get('url')}): {e}", file=sys.stderr)
                if not args.dry_run:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO document_processing_status (document_file_id, error)
                            VALUES (%s, %s)
                            ON CONFLICT (document_file_id) DO UPDATE SET error = EXCLUDED.error
                            """,
                            (row["id"], str(e)[:500]),
                        )
                    conn.commit()
            print()
            if args.batch:
                time.sleep(args.delay)

        print("Done.")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
