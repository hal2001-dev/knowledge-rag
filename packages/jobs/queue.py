"""TASK-018 (ADR-028): Postgres 기반 색인 작업 큐.

FastAPI는 `enqueue_job()`만 호출 후 즉시 응답.
indexer 워커는 `claim_next_job()`로 `FOR UPDATE SKIP LOCKED` 락을 걸어 동시 워커도 안전.
완료/실패는 `mark_done()`/`mark_failed()`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from packages.db.models import IngestJobRecord


def enqueue_job(
    db: Session,
    *,
    doc_id: str,
    file_path: str,
    title: str,
    source: str = "",
    content_hash: Optional[str] = None,
    user_doc_type: Optional[str] = None,
    user_category: Optional[str] = None,
    user_tags: Optional[list[str]] = None,
) -> IngestJobRecord:
    job = IngestJobRecord(
        doc_id=doc_id,
        file_path=file_path,
        title=title,
        source=source or "",
        content_hash=content_hash,
        user_doc_type=user_doc_type,
        user_category=user_category,
        user_tags=user_tags,
        status="pending",
        retry_count=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def claim_next_job(db: Session) -> Optional[IngestJobRecord]:
    """SKIP LOCKED로 가장 오래된 pending 잡 1개를 in_progress로 전환.

    동시 워커가 여러 개 떠도 같은 잡을 두 번 처리하지 않는다.
    트랜잭션 commit 후 워커는 잡을 가지고 본 처리 진입.
    """
    raw_sql = text(
        """
        UPDATE ingest_jobs
        SET    status = 'in_progress',
               started_at = NOW()
        WHERE  id = (
            SELECT id FROM ingest_jobs
            WHERE  status = 'pending'
            ORDER  BY enqueued_at
            FOR UPDATE SKIP LOCKED
            LIMIT 1
        )
        RETURNING id
        """
    )
    row = db.execute(raw_sql).first()
    db.commit()
    if row is None:
        return None
    return db.query(IngestJobRecord).filter(IngestJobRecord.id == row.id).first()


def mark_done(db: Session, job_id: int, doc_id: Optional[str] = None) -> None:
    job = db.query(IngestJobRecord).filter(IngestJobRecord.id == job_id).first()
    if job is None:
        return
    job.status = "done"
    if doc_id is not None:
        job.doc_id = doc_id
    job.finished_at = datetime.now(timezone.utc)
    job.error = None
    db.commit()


def mark_failed(db: Session, job_id: int, error: str, retry: bool = False) -> None:
    job = db.query(IngestJobRecord).filter(IngestJobRecord.id == job_id).first()
    if job is None:
        return
    if retry:
        # 재시도 — pending으로 되돌리고 retry 카운트만 증가
        job.status = "pending"
        job.started_at = None
    else:
        job.status = "failed"
        job.finished_at = datetime.now(timezone.utc)
    job.retry_count = (job.retry_count or 0) + 1
    job.error = error[:2000]  # 상한
    db.commit()


def get_job(db: Session, job_id: int) -> Optional[IngestJobRecord]:
    return db.query(IngestJobRecord).filter(IngestJobRecord.id == job_id).first()


def list_jobs(
    db: Session,
    status: Optional[str] = None,
    limit: int = 50,
) -> list[IngestJobRecord]:
    q = db.query(IngestJobRecord)
    if status:
        q = q.filter(IngestJobRecord.status == status)
    return q.order_by(IngestJobRecord.enqueued_at.desc()).limit(limit).all()
