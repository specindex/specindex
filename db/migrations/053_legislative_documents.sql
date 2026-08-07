-- Documents attached to legislative "matters" (Legistar/Granicus).
--
-- WHY A SEPARATE TABLE FROM project_document_files: a matter is not a project.
-- NYC land-use matters are keyed by address and block/lot -- "310 East 4th
-- Street, Block 373, Lot 8, Manhattan" -- and matching those to permit records
-- is a real join with real failure modes. Capture must NOT wait on that match:
-- a document held with no project attached is an asset, while a document never
-- fetched is gone once the jurisdiction rotates its site. Matching is a
-- separate, re-runnable step that promotes rows into project_document_files.

CREATE TABLE IF NOT EXISTS legislative_documents (
    id              bigserial PRIMARY KEY,
    jurisdiction    text NOT NULL,           -- legistar client slug, e.g. 'nyc'
    matter_id       bigint,
    matter_title    text,                    -- carries the address for matching
    matter_date     date,
    attachment_name text,
    url             text NOT NULL UNIQUE,
    gcs_path        text,
    content_sha256  text,
    byte_size       bigint,
    project_sk      bigint,                  -- set later by the matcher; NULL until then
    fetched_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS legislative_documents_juris_idx
    ON legislative_documents (jurisdiction);
CREATE INDEX IF NOT EXISTS legislative_documents_unmatched_idx
    ON legislative_documents (jurisdiction) WHERE project_sk IS NULL;
-- Address matching runs over matter_title; trigram makes that survivable.
CREATE INDEX IF NOT EXISTS legislative_documents_title_trgm
    ON legislative_documents USING gin (matter_title gin_trgm_ops);
