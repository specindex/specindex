-- docs/architecture-2026/04-productization.md P1: "Enforce the Free-tier
-- 1-brand-check/week limit ... already promised on the pricing page but
-- not implemented in api/main.py." Matches app/pricing/page.tsx's exact
-- copy: Free = "1 brand check per week", Pro/Team = "Unlimited brand
-- checks". A usage-counter table, not a rolling-window computation --
-- simple, and a week boundary a user can reason about ("resets Monday")
-- beats an opaque rolling 7-day count for a limit this small.
--
-- Idempotent -- safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS brand_check_usage (
  firebase_uid TEXT NOT NULL,
  week_start   DATE NOT NULL,  -- Monday of the ISO week, see api/main.py
  check_count  INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (firebase_uid, week_start)
);

COMMIT;
