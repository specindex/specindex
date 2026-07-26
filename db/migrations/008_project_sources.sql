-- Formalizes the provenance already partially captured in projects.sources
-- (a JSONB array of {url, title}, populated by
-- scripts/project_identity.py's merge_projects()) into a proper one-row-
-- per-(project, source) table -- so "where did this record come from" and
-- "which source currently owns this project's canonical fields" are real
-- queryable facts, not just an unstructured array.
--
-- projects.sources stays as-is -- it's what the project-detail page and API
-- already read for source links. This table is additive, populated by
-- scripts/load-corpus-to-postgres.py going forward (see that script for how
-- source_name gets derived via project_identity.classify_source()).
--
-- Idempotent — safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS project_sources (
  id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  project_sk        BIGINT NOT NULL REFERENCES projects(project_sk) ON DELETE CASCADE,
  source_name       TEXT NOT NULL,
  source_record_id  TEXT,
  source_url        TEXT,
  raw_data          JSONB,
  ingested_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_primary        BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS project_sources_project_sk ON project_sources (project_sk);
CREATE UNIQUE INDEX IF NOT EXISTS project_sources_unique
  ON project_sources (project_sk, source_name, COALESCE(source_url, ''));

COMMIT;
