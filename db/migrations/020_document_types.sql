-- Adds a deterministic, keyword-based document category to
-- project_document_files, populated by compute-project-documents.py's
-- classify_document_type() from the real filename/title -- no LLM
-- involved, same discipline as the rest of this pipeline (cheap,
-- reproducible, no hallucination risk on a field just used for filtering).
--
-- 'other' is the catch-all for titles that don't match a known keyword
-- pattern (e.g. opaque filenames, cover letters, correspondence).
--
-- Idempotent -- safe to re-run.

BEGIN;

ALTER TABLE project_document_files
  ADD COLUMN IF NOT EXISTS document_type TEXT NOT NULL DEFAULT 'other';

CREATE INDEX IF NOT EXISTS project_document_files_document_type
  ON project_document_files (document_type);

COMMIT;
