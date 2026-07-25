-- Split csi_divisions (JSONB array on projects) into a proper one-to-many
-- fact table. See docs/DATA_SCHEMA_V2.md — a project can hit a dozen+ CSI
-- divisions, each with its own citation; that's a fact row, not a nested
-- attribute, and normalized tables join/filter cleanly from Snowflake/
-- Databricks/BI tools in a way JSONB array operators don't.
--
-- Safe to run: csi_divisions was empty for all rows at the time this was
-- written (the extraction pipeline had not populated any yet). The backfill
-- step below is defensive — it only does something if that has changed.
--
-- Idempotent — safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS project_csi_divisions (
  id                       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  project_sk               BIGINT NOT NULL REFERENCES projects(project_sk) ON DELETE CASCADE,
  division                 CHAR(2) NOT NULL,
  division_name            TEXT NOT NULL,
  basis_of_design_product  TEXT,
  approved_manufacturers   TEXT[] NOT NULL DEFAULT '{}',
  substitution_language    TEXT,
  model_numbers            TEXT[] NOT NULL DEFAULT '{}',
  source_document           TEXT,
  page                      INTEGER,
  confidence                TEXT,
  created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (project_sk, division, source_document, page)
);

CREATE INDEX IF NOT EXISTS project_csi_divisions_project_sk ON project_csi_divisions (project_sk);
CREATE INDEX IF NOT EXISTS project_csi_divisions_division ON project_csi_divisions (division);

-- Defensive backfill: only fires if csi_divisions on some row is non-empty.
INSERT INTO project_csi_divisions (
  project_sk, division, division_name, basis_of_design_product,
  approved_manufacturers, substitution_language, model_numbers,
  source_document, page, confidence
)
SELECT
  p.project_sk,
  elem->>'division',
  elem->>'division_name',
  elem->>'basis_of_design_product',
  COALESCE((SELECT array_agg(x) FROM jsonb_array_elements_text(elem->'approved_manufacturers') x), '{}'),
  elem->>'substitution_language',
  COALESCE((SELECT array_agg(x) FROM jsonb_array_elements_text(elem->'model_numbers') x), '{}'),
  elem->>'source_document',
  NULLIF(elem->>'page', '')::int,
  elem->>'confidence'
FROM projects p, jsonb_array_elements(p.csi_divisions) elem
WHERE jsonb_array_length(p.csi_divisions) > 0
ON CONFLICT (project_sk, division, source_document, page) DO NOTHING;

-- csi_division_codes (SMALLINT[] summary on the project row) stays — cheap
-- denormalized filter for "does this project touch division X at all"
-- without a join. Only the detailed/cited JSONB column is being dropped.
ALTER TABLE projects DROP COLUMN IF EXISTS csi_divisions;

COMMIT;
