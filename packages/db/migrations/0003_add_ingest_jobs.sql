-- TASK-018 (ADR-028): 색인 작업 큐 테이블.
-- FastAPI는 파일 저장 + enqueue + 202만 처리, 별도 indexer 워커가 SKIP LOCKED로 claim 후 인덱싱.

CREATE TABLE IF NOT EXISTS ingest_jobs (
    id              BIGSERIAL PRIMARY KEY,
    doc_id          TEXT,                              -- 사전 발급된 doc_id (워커가 사용)
    file_path       TEXT NOT NULL,                     -- data/uploads/{doc_id}{ext} 절대/상대 경로
    title           TEXT NOT NULL,
    source          TEXT NOT NULL DEFAULT '',
    content_hash    VARCHAR(64),                       -- L1 중복 감지용. unique 제약 X (failed→retry 흐름)
    -- 사용자 명시 분류값 (워커가 인덱싱 후 적용)
    user_doc_type   VARCHAR(16),
    user_category   VARCHAR(64),
    user_tags       JSONB,
    -- 잡 상태 머신
    status          VARCHAR(16) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','in_progress','done','failed','cancelled')),
    retry_count     INTEGER NOT NULL DEFAULT 0,
    error           TEXT,
    -- 타임스탬프
    enqueued_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_ingest_jobs_status_enqueued
    ON ingest_jobs(status, enqueued_at);
CREATE INDEX IF NOT EXISTS ix_ingest_jobs_doc_id
    ON ingest_jobs(doc_id);
