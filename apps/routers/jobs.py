"""TASK-018: 색인 작업 조회 API.

운영자가 진행/실패 상황을 확인할 수 있도록 read-only API. 인증 미도입 단계라 로컬 LAN 전용.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.dependencies import get_db
from packages.jobs.queue import get_job, list_jobs

router = APIRouter()


class JobItem(BaseModel):
    id: int
    doc_id: Optional[str] = None
    title: str
    source: str = ""
    status: str
    retry_count: int
    error: Optional[str] = None
    enqueued_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class JobListResponse(BaseModel):
    jobs: list[JobItem]
    total: int


def _to_item(job) -> JobItem:
    return JobItem(
        id=job.id,
        doc_id=job.doc_id,
        title=job.title,
        source=job.source or "",
        status=job.status,
        retry_count=job.retry_count or 0,
        error=job.error,
        enqueued_at=job.enqueued_at.isoformat() if job.enqueued_at else "",
        started_at=job.started_at.isoformat() if job.started_at else None,
        finished_at=job.finished_at.isoformat() if job.finished_at else None,
    )


@router.get("/jobs", response_model=JobListResponse)
def list_ingest_jobs(
    status: Optional[str] = Query(None, description="pending|in_progress|done|failed|cancelled"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    rows = list_jobs(db, status=status, limit=limit)
    items = [_to_item(j) for j in rows]
    return JobListResponse(jobs=items, total=len(items))


@router.get("/jobs/{job_id}", response_model=JobItem)
def get_ingest_job(job_id: int, db: Session = Depends(get_db)):
    job = get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"잡을 찾을 수 없음: {job_id}")
    return _to_item(job)
