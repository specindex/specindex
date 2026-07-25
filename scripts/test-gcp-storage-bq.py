#!/usr/bin/env python3
"""One-off smoke test for the GCS bucket + BigQuery warehouse dataset
provisioned for the spec-book extraction pipeline (see docs/CONTEXT.md,
scripts/extract-spec-book.py). Not part of the pipeline itself -- just
proves read/write works end to end before wiring real code to it.

Usage: python3 scripts/test-gcp-storage-bq.py
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

from google.cloud import bigquery, storage

PROJECT_ID = "specindex-ai"
BUCKET_NAME = "specindex-ai-raw-documents"
DATASET = "warehouse"
TABLE = "spec_extractions"
SAMPLE_PDF = Path(
    "data/documents/fulton-county/county-forms/"
    "commercial-plan-review-building-permit-instructions.pdf"
)


def test_storage() -> None:
    print("--- GCS round trip ---")
    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(BUCKET_NAME)
    blob_name = f"_smoke-test/{uuid.uuid4().hex}.pdf"
    blob = bucket.blob(blob_name)

    original_bytes = SAMPLE_PDF.read_bytes()
    blob.upload_from_filename(str(SAMPLE_PDF))
    print(f"uploaded {SAMPLE_PDF.name} -> gs://{BUCKET_NAME}/{blob_name}")

    downloaded_bytes = bucket.blob(blob_name).download_as_bytes()
    assert downloaded_bytes == original_bytes, "downloaded bytes do not match upload"
    print(f"downloaded back, {len(downloaded_bytes)} bytes, byte-for-byte match")

    blob.delete()
    print("deleted test object")


def test_bigquery() -> None:
    print("--- BigQuery round trip ---")
    client = bigquery.Client(project=PROJECT_ID)
    table_ref = f"{PROJECT_ID}.{DATASET}.{TABLE}"
    extraction_id = f"smoke-test-{uuid.uuid4().hex}"

    row = {
        "extraction_id": extraction_id,
        "project_id": "smoke-test",
        "source_document": "smoke-test.pdf",
        "csi_division": "23",
        "csi_section": "23 00 00",
        "product_category": "test",
        "basis_of_design_product": "test product",
        "approved_manufacturers": "test mfr",
        "substitution_language": None,
        "confidence_score": 1.0,
        "extracted_at": None,
    }
    errors = client.insert_rows_json(table_ref, [row])
    if errors:
        raise RuntimeError(f"insert failed: {errors}")
    print(f"inserted test row {extraction_id}")

    query = f"""
        SELECT extraction_id, csi_division
        FROM `{table_ref}`
        WHERE extraction_id = @extraction_id
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("extraction_id", "STRING", extraction_id)
        ]
    )
    results = list(client.query(query, job_config=job_config).result())
    assert len(results) == 1, f"expected 1 row, got {len(results)} (streaming buffer lag?)"
    print(f"queried back: {dict(results[0])}")

    delete_query = f"DELETE FROM `{table_ref}` WHERE extraction_id = @extraction_id"
    try:
        client.query(delete_query, job_config=job_config).result()
        print("deleted test row")
    except Exception as exc:  # streaming buffer often blocks DELETE for a few minutes
        print(
            f"could not delete test row immediately (expected if BQ streaming buffer "
            f"hasn't flushed yet): {exc}\n"
            f"Row extraction_id={extraction_id} will need manual cleanup once the "
            f"buffer flushes (usually within ~90 min):\n  {delete_query}"
        )


def main() -> int:
    if not SAMPLE_PDF.exists():
        print(f"sample PDF not found: {SAMPLE_PDF}", file=sys.stderr)
        return 1
    try:
        test_storage()
        test_bigquery()
    except Exception as exc:
        print(f"SMOKE TEST FAILED: {exc}", file=sys.stderr)
        return 1
    print("\nAll smoke tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
