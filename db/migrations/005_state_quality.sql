-- Data quality reporting table: per-state field completeness and freshness,
-- so a source that's gone stale or has a sparse schema (e.g. no city/
-- value/contractor fields, like GA's Forsyth County source) is visible
-- without eyeballing raw records.
--
-- Populated by scripts/compute-state-quality.py. Deliberately excludes a
-- duplicate-rate metric in v1 -- computing it accurately means re-running
-- project_identity.dedupe_projects() per state, which is expensive and not
-- proven valuable yet. Revisit only if completeness/freshness alone aren't
-- enough to flag a bad source. Re-run the script after any corpus reload --
-- it's a derived/reporting table, not a source of truth itself.
--
-- Idempotent — safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS state_quality (
  state             CHAR(2) NOT NULL PRIMARY KEY,
  total_projects    INTEGER NOT NULL,
  pct_has_city      NUMERIC NOT NULL,
  pct_has_value     NUMERIC NOT NULL,
  pct_has_contractor NUMERIC NOT NULL,
  pct_has_date      NUMERIC NOT NULL,
  freshness_days    INTEGER,
  computed_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;
