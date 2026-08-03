-- Widen document_pages.ocr_engine to cover the full three-tier OCR cascade.
--
-- The original constraint allowed only 'native' and 'document_ai', written
-- before PaddleOCR was added as tier 2 (2026-08-03). That made the new tier
-- unusable: any page PaddleOCR successfully read would violate the check and
-- abort the whole transaction, so tier 2 could never have written a row even
-- once its own API-compatibility bug was fixed.
--
-- 'skipped_no_docai' records a page that had no native text layer, was not
-- rescued by PaddleOCR, and could not escalate because Document AI is not
-- configured. Recorded explicitly rather than dropped so those pages remain
-- findable for a re-run -- silently omitting them would make a document look
-- fully extracted when it is not.
ALTER TABLE document_pages DROP CONSTRAINT IF EXISTS document_pages_ocr_engine_check;
ALTER TABLE document_pages ADD CONSTRAINT document_pages_ocr_engine_check
    CHECK (ocr_engine = ANY (ARRAY[
        'native'::text,
        'paddleocr'::text,
        'document_ai'::text,
        'skipped_no_docai'::text
    ]));
