-- Jurisdiction-scoped reference documents (state DOT standard specifications,
-- owner design standards) and their pages.
--
-- WHY NOT project_document_files: it requires a project_sk. A state DOT spec
-- book governs EVERY state-funded project in that state, including ones not yet
-- ingested. Forcing it into a project row would either duplicate a 2,050-page
-- book thousands of times or attach it arbitrarily to one job.
--
-- WHY PAGES GO IN document_pages RATHER THAN A NEW TABLE: FTS and pgvector
-- already index document_pages. A second page store would be a place nothing
-- reads from -- the exact shape that left 78% of captured documents invisible
-- downstream. One page store, two possible owners.

CREATE TABLE IF NOT EXISTS reference_documents (
    id             bigserial PRIMARY KEY,
    scope          text NOT NULL,
    scope_value    text NOT NULL,
    doc_kind       text NOT NULL,
    title          text,
    url            text NOT NULL UNIQUE,
    gcs_path       text,
    content_sha256 text,
    page_count     int,
    byte_size      bigint,
    text_extracted bool NOT NULL DEFAULT false,
    fetched_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS reference_documents_scope_idx
    ON reference_documents (scope, scope_value);

-- Metadata-only changes: both are instant, no table rewrite.
ALTER TABLE document_pages
    ADD COLUMN IF NOT EXISTS reference_document_id bigint REFERENCES reference_documents(id);

ALTER TABLE document_pages
    ALTER COLUMN document_file_id DROP NOT NULL;

CREATE INDEX IF NOT EXISTS document_pages_reference_idx
    ON document_pages (reference_document_id)
    WHERE reference_document_id IS NOT NULL;

-- Exactly one owner per page. NOT VALID so it applies to new rows immediately
-- without scanning the existing 24k+ pages.
ALTER TABLE document_pages
    DROP CONSTRAINT IF EXISTS document_pages_one_owner;
ALTER TABLE document_pages
    ADD CONSTRAINT document_pages_one_owner CHECK (
        (document_file_id IS NOT NULL AND reference_document_id IS NULL)
     OR (document_file_id IS NULL AND reference_document_id IS NOT NULL)
    ) NOT VALID;
