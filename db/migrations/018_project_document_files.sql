-- Per-document rows (title/url), companion to project_documents' aggregate
-- count (migration 017). That table only tracks "how many" for the list-page
-- filter; this one holds what a user actually clicks to view a document on
-- the detail page. Populated by the same scripts/compute-project-documents.py.
--
-- Idempotent -- safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS project_document_files (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  project_sk    BIGINT NOT NULL REFERENCES projects(project_sk) ON DELETE CASCADE,
  title         TEXT NOT NULL,
  url           TEXT NOT NULL,
  content_type  TEXT,
  computed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (project_sk, url)
);

CREATE INDEX IF NOT EXISTS project_document_files_project_sk ON project_document_files (project_sk);

COMMIT;
