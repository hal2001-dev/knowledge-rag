-- TASK-020 (ADR-029): Series/묶음 문서 1급 시민 도입.
-- 30챕터처럼 여러 파일로 쪼개진 한 저작을 series로 묶어 도서관·검색·스코프에서 통합.
-- 색인 시점 자동 묶기 + 관리자 검수(Confirm/Detach). rejected 마킹은 동일 휴리스틱의 재바인딩을 차단.

CREATE TABLE IF NOT EXISTS series (
    series_id    TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    description  TEXT,
    cover_doc_id TEXT,
    series_type  TEXT NOT NULL DEFAULT 'book',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT series_type_check CHECK (series_type IN ('book','series','volume'))
);

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS series_id           TEXT REFERENCES series(series_id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS volume_number       INTEGER,
    ADD COLUMN IF NOT EXISTS volume_title        TEXT,
    ADD COLUMN IF NOT EXISTS series_match_status TEXT NOT NULL DEFAULT 'none';

-- enum 제약: 모델 레벨에서도 같은 enum을 강제 (CheckConstraint)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'documents_series_match_status_check'
    ) THEN
        ALTER TABLE documents
            ADD CONSTRAINT documents_series_match_status_check
            CHECK (series_match_status IN ('none','auto_attached','suggested','confirmed','rejected'));
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS ix_documents_series_id        ON documents(series_id);
CREATE INDEX IF NOT EXISTS ix_documents_match_status     ON documents(series_match_status);
