-- Zip code column -- populated only where a source actually provides it
-- (currently just Mecklenburg County's ArcGIS feed, which already returns
-- a zipcode field that was being fetched and discarded before this pass).
-- Deliberately NOT backfilled via geocoding here -- see docs/AGENT_STRATEGY.md
-- plan notes: real zip-based map filtering is phase 2, once a geocoder is
-- wired up for sources that don't provide it natively.
--
-- Idempotent — safe to re-run.

BEGIN;

ALTER TABLE projects ADD COLUMN IF NOT EXISTS zip TEXT;

COMMIT;
