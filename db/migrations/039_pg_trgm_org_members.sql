-- docs/architecture-2026/00-MASTER-ROADMAP.md P3, two independent
-- additive changes:
--
-- 1. pg_trgm: prerequisite extension for scripts/find-entity-duplicates.py
--    (the fuzzy-matching merge-proposal batch job) -- trigram similarity
--    is how it finds near-duplicate manufacturer/GC/people names without
--    an exact-match requirement.
--
-- 2. org_members: the org_id-based Team-tier multi-seat invite-and-roster
--    flow (productization P3 / identity P4 -- "one build," per both
--    docs). email is captured at invite time (before the invitee has an
--    account), firebase_uid is filled in on accept -- a row can exist in
--    "invited, not yet joined" state, which the roster UI needs to show
--    differently from an active member. invite_token is single-use,
--    cleared (not just left set) once accepted so it can't be replayed.
--
-- Idempotent -- safe to re-run.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS org_members (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  org_id        TEXT NOT NULL,
  firebase_uid  TEXT,
  email         TEXT NOT NULL,
  role          TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'member')),
  invited_by    TEXT NOT NULL,
  invite_token  TEXT UNIQUE,
  invited_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  joined_at     TIMESTAMPTZ,
  UNIQUE (org_id, email)
);

CREATE INDEX IF NOT EXISTS org_members_org_id ON org_members (org_id);
CREATE INDEX IF NOT EXISTS org_members_firebase_uid ON org_members (firebase_uid) WHERE firebase_uid IS NOT NULL;

COMMIT;
