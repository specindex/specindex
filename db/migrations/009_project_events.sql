-- Project timeline: one row per lifecycle milestone (Announced, Permit
-- Issued, Bid Opened, Awarded, ...), so a project's history is queryable
-- as a sequence of dated events, not just a single current `status` value.
-- This is the genuinely new capability the Perplexity-sourced schema doc
-- argued for -- projects.status still tracks *current state*; event_type
-- here uses its own, decoupled vocabulary describing *what happened when*.
--
-- v1 events are derived at load time from project_id/record_type (see
-- project_identity.derive_event_type()), not source-authored -- rewriting
-- every pull script to emit its own event stream is out of scope for a
-- first pass. The UNIQUE constraint makes re-running a load idempotent:
-- the same (project, type, date, source) tuple just no-ops on conflict
-- instead of piling up duplicate events on every weekly/monthly run.
--
-- Idempotent — safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS project_events (
  id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  project_sk   BIGINT NOT NULL REFERENCES projects(project_sk) ON DELETE CASCADE,
  event_type   TEXT NOT NULL,
  event_date   DATE NOT NULL,
  source_name  TEXT NOT NULL,
  source_url   TEXT,
  UNIQUE (project_sk, event_type, event_date, source_name)
);

CREATE INDEX IF NOT EXISTS project_events_project_sk ON project_events (project_sk);
CREATE INDEX IF NOT EXISTS project_events_type ON project_events (event_type);

COMMIT;
