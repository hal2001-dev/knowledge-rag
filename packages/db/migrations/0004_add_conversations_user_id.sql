-- TASK-019 (ADR-030): conversations 사용자 격리.
-- NextJS는 Clerk JWT의 user_id, Streamlit/로컬 호출은 미들웨어가 'admin' 자동 부여.
-- 기존 행은 DEFAULT 'admin'으로 일괄 백필 (Streamlit 흔적이 모두 admin으로 귀속).

ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'admin';

CREATE INDEX IF NOT EXISTS ix_conversations_user_id
    ON conversations(user_id);
