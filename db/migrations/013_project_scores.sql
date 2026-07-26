-- Project score: value + recency + news, the "magic sauce" from
-- docs/PROJECT_PAGE_REDESIGN.md -- tells a manufacturer's rep which open
-- project to prioritize, not just that it exists. This is v1 -- a simple,
-- transparent, adjustable starting formula (see
-- scripts/compute-project-scores.py), not a final methodology. Stored in
-- its own table (like county_coverage/state_quality) rather than columns
-- on `projects`, since it's fully re-derived on every run, not
-- hand-edited data.
--
-- Idempotent — safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS project_scores (
  project_sk      BIGINT PRIMARY KEY REFERENCES projects(project_sk) ON DELETE CASCADE,
  score           INTEGER NOT NULL,
  value_score     INTEGER NOT NULL,
  recency_score   INTEGER NOT NULL,
  news_score      INTEGER NOT NULL,
  computed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS project_scores_score ON project_scores (score DESC);

COMMIT;
