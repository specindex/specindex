-- Adds week-over-week movement tracking to county_coverage, so the Insights
-- dashboard can show which counties actually gained projects between two
-- runs of scripts/compute-county-coverage.py, not just a point-in-time count.
--
-- previous_project_count/delta are populated by compute-county-coverage.py
-- reading the prior row before each upsert -- NULL on a county's first-ever
-- computation (nothing to diff against yet).
--
-- Idempotent — safe to re-run.

BEGIN;

ALTER TABLE county_coverage ADD COLUMN IF NOT EXISTS previous_project_count INTEGER;
ALTER TABLE county_coverage ADD COLUMN IF NOT EXISTS delta INTEGER;

COMMIT;
