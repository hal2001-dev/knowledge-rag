-- TASK-015 (ADR-025): 카테고리 메타데이터 도입.
-- documents 테이블에 doc_type/category/tags 추가. 모두 idempotent — 재실행 안전.

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS doc_type             VARCHAR(16) NOT NULL DEFAULT 'book',
    ADD COLUMN IF NOT EXISTS category             VARCHAR(64),
    ADD COLUMN IF NOT EXISTS category_confidence  REAL,
    ADD COLUMN IF NOT EXISTS tags                 JSONB DEFAULT '[]'::jsonb;

-- doc_type enum 제약 (이미 존재 시 무시되도록 DO 블록으로 묶음)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'documents_doc_type_check'
    ) THEN
        ALTER TABLE documents
            ADD CONSTRAINT documents_doc_type_check
            CHECK (doc_type IN ('book', 'article', 'paper', 'note', 'report', 'web', 'other'));
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS ix_documents_doc_type  ON documents(doc_type);
CREATE INDEX IF NOT EXISTS ix_documents_category  ON documents(category);
