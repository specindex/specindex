-- SpecIndex MVP schema for Cloud Run testing.
-- Full lifecycle schema lives in docs/DATABASE_DESIGN.md.
-- This is the v1 baseline. On a fresh install, apply db/migrations/*.sql
-- (in order) after this file to bring the table up to the current schema —
-- see docs/DATA_SCHEMA_V2.md for what 002_schema_v2.sql adds and why.

CREATE TABLE IF NOT EXISTS projects (
  project_id              TEXT PRIMARY KEY,
  name                    TEXT NOT NULL,
  state                   CHAR(2),
  city                    TEXT,
  county                  TEXT,
  status                  TEXT NOT NULL,
  project_type            TEXT,
  estimated_value_usd     BIGINT,
  square_footage          INTEGER,
  owner                   TEXT,
  architect               TEXT,
  general_contractor      TEXT,
  opened_or_announced_date DATE,
  description             TEXT,
  key_specs               JSONB NOT NULL DEFAULT '[]',
  mentioned_brands        JSONB NOT NULL DEFAULT '[]',
  competitor_watch        JSONB NOT NULL DEFAULT '[]',
  sources                 JSONB NOT NULL DEFAULT '[]',
  open_for                TEXT,
  corpus_generated_at     TIMESTAMPTZ,
  loaded_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS projects_state ON projects (state);
CREATE INDEX IF NOT EXISTS projects_status ON projects (status);
CREATE INDEX IF NOT EXISTS projects_state_status ON projects (state, status);

CREATE OR REPLACE VIEW v_project_stats AS
SELECT
  count(*)::int AS total,
  count(DISTINCT state)::int AS states,
  count(*) FILTER (WHERE status IN ('planning', 'design', 'permitting', 'bidding'))::int AS early_stage
FROM projects;
