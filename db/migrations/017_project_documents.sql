-- Aggregate document-availability signal per project, populated by
-- scripts/compute-project-documents.py from the checked-in
-- data/documents/{georgia,new-jersey,fulton-county}/*.json manifests
-- (three different shapes -- GA's projects[].documents[], NJ's
-- by_project{}.documents[], Fulton's flat project_documents[] with
-- project_id per entry -- normalized into one table by that script).
--
-- Deliberately project-level aggregate (has_documents + count), not a
-- per-document row like project_sources -- this feeds a list-page filter
-- ("does this project have attached documents or not"), not a documents
-- browser. Individual document URLs stay in the git-committed manifests;
-- add a per-row table later if/when there's a UI that needs to list them.
--
-- Idempotent -- safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS project_documents (
  project_sk      BIGINT PRIMARY KEY REFERENCES projects(project_sk) ON DELETE CASCADE,
  document_count  INT NOT NULL DEFAULT 0,
  has_documents   BOOLEAN NOT NULL GENERATED ALWAYS AS (document_count > 0) STORED,
  computed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS project_documents_has_documents ON project_documents (has_documents);

COMMIT;
