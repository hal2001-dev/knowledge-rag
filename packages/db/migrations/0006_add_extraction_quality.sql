-- ISSUE-010 (후속 합의 시 ADR-032): 스캔본 PDF 등 텍스트 추출 누락 문서 식별.
-- NULL = 미평가/legacy(기본 ok 취급), 'ok' = 정상, 'partial' = 부분 추출(경계),
-- 'scan_only' = 본문 추출 사실상 0(목차·판권만). 도서관·검색에서 배지/안내 노출용.

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS extraction_quality TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'documents_extraction_quality_check'
    ) THEN
        ALTER TABLE documents
            ADD CONSTRAINT documents_extraction_quality_check
            CHECK (extraction_quality IS NULL OR extraction_quality IN ('ok','partial','scan_only'));
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS ix_documents_extraction_quality ON documents(extraction_quality);
