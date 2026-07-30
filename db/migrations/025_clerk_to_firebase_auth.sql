-- Auth provider swap: Clerk -> Firebase Auth (2026-07-29). Only one real
-- account existed under Clerk at the time of this migration (the founder's
-- own test/dev sign-in), so this is a straight column rename, not a data
-- migration -- the old Clerk-issued `sub` values in these columns become
-- orphaned (harmless leftover rows, not referenced by anything else) once
-- the same person signs back in via Firebase Auth and gets a new row keyed
-- by their Firebase uid. Delete the stale Clerk-keyed rows manually if
-- they bother you; nothing depends on them.
--
-- RENAME COLUMN preserves the existing indexes/constraints in place (they
-- keep their old names, e.g. user_tracked_projects_user, but now cover the
-- renamed column) -- no need to drop and recreate them.
--
-- Plain "RENAME COLUMN x TO y" errors on a second run once x no longer
-- exists, so this is wrapped in an existence check per table to actually
-- be idempotent/safe to re-run, matching every other migration's stated
-- guarantee.

BEGIN;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'user_profiles' AND column_name = 'clerk_user_id'
  ) THEN
    ALTER TABLE user_profiles RENAME COLUMN clerk_user_id TO firebase_uid;
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'user_tracked_projects' AND column_name = 'clerk_user_id'
  ) THEN
    ALTER TABLE user_tracked_projects RENAME COLUMN clerk_user_id TO firebase_uid;
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'user_saved_views' AND column_name = 'clerk_user_id'
  ) THEN
    ALTER TABLE user_saved_views RENAME COLUMN clerk_user_id TO firebase_uid;
  END IF;
END $$;

COMMIT;
