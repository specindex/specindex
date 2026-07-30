-- Real organizations table, replacing the "org_id = owner's own
-- firebase_uid" shortcut migration 039/api/main.py shipped with. Caught by
-- a Gemini review pass the same day: coupling an org's identity to one
-- user account breaks on owner account deletion (orphaned org_members rows,
-- headless org), ownership transfer (would require rewriting every
-- org_members.org_id row instead of one organizations row), and downgrade
-- (no place to represent "this org's seats are no longer valid"). Safe to
-- do now, not as a later migration: org_members/user_profiles.org_id had
-- zero live rows when this was caught -- built and reviewed same day,
-- before any real Team-tier account existed.
--
-- Idempotent -- safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS organizations (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name          TEXT,
  owner_uid     TEXT NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS organizations_owner_uid ON organizations (owner_uid);

ALTER TABLE org_members
  ALTER COLUMN org_id TYPE BIGINT USING NULL;

ALTER TABLE org_members
  ADD CONSTRAINT org_members_org_id_fkey FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE;

COMMIT;
