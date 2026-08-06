-- Let classifier output attach to a JURISDICTION document, not only a project.
--
-- THE BLOCKER. project_csi_divisions.project_sk is NOT NULL, but a state DOT
-- standard specification governs EVERY project in that state and has no
-- project_sk. So 18,144 pages of extracted DOT spec text -- the densest
-- basis-of-design material in the corpus -- could not be classified into this
-- table at all. Same for the 2,242 Legistar documents.
--
-- Same three-owner shape already working in document_pages since migration 052.

ALTER TABLE project_csi_divisions ALTER COLUMN project_sk DROP NOT NULL;

ALTER TABLE project_csi_divisions
    ADD COLUMN IF NOT EXISTS reference_document_id bigint REFERENCES reference_documents(id),
    ADD COLUMN IF NOT EXISTS legislative_document_id bigint REFERENCES legislative_documents(id);

-- The plan asks for "divisions present, with page ranges". `page` stays as the
-- first-occurrence anchor so the existing unique constraint and every existing
-- query keep working.
ALTER TABLE project_csi_divisions
    ADD COLUMN IF NOT EXISTS page_from int,
    ADD COLUMN IF NOT EXISTS page_to   int;

-- Openness as an enumerable signal rather than free text. substitution_language
-- keeps the verbatim quote -- the citation is the product -- while this makes
-- "how open is this spec" a query instead of a regex over prose.
ALTER TABLE project_csi_divisions
    ADD COLUMN IF NOT EXISTS openness text
        CHECK (openness IN ('proprietary','or-equal','performance','unspecified'));

-- Exactly one owner. NOT VALID so it binds new rows immediately without
-- scanning; the table is empty today, but that will not stay true.
ALTER TABLE project_csi_divisions DROP CONSTRAINT IF EXISTS csi_divisions_one_owner;
ALTER TABLE project_csi_divisions ADD CONSTRAINT csi_divisions_one_owner CHECK (
    (project_sk IS NOT NULL)::int
  + (reference_document_id IS NOT NULL)::int
  + (legislative_document_id IS NOT NULL)::int = 1) NOT VALID;

CREATE INDEX IF NOT EXISTS csi_divisions_reference_idx
    ON project_csi_divisions (reference_document_id) WHERE reference_document_id IS NOT NULL;

-- doc_type / spec_format belong on the DOCUMENT, not per-division. Without them
-- the funnel metric "% of documented projects with a confirmed spec doc" cannot
-- be computed at all -- the A3 runner already derives both and was writing them
-- only to a CSV.
ALTER TABLE project_document_files
    ADD COLUMN IF NOT EXISTS doc_type text,
    ADD COLUMN IF NOT EXISTS spec_format text;
ALTER TABLE reference_documents
    ADD COLUMN IF NOT EXISTS doc_type text,
    ADD COLUMN IF NOT EXISTS spec_format text;

-- The status flag meant "some extractor touched this", which is why 269
-- documents read as done while the divisions table was empty. Split it: this
-- column means DIVISIONS WERE WRITTEN, and nothing else may set it.
ALTER TABLE document_processing_status
    ADD COLUMN IF NOT EXISTS divisions_written_at timestamptz;

COMMENT ON COLUMN document_processing_status.structured_extraction_at IS
  'Set by extract-spec-positions.py when substitution rulings were extracted. Does NOT mean CSI divisions exist -- see divisions_written_at.';
COMMENT ON COLUMN document_processing_status.divisions_written_at IS
  'Set ONLY by classify-spec-documents.py after rows land in project_csi_divisions.';
