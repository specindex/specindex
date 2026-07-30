-- Extends project_enrichment_checks (016) with the three things it's
-- missing: a fingerprint of the source data actually fed into the
-- enrichment prompt (so "re-enrich if changed" replaces "re-enrich if 30
-- days old"), a schema/prompt version (so a future prompt change can
-- selectively force re-enrichment instead of an all-or-nothing backfill),
-- and an explicit status (today "attempted" is implied by row existence;
-- failures are indistinguishable from untried projects).
--
-- last_enriched_at is distinct from checked_at: checked_at fires on every
-- ATTEMPT (including "found nothing, don't retry for 30 days");
-- last_enriched_at only advances when the attempt actually wrote new/
-- changed rows into project_enrichment.
--
-- Gemini review flagged a real bug in the original fingerprint-only
-- design: enrichment discovers EXTERNAL web content, but the fingerprint
-- only hashes LOCAL fields -- a sparse project's fingerprint never
-- changes, so it would be permanently frozen out of re-enrichment. The
-- 180-day max-staleness fallback below is the fix: re-enrich if the
-- fingerprint changed OR it's been over 180 days, whichever comes first.
--
-- Idempotent -- safe to re-run.

BEGIN;

ALTER TABLE project_enrichment_checks
  ADD COLUMN IF NOT EXISTS source_fingerprint TEXT,
  ADD COLUMN IF NOT EXISTS enrichment_version INTEGER NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'done', 'failed', 'stale')),
  ADD COLUMN IF NOT EXISTS last_enriched_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS project_enrichment_checks_status
  ON project_enrichment_checks (status)
  WHERE status IN ('pending', 'stale');

COMMIT;
