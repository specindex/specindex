-- GIN trigram indexes for the entity directory tables. Migration 039
-- enabled pg_trgm but never added these -- find-entity-duplicates.py's
-- self-join (a.normalized_name % b.normalized_name) is an O(n^2) nested
-- loop without them, confirmed live: timed out after 2 minutes against
-- 13,865 general_contractors / 25,242 people once normalize-entity-
-- directories.py's real run finally completed and populated these tables
-- for the first time. manufacturers (305 rows) ran fine without an index
-- at this row count, but the index costs nothing to add there too.
--
-- Idempotent -- safe to re-run.

BEGIN;

CREATE INDEX IF NOT EXISTS manufacturers_normalized_trgm
  ON manufacturers USING gin (normalized_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS general_contractors_normalized_trgm
  ON general_contractors USING gin (normalized_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS people_normalized_trgm
  ON people USING gin (normalized_name gin_trgm_ops);

COMMIT;
