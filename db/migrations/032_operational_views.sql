-- ROADMAP.md item 49 / docs/architecture-2026/00-MASTER-ROADMAP.md P1:
-- "A small set of well-commented SQL views, not a dbt semantic layer, at
-- this stage" (01-data-platform.md). Same pattern as the existing
-- v_project_stats in db/schema.sql -- these are exactly what a future
-- MCP server would expose as read-only tools/resources (see that doc's
-- "Connection point to MCP" section), so each view's grain and freshness
-- are stated explicitly rather than left for a reader to guess.
--
-- Idempotent -- safe to re-run.

BEGIN;

-- Grain: one row per (call_site, model, calendar day). Freshness:
-- recomputed on read (not materialized) -- llm_call_log is append-only
-- and small enough that a live aggregate is cheap; revisit as a
-- materialized view only if this starts showing up in slow-query logs.
CREATE OR REPLACE VIEW v_llm_daily_spend AS
SELECT
  date_trunc('day', called_at)::date AS day,
  call_site,
  model,
  count(*)::int AS call_count,
  sum(input_tokens)::bigint AS total_input_tokens,
  sum(output_tokens)::bigint AS total_output_tokens,
  sum(grounding_requests_count)::bigint AS total_grounding_requests,
  sum(estimated_cost_usd)::numeric(12,4) AS total_estimated_cost_usd
FROM llm_call_log
GROUP BY 1, 2, 3;

-- Grain: one row per state. Freshness: recomputed on read.
-- "Current" enrichment = status='done' AND enrichment_version matches
-- the latest version seen for that state (a version bump means every
-- prior 'done' row is stale even though its own status column hasn't
-- been updated yet -- that backfill is a separate P1/P2 job, this view
-- just reports the gap honestly rather than overcounting coverage).
CREATE OR REPLACE VIEW v_enrichment_coverage AS
WITH latest_version AS (
  SELECT max(enrichment_version) AS v FROM project_enrichment_checks
)
SELECT
  p.state,
  count(*)::int AS total_projects,
  count(c.project_sk)::int AS ever_checked,
  count(*) FILTER (
    WHERE c.status = 'done' AND c.enrichment_version = (SELECT v FROM latest_version)
  )::int AS current_and_done,
  round(
    100.0 * count(*) FILTER (
      WHERE c.status = 'done' AND c.enrichment_version = (SELECT v FROM latest_version)
    ) / NULLIF(count(*), 0),
    1
  ) AS pct_current_and_done
FROM projects p
LEFT JOIN project_enrichment_checks c ON c.project_sk = p.project_sk
GROUP BY p.state
ORDER BY total_projects DESC;

-- Grain: one row per workflow. Freshness: recomputed on read; "latest
-- run" is a real-time LATERAL join, not a snapshot.
CREATE OR REPLACE VIEW v_pipeline_health AS
SELECT
  w.workflow,
  latest.started_at AS last_run_at,
  latest.overall_status AS last_run_status,
  latest.projects_after - latest.projects_before AS last_run_delta,
  (
    SELECT count(*) FROM pipeline_runs r
    WHERE r.workflow = w.workflow AND r.overall_status = 'failure'
      AND r.started_at > now() - interval '30 days'
  )::int AS failures_last_30d
FROM (SELECT DISTINCT workflow FROM pipeline_runs) w
CROSS JOIN LATERAL (
  SELECT started_at, overall_status, projects_after, projects_before
  FROM pipeline_runs r
  WHERE r.workflow = w.workflow
  ORDER BY started_at DESC
  LIMIT 1
) latest;

COMMIT;
