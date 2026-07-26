-- Tracks Mapbox GL JS map-load count per calendar month, so the API can
-- hard-stop issuing tokens once a quota threshold is hit -- protects
-- against a bot/crawler hammering the noindex /map/ page (or a leaked
-- token being reused elsewhere) from generating a surprise Mapbox bill.
-- This is a backstop, not the primary defense -- the Mapbox token itself
-- should also be URL-restricted to specindex.ai in the Mapbox account
-- dashboard, which stops unauthorized *domains* regardless of this quota.
--
-- Postgres-backed rather than in-memory: an in-memory counter resets on
-- every Cloud Run cold start, which happens often enough at this traffic
-- level that it would barely rate-limit anything.
--
-- Idempotent — safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS mapbox_usage (
  month       TEXT PRIMARY KEY,  -- 'YYYY-MM'
  load_count  INTEGER NOT NULL DEFAULT 0
);

COMMIT;
