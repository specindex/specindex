-- Per-page text layer for real documents, populated by
-- scripts/extract-document-text.py -- pipeline step 9 (docs/AGENT_STRATEGY.md
-- already spoken for step 8 as project enrichment, added 2026-07-29, so
-- text extraction slots in right after it, not at 8).
--
-- Native-text extraction (pdfplumber) is tried first -- most spec/RFP text
-- already has a real text layer, free and instant. Only pages that come
-- back empty (drawing sheets, scans) go to Google Document AI. Settled
-- over a self-hosted PaddleOCR pipeline after a live head-to-head test on
-- a real VA drawing cover sheet (2026-07-29): comparable accuracy, but
-- Document AI read one dense small-print regulatory citation cleanly that
-- PaddleOCR garbled, its block/paragraph output is more useful for
-- layout-aware schedule parsing later, and at the corpus's real scale
-- (~240K pages needing OCR, ~$360 total) it beats the engineering time of
-- operating a CPU OCR worker pool.
--
-- pgvector on the existing Cloud SQL instance, not a separate vector DB --
-- confirmed via Gemini architecture review this fits the corpus's real
-- data volume (~16GB at full long-term growth) without needing dedicated
-- vector infrastructure. embedding is nullable: the text layer lands
-- first, embeddings backfill in a separate pass once the chat agent's
-- retrieval step actually needs them.
--
-- Idempotent -- safe to re-run.

BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS document_pages (
  id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  document_file_id   BIGINT NOT NULL REFERENCES project_document_files(id) ON DELETE CASCADE,
  page_number        INT NOT NULL,
  raw_text           TEXT NOT NULL DEFAULT '',
  ocr_engine         TEXT NOT NULL CHECK (ocr_engine IN ('native', 'document_ai')),
  avg_confidence     NUMERIC,
  embedding          vector(768),
  extracted_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (document_file_id, page_number)
);

CREATE INDEX IF NOT EXISTS document_pages_document_file_id ON document_pages (document_file_id);

-- Full-text search index for the hybrid retrieval path (tsvector side of
-- tsvector + pgvector + reciprocal rank fusion) -- exact CSI codes and
-- model numbers (e.g. "W12x26") that pure vector search misses.
CREATE INDEX IF NOT EXISTS document_pages_raw_text_fts
  ON document_pages USING GIN (to_tsvector('english', raw_text));

-- Per-document pipeline checkpoint, same watermark/idempotency pattern as
-- the rest of this codebase's incremental pulls -- lets step 9 run
-- repeatedly over the corpus without re-processing (and re-billing)
-- documents it's already extracted.
CREATE TABLE IF NOT EXISTS document_processing_status (
  document_file_id         BIGINT PRIMARY KEY REFERENCES project_document_files(id) ON DELETE CASCADE,
  text_extracted_at        TIMESTAMPTZ,
  structured_extraction_at TIMESTAMPTZ,
  page_count               INT,
  error                    TEXT
);

COMMIT;
