-- docs/architecture-2026/00-MASTER-ROADMAP.md P2, two small independent
-- additive schema changes bundled into one migration:
--
-- 1. ask_log: one row per /v1/projects/{id}/ask, /v1/me/ask, and (once
--    built) the MCP server's ask_about_territory tool call. Growth doc:
--    "also a P0-adjacent dependency for productization's MCP usage
--    metering -- build once." project_id is nullable because a
--    territory-scoped ask has no single project to attach to.
--
-- 2. user_profiles.org_id: nullable forward seam for Team-tier org/seat
--    billing (identity doc P3/P4) -- adding the column now costs nothing
--    and avoids a later migration touching every row; nothing reads or
--    writes it yet.
--
-- Idempotent -- safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS ask_log (
  id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  firebase_uid TEXT NOT NULL,
  scope        TEXT NOT NULL CHECK (scope IN ('project', 'territory')),
  project_id   TEXT,
  question     TEXT NOT NULL,
  answer       TEXT NOT NULL,
  asked_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ask_log_firebase_uid ON ask_log (firebase_uid, asked_at DESC);

ALTER TABLE user_profiles
  ADD COLUMN IF NOT EXISTS org_id TEXT;

CREATE INDEX IF NOT EXISTS user_profiles_org_id
  ON user_profiles (org_id) WHERE org_id IS NOT NULL;

COMMIT;
