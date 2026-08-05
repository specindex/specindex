-- Continuous crawling: a source registry with volatility-driven cadence.
--
-- WHY THIS EXISTS. Today every pull is a human running a script against a
-- hand-picked list. That cannot hold the moat, because the moat is
-- TIME-SENSITIVE in a way nothing else in the corpus is: substitution rulings
-- appear in addenda on open solicitations and are REMOVED after award. A
-- source polled monthly loses most of them. A source polled daily while the
-- solicitation is open catches nearly all.
--
-- So cadence is not a global setting -- it is a property of the source, and
-- specifically of how fast that source changes and how quickly its content
-- disappears. Three tiers:
--
--   hot     open solicitations with addenda   -- daily. Content vanishes.
--   warm    permit feeds, award feeds         -- weekly. Content accumulates.
--   cold    owner design standards, UFGS/VA   -- monthly. Content is stable
--                                                and permanent; re-crawling
--                                                often is pure waste.
--
-- WHAT IT ALSO FIXES. A SAM.gov state run died on a single GCS upload
-- timeout (RetryError, 120s write timeout, uplink saturated) and took the
-- ENTIRE remaining state with it -- 163 opportunities abandoned because one
-- file stalled. There was no per-item isolation and no resume. Work items now
-- live in work_queue at document granularity, so one timeout fails one item,
-- gets retried, and the run continues.
--
-- Idempotent -- safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS source_registry (
  id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  source_key        TEXT NOT NULL UNIQUE,   -- 'sam:nc', 'accela:FL-PINELLAS', 'owner:uw'
  kind              TEXT NOT NULL,          -- sam | accela | energov | arcgis | socrata | owner_standards | bid_portal
  label             TEXT,
  state             TEXT,
  county            TEXT,
  url               TEXT,
  config            JSONB,                  -- everything the worker needs

  -- Cadence. volatility drives cadence_hours; cadence_hours drives next_due_at.
  volatility        TEXT NOT NULL DEFAULT 'warm'
    CHECK (volatility IN ('hot', 'warm', 'cold', 'frozen')),
  cadence_hours     INT  NOT NULL DEFAULT 168,   -- 24 hot / 168 warm / 720 cold
  next_due_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_crawled_at   TIMESTAMPTZ,
  last_changed_at   TIMESTAMPTZ,            -- last time the crawl found anything NEW

  -- Health. A source that stops yielding is not automatically dead -- but a
  -- source that errors repeatedly should stop being retried at full rate.
  consecutive_failures INT NOT NULL DEFAULT 0,
  consecutive_empty    INT NOT NULL DEFAULT 0,
  status            TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'backoff', 'paused', 'dead')),
  last_error        TEXT,
  notes             TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS source_registry_due
  ON source_registry (next_due_at)
  WHERE status = 'active';
CREATE INDEX IF NOT EXISTS source_registry_kind ON source_registry (kind, status);

COMMENT ON COLUMN source_registry.volatility IS
  'hot = content DISAPPEARS (open solicitations with addenda) -> poll daily. warm = content accumulates (permit/award feeds) -> weekly. cold = stable, permanent (owner standards, UFGS, VA masters) -> monthly. frozen = never re-crawl.';
COMMENT ON COLUMN source_registry.last_changed_at IS
  'Distinct from last_crawled_at on purpose. A source crawled daily that has not CHANGED in 90 days is a candidate for slower cadence; one that changes every crawl may deserve a faster one. Crawling frequency should follow observed change, not a guess made once.';

-- Per-attempt history. Without it, "is this source still healthy" is
-- unanswerable, and a source that silently went to zero looks identical to a
-- source that was always empty -- the Harris ArcGIS failure mode, where a dead
-- layer kept answering queries and returned 0 rows for everything.
CREATE TABLE IF NOT EXISTS crawl_history (
  id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  source_id      BIGINT NOT NULL REFERENCES source_registry(id) ON DELETE CASCADE,
  started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at    TIMESTAMPTZ,
  items_seen     INT,        -- how many records/documents the source offered
  items_new      INT,        -- how many were not already held
  items_changed  INT,        -- how many had a different content hash
  bytes_fetched  BIGINT,
  status         TEXT NOT NULL DEFAULT 'running'
    CHECK (status IN ('running', 'ok', 'empty', 'failed')),
  error          TEXT
);

CREATE INDEX IF NOT EXISTS crawl_history_source ON crawl_history (source_id, started_at DESC);

-- Cheap change detection so a re-crawl of an unchanged source costs almost
-- nothing. content_sha256 already exists on project_document_files; these add
-- the HTTP-level short-circuit, which avoids downloading the bytes at all.
ALTER TABLE project_document_files
  ADD COLUMN IF NOT EXISTS etag           TEXT,
  ADD COLUMN IF NOT EXISTS last_modified  TEXT,
  ADD COLUMN IF NOT EXISTS last_seen_at   TIMESTAMPTZ,
  -- When a document DISAPPEARS from its source. Critical for the moat:
  -- addenda are removed after award, and the fact that we hold one the
  -- source no longer serves is itself the defensible asset. Never delete
  -- these rows -- mark them.
  ADD COLUMN IF NOT EXISTS vanished_at    TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS project_document_files_vanished
  ON project_document_files (vanished_at)
  WHERE vanished_at IS NOT NULL;

COMMENT ON COLUMN project_document_files.vanished_at IS
  'Set when a document we hold is no longer served by its source. Do NOT delete the row: an addendum that has been taken down after award is exactly the back-file nobody starting later can reconstruct. This column is the moat made queryable.';

-- Adjust cadence from observed behaviour rather than from the guess made when
-- the source was registered.
CREATE OR REPLACE FUNCTION retune_source_cadence()
RETURNS INT AS $$
DECLARE n INT := 0;
BEGIN
  -- Changing on most crawls and not already hot -> speed up.
  UPDATE source_registry s SET cadence_hours = greatest(24, cadence_hours / 2)
   WHERE s.status = 'active'
     AND s.last_changed_at IS NOT NULL
     AND s.last_crawled_at IS NOT NULL
     AND s.last_changed_at > now() - make_interval(hours => s.cadence_hours);
  GET DIAGNOSTICS n = ROW_COUNT;

  -- Nothing new in 90 days -> slow down, capped at monthly. Saves request
  -- budget for sources that actually move, and reduces the ban risk that
  -- comes from hammering a static source.
  UPDATE source_registry s SET cadence_hours = least(720, cadence_hours * 2)
   WHERE s.status = 'active'
     AND (s.last_changed_at IS NULL OR s.last_changed_at < now() - interval '90 days')
     AND s.last_crawled_at IS NOT NULL;
  RETURN n;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE VIEW source_health AS
SELECT
  s.source_key, s.kind, s.state, s.volatility, s.cadence_hours, s.status,
  s.last_crawled_at, s.last_changed_at, s.consecutive_failures, s.consecutive_empty,
  CASE
    WHEN s.status <> 'active'                                   THEN s.status
    WHEN s.last_crawled_at IS NULL                              THEN 'never crawled'
    WHEN s.consecutive_failures >= 3                            THEN 'FAILING'
    -- A source that used to yield and now yields nothing is the dangerous
    -- case: it reads as "no new data" when it may be a dead endpoint.
    WHEN s.consecutive_empty >= 5 AND s.last_changed_at IS NOT NULL THEN 'WENT QUIET — verify endpoint is alive'
    WHEN s.next_due_at < now() - interval '2 days'              THEN 'OVERDUE'
    ELSE 'ok'
  END AS verdict
FROM source_registry s;

COMMIT;
