-- Aspect C: coverage-conditioned absence -- the three-state assertion model.
--
-- THE PROBLEM THIS FIXES. Today a fact is either a row in
-- project_enrichment or it isn't, and the absence of a row carries two
-- completely different meanings that we sell to the customer identically:
--
--   (a) "we read the Division 23 equipment schedule and no basis-of-design
--        manufacturer is named"                        <- a real, valuable fact
--   (b) "we never obtained a document for this project" <- a gap in our coverage
--
-- (a) is a product. A rep asking "is Trane basis-of-design here?" wants to
-- hear "no -- the schedule names Daikin", not silence. (b) is a hole we are
-- charging for. Collapsing them is the single most misleading thing the
-- schema currently does, and it gets worse as coverage grows, because the
-- ratio of (a) to (b) shifts without anything in the data reflecting it.
--
-- THE MODEL. Every enrichment fact now carries an assertion_status:
--
--   named             -- we have a value           (field_value IS NOT NULL)
--   determined_absent -- we looked and there is none
--   indeterminate     -- we could not look, or looked and could not tell
--
-- Note that 'indeterminate' is the DEFAULT-safe state, not 'determined_absent'.
-- Anything we cannot justify degrades to "we don't know", never to "there
-- isn't one". An absence claim is a strictly stronger statement than a
-- value claim -- it quantifies over an entire document -- so it carries a
-- correspondingly higher burden of proof.
--
-- THE CONSTRAINT IS THE WHOLE POINT. determined_absent REQUIRES a non-empty
-- coverage_ref: machine-checkable pointers to the document pages actually
-- examined. Without this the status would decay into a synonym for "the
-- model didn't return anything", which is exactly the failure this
-- migration exists to prevent -- and that decay would be silent, matching
-- the pattern that has burned this codebase repeatedly (a broken filter
-- returning MORE rows; an expired credential reading as "no documents";
-- a non-ISO date reading as "thin source"). Here the database refuses the
-- write instead. You cannot claim you looked without saying where.
--
-- WHY coverage_ref IS JSONB AND NOT A COMMENT. It has to be re-checkable
-- after the fact. When a customer disputes "no Trane on this project", we
-- must be able to pull up the exact pages that were read and either stand
-- behind the claim or find the page we missed. A prose note cannot be
-- audited; {"document_file_ids": [...], "page_numbers": [...]} can, and
-- can be re-run when a better extractor ships.
--
-- SEPARATELY: agreement. The verification gate (Claim 1) emits
-- agreement / disagreement / unsupported, which is a DIFFERENT axis from
-- confidence. confidence answers "how much should you trust this value";
-- agreement records "what did the independent second pass actually do".
-- They are correlated but not derivable from one another -- in particular
-- 'unsupported' (pass 2 found nothing) and 'disagreement' (pass 2 found a
-- conflicting value) both currently collapse into confidence='unconfirmed'
-- and 'reported', losing the distinction that matters most when auditing
-- whether the gate is earning its second API call.
--
-- Idempotent -- safe to re-run.

BEGIN;

ALTER TABLE project_enrichment
  ADD COLUMN IF NOT EXISTS assertion_status TEXT NOT NULL DEFAULT 'named'
    CHECK (assertion_status IN ('named', 'determined_absent', 'indeterminate')),
  ADD COLUMN IF NOT EXISTS coverage_basis TEXT,
  ADD COLUMN IF NOT EXISTS coverage_ref JSONB,
  ADD COLUMN IF NOT EXISTS agreement TEXT
    CHECK (agreement IN ('agreement', 'disagreement', 'unsupported'));

-- field_value must become nullable: a determined_absent fact has no value
-- by definition, and forcing a sentinel string like 'NONE' into a NOT NULL
-- column is how you end up with 'NONE' rendered to a customer as a
-- manufacturer name.
ALTER TABLE project_enrichment ALTER COLUMN field_value DROP NOT NULL;

-- The invariant. Written as one constraint so the three states are
-- defined in a single readable place rather than scattered.
ALTER TABLE project_enrichment DROP CONSTRAINT IF EXISTS project_enrichment_assertion_coherent;
ALTER TABLE project_enrichment ADD CONSTRAINT project_enrichment_assertion_coherent CHECK (
      (assertion_status = 'named'
         AND field_value IS NOT NULL AND length(btrim(field_value)) > 0)
   OR (assertion_status = 'determined_absent'
         AND coverage_ref IS NOT NULL
         AND jsonb_typeof(coverage_ref) = 'object'
         AND coverage_ref <> '{}'::jsonb)
   OR (assertion_status = 'indeterminate')
);

CREATE INDEX IF NOT EXISTS project_enrichment_assertion_status
  ON project_enrichment (assertion_status)
  WHERE assertion_status <> 'named';

COMMENT ON COLUMN project_enrichment.assertion_status IS
  'named = we have a value; determined_absent = we read the relevant document region and no value is present (requires coverage_ref); indeterminate = we could not determine. Absence of a row is NOT equivalent to any of these -- it means the field was never considered.';
COMMENT ON COLUMN project_enrichment.coverage_ref IS
  'Machine-checkable proof of what was examined, e.g. {"document_file_ids":[123],"page_numbers":[44,45],"method":"div23_schedule_scan"}. Required for determined_absent so the claim can be re-audited or re-run against a better extractor.';
COMMENT ON COLUMN project_enrichment.agreement IS
  'What the independent verification pass did: agreement / disagreement / unsupported. Distinct from confidence -- unsupported (found nothing) and disagreement (found a conflict) are very different signals that both flatten into low confidence.';

-- Coverage reporting. This is what turns the model into something
-- sellable: per section+field, how much of the answer is a real assertion
-- versus an admitted gap. Deliberately a view, not a materialized table --
-- it must never drift from the underlying rows.
CREATE OR REPLACE VIEW enrichment_coverage AS
SELECT
  section,
  field_key,
  count(*)                                                        AS total,
  count(*) FILTER (WHERE assertion_status = 'named')              AS named,
  count(*) FILTER (WHERE assertion_status = 'determined_absent')  AS determined_absent,
  count(*) FILTER (WHERE assertion_status = 'indeterminate')      AS indeterminate,
  -- The honest headline number: the share of facts on which we can make
  -- ANY defensible statement, absence included. Reporting only 'named'
  -- understates the product; reporting named+indeterminate overstates it.
  round(
    100.0 * count(*) FILTER (WHERE assertion_status IN ('named', 'determined_absent'))
    / nullif(count(*), 0)
  , 1)                                                            AS answerable_pct
FROM project_enrichment
GROUP BY section, field_key;

COMMIT;
