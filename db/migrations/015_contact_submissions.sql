-- Real storage for the homepage demo-request form (components/marketing/
-- DemoSection.tsx), replacing the previous mailto:/optional-Google-Sheet-
-- webhook approach -- a submission now durably lands here even if the
-- visitor's email client isn't configured or the webhook was never set up
-- (see docs/ROADMAP.md, "setup a real form" ask, 2026-07-26).
--
-- Idempotent -- safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS contact_submissions (
  id              BIGSERIAL PRIMARY KEY,
  first_name      TEXT NOT NULL,
  last_name       TEXT NOT NULL,
  email           TEXT NOT NULL,
  company         TEXT NOT NULL,
  categories      TEXT NOT NULL DEFAULT '',
  source_path     TEXT NOT NULL DEFAULT '',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  notified_at     TIMESTAMPTZ,
  notify_error    TEXT
);

CREATE INDEX IF NOT EXISTS contact_submissions_created_at ON contact_submissions (created_at DESC);

COMMIT;
