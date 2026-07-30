-- docs/architecture-2026/03-growth.md P2 §2c: persona rides along as a
-- hidden field on the existing /v1/contact POST, not a new endpoint or
-- field set -- see components/marketing/DemoModal.tsx's DemoPersona type
-- for the fixed set of values this actually takes.
--
-- Idempotent -- safe to re-run.

BEGIN;

ALTER TABLE contact_submissions
  ADD COLUMN IF NOT EXISTS persona TEXT;

COMMIT;
