-- Adds real GCS-backed storage to project_document_files (migration 018),
-- which until now only ever stored the original external source URL --
-- exactly the kind of link that rots (confirmed live 2026-07-29:
-- investatlanta.com moved/removed the page a Teachers Village document
-- pointed at, 404ing on a real user click).
--
-- gcs_path is nullable on purpose -- existing rows (fetched before this
-- migration) keep working off `url` alone until backfilled by
-- scripts/fetch-and-store-documents.py; this is additive, not a breaking
-- change to what's already live.
--
-- content_sha256 is the dedup key: before uploading a freshly-fetched
-- document, the fetch script checks whether an object with that hash
-- already exists in GCS and skips the upload if so -- so the same file
-- linked from two different source URLs (or re-fetched on a later
-- pipeline run) is never stored twice. Explicitly requested 2026-07-29:
-- "don't want to overpay for storage of documents if its duplicated."
--
-- Idempotent -- safe to re-run.

BEGIN;

ALTER TABLE project_document_files
  ADD COLUMN IF NOT EXISTS gcs_path       TEXT,
  ADD COLUMN IF NOT EXISTS content_sha256 TEXT,
  ADD COLUMN IF NOT EXISTS fetched_at     TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS project_document_files_content_sha256
  ON project_document_files (content_sha256);

COMMIT;
