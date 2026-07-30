-- Saved territory/category presets -- the "Saved views" list in the
-- signed-in home's left pane. Lets a user store more than one filter
-- combination (e.g. "GA + FL Lighting" and "Southeast, all categories")
-- and switch between them without re-picking states/categories each time.
--
-- Deliberately separate from user_profiles (021_user_profiles.sql):
-- user_profiles.territory_states/categories is the ONE active default
-- used to personalize the app on sign-in; this table is the full list of
-- presets a user has saved, of which their profile's current values are
-- just the most-recently-selected one. Not a foreign key relationship --
-- the two are independent, profile doesn't reference a saved view row.
--
-- Numbered 024 (not 023) -- 022 and 023 landed concurrently from other
-- work in progress on this branch's history; no migration used 023
-- either, gap is intentional, not a mistake.
--
-- Idempotent -- safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS user_saved_views (
  id                BIGSERIAL PRIMARY KEY,
  clerk_user_id     TEXT NOT NULL,
  name              TEXT NOT NULL,
  territory_states  TEXT[] NOT NULL DEFAULT '{}',
  categories        TEXT[] NOT NULL DEFAULT '{}',
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS user_saved_views_user
  ON user_saved_views (clerk_user_id);

COMMIT;
