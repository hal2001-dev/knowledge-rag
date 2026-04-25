-- TASK-014 (ADR-024): 문서 요약 컬럼 도입.
-- 기존 documents 테이블이 있는 환경에서 summary 관련 3개 컬럼을 추가한다.
-- 각 ALTER 는 IF NOT EXISTS 라 재실행해도 안전하다.

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS summary              JSONB,
    ADD COLUMN IF NOT EXISTS summary_model        TEXT,
    ADD COLUMN IF NOT EXISTS summary_generated_at TIMESTAMPTZ;
