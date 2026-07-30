-- Per-user project tracking -- the "Tracked" pipeline in the signed-in
-- home experience. Lets a user move a project through a lightweight
-- sales pipeline (watching -> contacted -> quoted -> won/lost) with a
-- free-text note. One row per (user, project) pair: tracking is a
-- deliberate action a user takes, not a passive/computed state.
--
-- project_sk (not the project_id text slug) to match the FK convention
-- every other per-project table already uses (project_scores,
-- project_events, project_sources, project_news, project_documents).
--
-- clerk_user_id is not a foreign key to any local table -- same pattern
-- as user_profiles (021_user_profiles.sql), since Clerk is the source of
-- truth for identity, not a local users table.
--
-- Idempotent -- safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS user_tracked_projects (
  id                BIGSERIAL PRIMARY KEY,
  clerk_user_id     TEXT NOT NULL,
  project_sk        BIGINT NOT NULL REFERENCES projects(project_sk) ON DELETE CASCADE,
  stage             TEXT NOT NULL DEFAULT 'watching'
                      CHECK (stage IN ('watching', 'contacted', 'quoted', 'won', 'lost')),
  note              TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (clerk_user_id, project_sk)
);

CREATE INDEX IF NOT EXISTS user_tracked_projects_user
  ON user_tracked_projects (clerk_user_id);

COMMIT;
