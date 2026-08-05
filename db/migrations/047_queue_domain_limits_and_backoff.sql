-- Per-domain concurrency limits and retry backoff.
--
-- TWO RISKS IDENTIFIED IN REVIEW, both of which the queue as built would have
-- walked straight into.
--
-- RISK 1 -- THUNDERING HERD. work_queue claims strictly by priority. When the
-- scheduler marks 50 SAM.gov states due at once, they all sit at the top of
-- the queue and EVERY worker claims a SAM.gov item simultaneously. The result
-- is N concurrent requests against a single host, which is how a WAF ban
-- happens -- and a ban here is not a slowdown, it is permanent loss of the
-- only source delivering both federal project manuals and amendments.
--
--   Priority ordering and per-host politeness are in direct conflict, and the
--   queue previously honoured only the first. A claim now also respects a
--   per-domain lease cap: if a domain already has max_concurrent items in
--   flight, the claimer SKIPS to the next domain rather than piling on.
--
-- RISK 2 -- POISON PILLS. Items "fail alone and retry", but retried
-- IMMEDIATELY. A permanently-500ing URL therefore burns its full attempt
-- budget in seconds and, in aggregate, keeps workers busy doing nothing.
-- Exponential backoff (next_attempt_at) makes a failing item cheap.
--
-- Idempotent -- safe to re-run.

BEGIN;

ALTER TABLE work_queue
  ADD COLUMN IF NOT EXISTS domain          TEXT,
  -- Retries wait: 2^attempts minutes, so 2, 4, 8, 16... rather than a hot loop.
  ADD COLUMN IF NOT EXISTS next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS work_queue_claimable_v2
  ON work_queue (kind, priority, next_attempt_at, id)
  WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS work_queue_domain_inflight
  ON work_queue (domain)
  WHERE status = 'claimed';

-- Per-domain politeness. Defaults are deliberately conservative: measured
-- uplink saturates around 3 concurrent large transfers (8 produced OSError 65
-- and zero uploads), and government hosts are quicker to ban than to throttle.
CREATE TABLE IF NOT EXISTS domain_limits (
  domain          TEXT PRIMARY KEY,
  max_concurrent  INT NOT NULL DEFAULT 2,
  min_delay_ms    INT NOT NULL DEFAULT 500,
  notes           TEXT
);

INSERT INTO domain_limits (domain, max_concurrent, min_delay_ms, notes) VALUES
  ('api.sam.gov',   2, 1000, 'Federal. Only source giving BOTH project manuals and amendments -- a ban would cost the wedge permanently.'),
  ('sam.gov',       2, 1000, 'same host family as api.sam.gov'),
  ('aca-prod.accela.com', 2, 1000, 'shared Accela tenant host -- many jurisdictions behind ONE hostname, so per-tenant limits would not protect it'),
  ('www.wbdg.org',  1, 2000, 'already serves a 1,359-byte bot-wall stub for HTML; treat as fragile')
ON CONFLICT (domain) DO NOTHING;

COMMENT ON TABLE domain_limits IS
  'Per-domain concurrency caps. Priority ordering and per-host politeness conflict: a priority-only queue sends every worker at whichever host happens to be due. Note aca-prod.accela.com hosts MANY jurisdictions behind one name, so limiting by tenant would not protect the host.';

-- Claim honouring BOTH priority and per-domain leases.
--
-- Scalar subqueries, NOT joins. Postgres refuses "FOR UPDATE cannot be applied
-- to the nullable side of an outer join", so the LEFT JOIN form of this --
-- which reads more naturally -- is simply illegal alongside row locking.
CREATE OR REPLACE FUNCTION claim_work(p_kind TEXT, p_worker TEXT)
RETURNS TABLE (out_id BIGINT, out_payload JSONB, out_attempts INT, out_max_attempts INT) AS $$
BEGIN
  RETURN QUERY
  WITH candidate AS (
    SELECT w.id
    FROM work_queue w
    WHERE w.status = 'pending'
      AND w.kind = p_kind
      AND w.next_attempt_at <= now()
      -- The lease check. A domain already at its cap is SKIPPED, not blocked:
      -- the claimer moves on to the next domain rather than stalling the
      -- worker. NULL domain means unlimited, which is why enqueue() derives
      -- the domain from the payload url.
      AND (
        w.domain IS NULL
        OR (SELECT count(*) FROM work_queue x
             WHERE x.status = 'claimed' AND x.domain = w.domain)
           < coalesce((SELECT dl.max_concurrent FROM domain_limits dl
                        WHERE dl.domain = w.domain), 3)
      )
    ORDER BY w.priority, w.id
    FOR UPDATE SKIP LOCKED
    LIMIT 1
  )
  UPDATE work_queue q
     SET status = 'claimed', claimed_at = now(), claimed_by = p_worker,
         attempts = q.attempts + 1
    FROM candidate c
   WHERE q.id = c.id
  RETURNING q.id, q.payload, q.attempts, q.max_attempts;
END;
$$ LANGUAGE plpgsql;

-- Failure with exponential backoff.
CREATE OR REPLACE FUNCTION fail_work(p_id BIGINT, p_error TEXT)
RETURNS TEXT AS $$
DECLARE v_attempts INT; v_max INT; v_status TEXT;
BEGIN
  SELECT attempts, max_attempts INTO v_attempts, v_max FROM work_queue WHERE id = p_id;
  v_status := CASE WHEN v_attempts >= v_max THEN 'dead' ELSE 'pending' END;
  UPDATE work_queue
     SET status = v_status,
         last_error = left(p_error, 2000),
         claimed_at = NULL, claimed_by = NULL,
         finished_at = CASE WHEN v_status = 'dead' THEN now() ELSE NULL END,
         -- 2^attempts minutes, capped at 6h. A permanently-500ing URL becomes
         -- cheap instead of consuming worker capacity in a hot retry loop.
         next_attempt_at = now() + make_interval(mins => least(360, power(2, v_attempts)::int))
   WHERE id = p_id;
  RETURN v_status;
END;
$$ LANGUAGE plpgsql;

COMMIT;
