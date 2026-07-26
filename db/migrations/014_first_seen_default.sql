-- Fix: first_seen_at (added by migration 002) had no column default and
-- the loader's INSERT list never set it, so every project loaded since
-- 002 ran has first_seen_at = NULL. Needed for the "new this week" badge
-- on the projects dashboard (docs/ROADMAP.md item 46).
--
-- Going forward: DEFAULT now() means a plain INSERT (loader still omits
-- the column) picks it up automatically; it's already excluded from the
-- loader's ON CONFLICT ... DO UPDATE SET, so existing rows are untouched
-- on reload.
--
-- Backfill for currently-NULL rows: there is no real historical record of
-- when these were first ingested (loaded_at gets overwritten on every
-- reload, so it can't be used as a proxy — it would falsely stamp
-- thousands of pre-existing projects as "seen today"). Backfilling to
-- "now" would make them all incorrectly show as new-this-week for the
-- next 7 days. Backfilling to 365 days ago is the honest choice: we don't
-- know the real date, so treat them as not-new rather than falsely new.
--
-- Idempotent — safe to re-run.

BEGIN;

ALTER TABLE projects ALTER COLUMN first_seen_at SET DEFAULT now();

UPDATE projects
SET first_seen_at = now() - INTERVAL '365 days'
WHERE first_seen_at IS NULL;

COMMIT;
