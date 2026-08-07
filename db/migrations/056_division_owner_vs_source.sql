-- A division has ONE owner and may also cite the document it was read from.
--
-- Migration 055 modelled project_sk / reference_document_id /
-- legislative_document_id as three mutually exclusive OWNERS. That was right
-- when a division could only hang off one of them. It is wrong now: a division
-- extracted FROM a spec book and belonging TO a project needs both -- the
-- project so the record page can show it, and the document so the claim keeps
-- its citation.
--
-- Dropping the citation to satisfy the constraint would have been the worst
-- possible fix: an uncited manufacturer claim is exactly what the compliance
-- brief forbids and what the product promises never to make.
--
-- So: exactly one OWNER (project | reference | legislative), and
-- source_document_id as an independent provenance pointer.

ALTER TABLE project_csi_divisions
    ADD COLUMN IF NOT EXISTS source_document_id bigint REFERENCES reference_documents(id);

-- Preserve existing provenance before the owner semantics change.
UPDATE project_csi_divisions
   SET source_document_id = reference_document_id
 WHERE reference_document_id IS NOT NULL
   AND source_document_id IS NULL;

ALTER TABLE project_csi_divisions DROP CONSTRAINT IF EXISTS csi_divisions_one_owner;
ALTER TABLE project_csi_divisions ADD CONSTRAINT csi_divisions_one_owner CHECK (
    (project_sk IS NOT NULL)::int
  + (reference_document_id IS NOT NULL)::int
  + (legislative_document_id IS NOT NULL)::int = 1) NOT VALID;

CREATE INDEX IF NOT EXISTS csi_divisions_source_doc_idx
    ON project_csi_divisions (source_document_id) WHERE source_document_id IS NOT NULL;

COMMENT ON COLUMN project_csi_divisions.source_document_id IS
  'The document this division was extracted from. Provenance, not ownership -- survives when the row is attached to a project.';
