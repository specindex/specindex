-- docs/architecture-2026/03-growth.md P1: "Client sends PostHog's
-- distinct_id alongside the /v1/contact POST body so the anonymous
-- pre-signup session can be joined to the submission row, and later to
-- the firebase_uid once PostHog's identify() call fires on sign-in."
--
-- Idempotent -- safe to re-run.

BEGIN;

ALTER TABLE contact_submissions
  ADD COLUMN IF NOT EXISTS posthog_distinct_id TEXT;

COMMIT;
