-- Pipeline contracts (item 1) and a work queue (item 2).
--
-- NAMING: this is pipeline_STAGE_runs, not pipeline_runs. A `pipeline_runs`
-- table already exists and tracks CI WORKFLOW runs (workflow, run_url,
-- projects_before/after, step_outcomes) -- an entirely different thing. The
-- first version of this migration used that name and CREATE TABLE IF NOT
-- EXISTS silently did nothing, so the migration failed on a missing column
-- rather than quietly writing stage records into the CI table. Worth noting:
-- IF NOT EXISTS makes a name collision SILENT, which is why the existing
-- schema must be read before adding a table, not after.
--
-- Both exist because of two failures on 2026-08-05, and both failures were
-- invisible rather than loud.
--
-- FAILURE 1 -- the seam. fetch-sam-gov-documents.py and
-- fetch-accela-documents.py write to GCS and touch the database zero times.
-- extract-document-text.py selects its work FROM project_document_files. So
-- 10,033 objects existed in GCS against 2,240 rows, and ~78% of the corpus was
-- unreachable by every downstream step. Nothing errored. It read as
-- "extraction is slow".
--
--   The rule this encodes: a stage that succeeds into a place nothing reads
--   from must not look the same as a stage that ran. pipeline_stage_runs records
--   rows_in and rows_out per stage, so the gap between what a stage produced
--   and what the next stage could see becomes a queryable number instead of a
--   thing somebody eventually notices.
--
-- FAILURE 2 -- orchestration by shell. A `while pgrep -f "scripts/..."` loop
-- matched the waiting wrapper's OWN argv and stalled steps 8-10 for fifteen
-- hours at 0.01s CPU while appearing to run. Shell chaining has no retry, no
-- idempotency, no visibility.
--
--   work_queue replaces it. Workers claim rows with
--   SELECT ... FOR UPDATE SKIP LOCKED, which is what makes concurrency a
--   CONFIG VALUE rather than a process count -- and means a worker dying
--   mid-item returns that item to the queue instead of losing it silently.
--   No wait loops, so no self-matching pgrep, so no deadlock of this class.
--
-- Idempotent -- safe to re-run.

BEGIN;

-- ---------------------------------------------------------------------------
-- Stage contracts
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pipeline_stage_runs (
  id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  stage          TEXT NOT NULL,        -- 'capture_sam' | 'register' | 'extract_text' | ...
  scope          TEXT,                 -- state code, tenant, county -- whatever the run covered
  started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at    TIMESTAMPTZ,
  rows_in        BIGINT,               -- what this stage was given
  rows_out       BIGINT,               -- what it produced
  -- The contract: what the NEXT stage can actually see. When this trails
  -- rows_out, the seam is leaking -- which is precisely the condition that
  -- went unnoticed for months.
  rows_visible_downstream BIGINT,
  status         TEXT NOT NULL DEFAULT 'running'
    CHECK (status IN ('running', 'ok', 'failed', 'partial')),
  error          TEXT,
  notes          JSONB
);

CREATE INDEX IF NOT EXISTS pipeline_stage_runs_stage ON pipeline_stage_runs (stage, started_at DESC);

COMMENT ON COLUMN pipeline_stage_runs.rows_visible_downstream IS
  'What the NEXT stage can actually see, counted by querying the next stage''s own input. If this is materially below rows_out the seam is leaking -- the exact condition that hid 78% of the document corpus.';

-- The alarm. A stage that produced rows the next stage cannot see is a
-- LEAKING seam, and it should be as visible as an error.
CREATE OR REPLACE VIEW pipeline_seam_health AS
SELECT
  stage,
  scope,
  started_at,
  rows_out,
  rows_visible_downstream,
  rows_out - coalesce(rows_visible_downstream, 0) AS leaked,
  CASE
    WHEN rows_visible_downstream IS NULL THEN 'UNVERIFIED — stage never checked its own seam'
    WHEN rows_out IS NULL OR rows_out = 0 THEN 'no output'
    WHEN rows_visible_downstream >= rows_out THEN 'ok'
    WHEN rows_visible_downstream = 0 THEN 'SEAM BROKEN — next stage sees nothing'
    ELSE 'SEAM LEAKING'
  END AS verdict
FROM pipeline_stage_runs
WHERE status <> 'running'
ORDER BY started_at DESC;

-- ---------------------------------------------------------------------------
-- Work queue
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS work_queue (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  kind          TEXT NOT NULL,        -- 'capture_sam_state' | 'extract_text' | 'spec_book' | ...
  payload       JSONB NOT NULL,       -- everything the worker needs; no hidden state
  -- Lower runs first. Defaults to the document ranking (addenda 1, spec book 2,
  -- MEP 3, drawings 4, other 5) so the moat drains first when capacity is
  -- short -- the queue enforces the same value ordering as the classifier.
  priority      INT NOT NULL DEFAULT 5,
  status        TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'claimed', 'done', 'failed', 'dead')),
  attempts      INT NOT NULL DEFAULT 0,
  max_attempts  INT NOT NULL DEFAULT 3,
  claimed_at    TIMESTAMPTZ,
  claimed_by    TEXT,
  finished_at   TIMESTAMPTZ,
  last_error    TEXT,
  dedupe_key    TEXT,                 -- idempotency: re-enqueueing the same work is a no-op
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Idempotent enqueue. Re-running an enqueue script after a partial failure
-- must not duplicate work -- a partial re-run is the NORMAL case here, not the
-- exception.
CREATE UNIQUE INDEX IF NOT EXISTS work_queue_dedupe
  ON work_queue (kind, dedupe_key)
  WHERE dedupe_key IS NOT NULL AND status <> 'dead';

CREATE INDEX IF NOT EXISTS work_queue_claimable
  ON work_queue (kind, priority, id)
  WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS work_queue_stuck
  ON work_queue (claimed_at)
  WHERE status = 'claimed';

COMMENT ON TABLE work_queue IS
  'Replaces shell-script orchestration. Workers claim with SELECT ... FOR UPDATE SKIP LOCKED, so concurrency is a config value rather than a process count, a dead worker returns its item to the queue, and there are no wait loops to self-match on pgrep.';

-- Requeue anything a dead worker was holding. Called at worker startup:
-- without it, a crashed worker's items stay 'claimed' forever and the queue
-- silently shrinks -- another plausible-looking number instead of an error.
CREATE OR REPLACE FUNCTION requeue_stale_work(stale_minutes INT DEFAULT 60)
RETURNS INT AS $$
DECLARE n INT;
BEGIN
  WITH revived AS (
    UPDATE work_queue
       SET status = CASE WHEN attempts >= max_attempts THEN 'dead' ELSE 'pending' END,
           claimed_at = NULL,
           claimed_by = NULL,
           last_error = coalesce(last_error, '') || ' [requeued: worker vanished]'
     WHERE status = 'claimed'
       AND claimed_at < now() - make_interval(mins => stale_minutes)
     RETURNING 1
  )
  SELECT count(*) INTO n FROM revived;
  RETURN n;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE VIEW work_queue_health AS
SELECT kind, status, count(*) AS items,
       min(created_at) AS oldest,
       count(*) FILTER (WHERE attempts > 0) AS retried
FROM work_queue
GROUP BY kind, status
ORDER BY kind, status;

COMMIT;
