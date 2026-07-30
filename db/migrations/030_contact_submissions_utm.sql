-- Adds real traffic-source attribution to contact_submissions. Today only
-- source_path (the page path, not the traffic source) is captured -- the
-- single most important attribution gap flagged in
-- docs/architecture-2026/03-growth.md: SpecIndex currently cannot tell
-- whether a demo request came from organic search, a LinkedIn post, or a
-- cold email link.
--
-- Idempotent -- safe to re-run.

BEGIN;

ALTER TABLE contact_submissions
  ADD COLUMN IF NOT EXISTS utm_source   TEXT,
  ADD COLUMN IF NOT EXISTS utm_medium   TEXT,
  ADD COLUMN IF NOT EXISTS utm_campaign TEXT,
  ADD COLUMN IF NOT EXISTS referrer     TEXT;

COMMIT;
