-- Pipeline run history: one row per execution of a scheduled/on-demand
-- puller workflow (pull-national.yml, pull-state.yml), so the ops
-- dashboard (specindex.ai/ops/) can show whether the agents are actually
-- healthy over time -- not just the latest project count, but the trend
-- and the failure history.
--
-- Written directly by the GitHub Actions workflows themselves (a plain
-- INSERT at the end of each run, using the same DATABASE_URL/Cloud SQL
-- Proxy connection already open for the load/coverage/quality steps) --
-- not derived from anything else, since GitHub's own Actions API isn't
-- queried by the live site (no GitHub token wired into api/main.py, and
-- no reason to add one just for this).
--
-- Idempotent — safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS pipeline_runs (
  id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  workflow           TEXT NOT NULL,          -- e.g. 'pull-national', 'pull-state'
  run_url            TEXT,                    -- link back to the GitHub Actions run
  started_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  projects_before    INTEGER,
  projects_after     INTEGER,
  step_outcomes      JSONB NOT NULL DEFAULT '{}'::jsonb,  -- {"pull_sam_ga": "success", ...}
  top_movers         TEXT,
  overall_status     TEXT NOT NULL CHECK (overall_status IN ('success', 'partial_failure', 'failure'))
);

CREATE INDEX IF NOT EXISTS pipeline_runs_workflow_started ON pipeline_runs (workflow, started_at DESC);

COMMIT;
