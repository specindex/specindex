-- Step 11 (Phase IV): the substitution ledger -- the moat.
--
-- WHAT THIS RECORDS. Pre-bid substitution requests are ruled on publicly, and
-- the approved and rejected manufacturers are named, with dates, in addenda
-- posted to public bid portals. This is the ONLY public artifact that shows
-- competitive DISPLACEMENT: manufacturer X asked to replace the specified
-- basis-of-design manufacturer Y, and the engineer said yes or no, on a date,
-- on a page. Nobody indexes it.
--
-- WHY IT IS THE MOAT AND NOT JUST ANOTHER TABLE. Three properties together:
--   * it is public, so collecting it is defensible (see the scraping rules --
--     public data only is what keeps this company defensible)
--   * it is NOT retained: addenda come down after award, so a back-file cannot
--     be reconstructed by anyone who starts later. Every week without a
--     crawler is data permanently lost.
--   * it is the fact the channel already pays for. One filed rep agreement
--     pays 25% of commission for finding the opportunity, 50% for WRITING AND
--     SECURING THE SPECIFICATION, 25% for closing. The industry prices the
--     spec step at half the deal and has no system of record for it --
--     Ingen's own OASIS documentation says "there exists no magic method to
--     ensure the agency receives proper credit."
--
-- A RULING IS A CLAIM ABOUT A NAMED THIRD PARTY, so the evidence requirements
-- here are stricter than anywhere else in the schema. "Trane was rejected on
-- this project" is commercially damaging if wrong. Every row therefore
-- REQUIRES a document and a page number: the CHECK below refuses any ruling
-- that cannot point at the page it came from. There is no path to writing an
-- uncited ruling, deliberately -- an uncited ruling is worse than no ruling.
--
-- 'as_noted' is a real third outcome, not a tidy-up: engineers frequently
-- approve a substitution subject to conditions ("approved as noted, provided
-- capacity is verified"). Collapsing it into approved would overstate the
-- substituting manufacturer's win and understate the incumbent's position.
--
-- Idempotent -- safe to re-run.

BEGIN;

CREATE TABLE IF NOT EXISTS substitution_rulings (
  id                     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  project_sk             BIGINT NOT NULL REFERENCES projects(project_sk) ON DELETE CASCADE,

  -- WHO ASKED. Usually the contractor or the substituting manufacturer's rep;
  -- nullable because addenda often rule without naming the requester.
  requesting_party       TEXT,

  -- THE TWO MANUFACTURERS. proposed = who wants in. displaced = the
  -- basis-of-design incumbent they are trying to replace. displaced is
  -- nullable: many addenda approve an added manufacturer without naming who
  -- it competes against, and inferring the incumbent would be a guess about a
  -- named company.
  proposed_manufacturer  TEXT NOT NULL,
  proposed_product       TEXT,
  displaced_manufacturer TEXT,

  ruling                 TEXT NOT NULL
    CHECK (ruling IN ('approved', 'rejected', 'as_noted', 'withdrawn', 'pending')),
  ruling_date            DATE,

  -- WHERE IN THE SPEC. Lets a rep filter to their own division.
  csi_section            TEXT,
  csi_division           TEXT,

  -- THE CITATION. Not optional -- see the CHECK below.
  document_file_id       BIGINT REFERENCES project_document_files(id) ON DELETE SET NULL,
  page_number            INT,
  source_url             TEXT,
  quoted_text            TEXT,

  -- Same three-state discipline as project_enrichment (migration 042):
  -- what the independent verification pass did, kept separate from how much
  -- to trust the value.
  agreement              TEXT CHECK (agreement IN ('agreement', 'disagreement', 'unsupported')),
  confidence             TEXT NOT NULL DEFAULT 'reported'
    CHECK (confidence IN ('confirmed', 'reported', 'unconfirmed')),

  extracted_at           TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- One ruling per (project, proposed manufacturer, section, document). Lets
  -- the extractor be re-run over the same addendum without duplicating rows,
  -- while still allowing the same manufacturer to appear in a later addendum.
  UNIQUE (project_sk, proposed_manufacturer, csi_section, document_file_id)
);

-- The evidence requirement. A ruling names a real company and says it was
-- accepted or refused; that claim must be traceable to a page or it does not
-- get stored.
ALTER TABLE substitution_rulings DROP CONSTRAINT IF EXISTS substitution_rulings_must_cite;
ALTER TABLE substitution_rulings ADD CONSTRAINT substitution_rulings_must_cite CHECK (
  document_file_id IS NOT NULL
  AND page_number IS NOT NULL
  AND page_number > 0
);

CREATE INDEX IF NOT EXISTS substitution_rulings_project    ON substitution_rulings (project_sk);
CREATE INDEX IF NOT EXISTS substitution_rulings_proposed   ON substitution_rulings (lower(proposed_manufacturer));
CREATE INDEX IF NOT EXISTS substitution_rulings_displaced  ON substitution_rulings (lower(displaced_manufacturer))
  WHERE displaced_manufacturer IS NOT NULL;
CREATE INDEX IF NOT EXISTS substitution_rulings_division   ON substitution_rulings (csi_division);
CREATE INDEX IF NOT EXISTS substitution_rulings_date       ON substitution_rulings (ruling_date);

COMMENT ON TABLE substitution_rulings IS
  'Step 11 / Phase IV. Public substitution rulings extracted from addenda and pre-bid Q&A logs. The only public record of competitive displacement between building-product manufacturers. Every row must cite a document page -- an uncited ruling about a named company is worse than no ruling.';
COMMENT ON COLUMN substitution_rulings.ruling IS
  'as_noted is a genuine third outcome (approved subject to conditions), not a variant of approved -- collapsing it would overstate the substituting manufacturer''s win.';
COMMENT ON COLUMN substitution_rulings.displaced_manufacturer IS
  'Nullable on purpose: many addenda approve an added manufacturer without naming the incumbent it competes against, and inferring one would be a guess about a named company.';

-- The sellable view: per manufacturer, how often they get in and who they
-- displace. This is the "am I winning or losing specs, and to whom" question
-- the rep channel has no system of record for.
CREATE OR REPLACE VIEW manufacturer_substitution_summary AS
SELECT
  lower(proposed_manufacturer)                                   AS manufacturer,
  count(*)                                                       AS requests,
  count(*) FILTER (WHERE ruling = 'approved')                    AS approved,
  count(*) FILTER (WHERE ruling = 'rejected')                    AS rejected,
  count(*) FILTER (WHERE ruling = 'as_noted')                    AS approved_as_noted,
  round(100.0 * count(*) FILTER (WHERE ruling IN ('approved', 'as_noted'))
        / nullif(count(*) FILTER (WHERE ruling IN ('approved', 'as_noted', 'rejected')), 0), 1)
                                                                 AS win_rate_pct,
  count(DISTINCT project_sk)                                     AS projects,
  count(DISTINCT lower(displaced_manufacturer))
    FILTER (WHERE displaced_manufacturer IS NOT NULL)            AS distinct_incumbents_challenged,
  min(ruling_date)                                               AS first_seen,
  max(ruling_date)                                               AS last_seen
FROM substitution_rulings
GROUP BY 1;

COMMIT;
