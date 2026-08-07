-- Move page ownership for portal spec books from reference_documents to the
-- project document row.
--
-- THE DEFECT. A portal spec book was registered TWICE under one URL: once into
-- reference_documents (by the registration script, which extracted its text) and
-- once into project_document_files (by the portal loader, which attached it to a
-- project). document_pages hung off the reference row, and document_pages_one_owner
-- permits only one owner -- so every join from a project to its own spec book text
-- returned zero pages. 207 of 207 spec books, including Maine 3820's 219 pages.
--
-- This is the same shape as the seam migration 056 fixed for divisions, and the
-- same shape as the capture-never-wrote-to-DB incident: a step succeeded into a
-- place nothing downstream reads from, so it was indistinguishable from a step
-- that never ran. Text extraction had genuinely run; the record page could not
-- see a word of it.
--
-- SCOPE IS DELIBERATELY NARROW. Only pages whose reference_document has an
-- identical-URL twin in project_document_files move. A state DOT standard
-- specification governs every project in the state, belongs to no single one, and
-- has no project twin -- those rows are untouched and keep their pages.
--
-- The reference_documents rows are RETAINED, not deleted: migration 056 pointed
-- project_csi_divisions.source_document_id at them, and dropping them would
-- produce uncited manufacturer claims.

BEGIN;

CREATE TEMP TABLE _dup_specbooks ON COMMIT DROP AS
SELECT r.id AS ref_id, f.id AS file_id
FROM reference_documents r
JOIN project_document_files f ON f.url = r.url;

UPDATE document_pages dp
   SET document_file_id      = d.file_id,
       reference_document_id = NULL
  FROM _dup_specbooks d
 WHERE dp.reference_document_id = d.ref_id;

-- Backfill the identity fields the portal loader never wrote, so the project row
-- can be deduped on content like every other captured document.
UPDATE project_document_files f
   SET content_sha256 = COALESCE(f.content_sha256, r.content_sha256)
  FROM reference_documents r
 WHERE r.url = f.url AND f.content_sha256 IS NULL;

COMMIT;
