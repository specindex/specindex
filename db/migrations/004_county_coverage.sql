-- Coverage reporting table: how many projects per (state, county), which
-- sources contributed them, and whether that county has "deep" coverage
-- (a dedicated local permit feed -- ArcGIS/Accela city or county source)
-- or only "thin" coverage (a broad statewide/federal source with no
-- dedicated local feed: DRI, USAspending, SAM.gov, hand-curated research).
--
-- Populated by scripts/compute-county-coverage.py, which derives source
-- attribution from each project_id's prefix (e.g. "ga-fulton-...",
-- "nc-mecklenburg-...") rather than a stored column, since that
-- classification didn't exist when most of the corpus was loaded. Re-run
-- the script after any corpus reload to refresh this table -- it's a
-- derived/reporting table, not a source of truth itself.
--
-- Idempotent — safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS county_coverage (
  state           CHAR(2) NOT NULL,
  county          TEXT NOT NULL,
  project_count   INTEGER NOT NULL,
  sources         TEXT[] NOT NULL,
  coverage_type   TEXT NOT NULL CHECK (coverage_type IN ('deep', 'thin')),
  computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (state, county)
);

CREATE INDEX IF NOT EXISTS county_coverage_state ON county_coverage (state);
CREATE INDEX IF NOT EXISTS county_coverage_type ON county_coverage (coverage_type);

COMMIT;
