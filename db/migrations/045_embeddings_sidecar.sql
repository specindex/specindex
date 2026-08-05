-- Move embeddings OFF document_pages into a 1:1 sidecar, before they exist.
--
-- MEASURED, not assumed (2026-08-05, live instance):
--   document_pages          24,167 rows,  60 MB total,  2,612 bytes/page
--   GIN FTS on raw_text                    17 MB,         723 bytes/page
--   embedding vector(768)   0 populated,             ~3,100 bytes/page
--   shared_buffers                       2,481 MB
--   maintenance_work_mem                     64 MB
--
-- PROJECTED AT 1M PAGES (the corpus is heading there: ~28,000 documents from
-- the 50-state SAM.gov pull, and 24,167 pages came from just 405 documents,
-- so ~60 pages/document puts a full corpus near 1.7M pages):
--   document_pages heap        ~2.6 GB
--   GIN FTS index              ~0.7 GB
--   HNSW on vector(768)     ~1.5-2.0 GB
--   -> indexes alone ~2.2-2.7 GB against 2,481 MB of shared_buffers.
--
-- Once the working set exceeds cache, vector search degrades to disk
-- thrashing. That is a cliff, not a slope, and it arrives without warning.
--
-- WHY A SIDECAR RATHER THAN A COLUMN:
--   * A 3.1 KB vector on every row bloats the heap and slows EVERY
--     non-vector query, including the FTS path that works well today.
--     Sequential scans over document_pages would carry the vector payload
--     whether or not the query wants it.
--   * The vector index can be rebuilt, re-tuned, or swapped (IVFFlat <-> HNSW)
--     without locking page text -- and it WILL need retuning, because nobody
--     picks HNSW parameters correctly the first time.
--   * Embeddings are regenerable derived data; page text is the expensive
--     artifact. They have different durability requirements and should not
--     share a lifecycle. Re-embedding on a model change becomes TRUNCATE +
--     refill instead of a rewrite of the whole table.
--
-- The existing document_pages.embedding column is intentionally NOT dropped
-- here: it holds zero rows, so nothing is lost by leaving it, and dropping a
-- column while extraction jobs are actively running invites an avoidable
-- failure. Drop it in a later migration once no code references it.
--
-- Idempotent -- safe to re-run.

BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS document_page_embeddings (
  document_page_id BIGINT PRIMARY KEY
                   REFERENCES document_pages(id) ON DELETE CASCADE,
  embedding        vector(768) NOT NULL,
  -- Which model produced this. Without it, a model upgrade silently mixes
  -- incompatible vector spaces in one index and similarity scores become
  -- meaningless -- a failure that returns plausible-looking neighbours rather
  -- than an error, which is the worst kind here.
  model            TEXT NOT NULL,
  embedded_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS document_page_embeddings_model
  ON document_page_embeddings (model);

-- NO vector index yet, deliberately. HNSW build cost and quality both depend
-- on the data being present: building on an empty or tiny table produces a
-- structure that must be rebuilt anyway. Create it after the first bulk
-- embedding pass, and raise maintenance_work_mem for that session --
-- 64 MB is the CURRENT setting and is far too low for a 1M-row HNSW build:
--
--   SET maintenance_work_mem = '2GB';
--   CREATE INDEX CONCURRENTLY document_page_embeddings_hnsw
--     ON document_page_embeddings USING hnsw (embedding vector_cosine_ops);
--
-- maintenance_work_mem -- NOT work_mem -- governs GIN and HNSW index
-- construction. Tuning work_mem for this is a common and costly mistake.

COMMENT ON TABLE document_page_embeddings IS
  'Sidecar for page embeddings, kept off document_pages so a 3.1 KB/row vector does not bloat the heap or slow the FTS path, and so the vector index can be rebuilt or retuned without locking page text. Measured projection: at 1M pages GIN (0.7 GB) + HNSW (1.5-2.0 GB) would exceed shared_buffers (2.4 GB).';

-- Convenience join so callers never hand-write the 1:1 and accidentally use
-- an INNER join, which would silently hide every page that has text but no
-- embedding yet -- during a backfill that is most of them.
CREATE OR REPLACE VIEW document_pages_with_embedding AS
SELECT p.id, p.document_file_id, p.page_number, p.raw_text, p.ocr_engine,
       e.embedding, e.model AS embedding_model
FROM document_pages p
LEFT JOIN document_page_embeddings e ON e.document_page_id = p.id;

COMMIT;
