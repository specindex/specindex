-- User profiles for signed-in accounts (Clerk-authenticated), replacing the
-- localStorage-only territory/category stand-in in ProjectsDashboard.tsx
-- (docs/ROADMAP.md item 46, Phase B). One row per Clerk user, created lazily
-- on first authenticated /v1/me/profile write, not on Clerk signup itself --
-- keeps this table demand-driven, no webhook dependency for v1.
--
-- territory_states/categories are arrays, not a join table, matching the
-- shape ProjectsDashboard.tsx already keeps client-side -- categories
-- generalized to an array even though v1 UI may start single-select, per
-- the Team-tier "multiple brand profiles" pricing promise. Upgradable to a
-- join table later without a breaking migration.
--
-- clerk_org_id is nullable and unused by any v1 endpoint -- reserved so a
-- later Team-tier/org-seat phase doesn't need another migration.
--
-- email is sourced fresh from the verified JWT on every write, not treated
-- as canonical once stored -- a Gemini review of the implementation plan
-- flagged that lazily-written emails go stale if a user changes their
-- email in Clerk after onboarding.
--
-- Idempotent -- safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS user_profiles (
  id                BIGSERIAL PRIMARY KEY,
  clerk_user_id     TEXT NOT NULL UNIQUE,
  email             TEXT NOT NULL,
  company           TEXT,
  territory_states  TEXT[] NOT NULL DEFAULT '{}',
  categories        TEXT[] NOT NULL DEFAULT '{}',
  clerk_org_id      TEXT,
  onboarded_at      TIMESTAMPTZ,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS user_profiles_clerk_org_id
  ON user_profiles (clerk_org_id) WHERE clerk_org_id IS NOT NULL;

COMMIT;
