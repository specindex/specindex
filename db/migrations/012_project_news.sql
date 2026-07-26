-- Related news articles per project, for the "Related news" citations
-- section on the project detail page. Populated by
-- scripts/enrich-news.py from Google News RSS, filtered for relevance
-- (see that script -- raw name-only search returns real false positives,
-- e.g. searching a generic project name like "Linden Village" surfaced
-- obituaries alongside one real construction article).
--
-- Idempotent — safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS project_news (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  project_sk    BIGINT NOT NULL REFERENCES projects(project_sk) ON DELETE CASCADE,
  title         TEXT NOT NULL,
  url           TEXT NOT NULL,
  source_name   TEXT,
  published_at  TIMESTAMPTZ,
  fetched_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (project_sk, url)
);

CREATE INDEX IF NOT EXISTS project_news_project_sk ON project_news (project_sk);

-- Tracks the last time a project was *checked* for news, independent of
-- whether anything relevant was found -- keeps the 30-day recheck cooldown
-- without polluting project_news (which holds only real articles) with
-- sentinel/marker rows for zero-result checks.
CREATE TABLE IF NOT EXISTS project_news_checks (
  project_sk  BIGINT PRIMARY KEY REFERENCES projects(project_sk) ON DELETE CASCADE,
  checked_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;
