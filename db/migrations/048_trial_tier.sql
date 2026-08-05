-- Wires up the `trial` tier that's existed in user_profiles.subscription_tier's
-- CHECK constraint since migration 027 but was never actually set by
-- anything -- "Start for free" (components/SiteHeader.tsx) now grants a
-- real 14-day trial instead of silently landing on `free`.
--
-- Idempotent -- safe to re-run.

BEGIN;

ALTER TABLE user_profiles
  ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMPTZ;

COMMIT;
