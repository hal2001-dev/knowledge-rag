"""TASK-020 (ADR-029): 시리즈 1급 시민 라우터.

CRUD + 멤버 목록 + 매치 검수(confirm/reject). Streamlit 동결 정책에 따라
사용자 측은 read-only(/series, /series/{id}, /series/{id}/members)이고
쓰기·검수 엔드포인트는 관리자 LAN/admin 자동부여 흐름이나 NextJS admin 영역에서 호출 (별건).
"""
from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.dependencies import get_db
from apps.schemas.documents import (
    DocumentItem,
    SeriesCreateRequest,
    SeriesItem,
    SeriesListResponse,
    SeriesMembersResponse,
    SeriesPatchRequest,
    SeriesReviewItem,
)
from packages.code.logger import get_logger
from packages.db import repository as repo
from packages.db.models import SeriesRecord
from packages.db.repository import to_doc_record

logger = get_logger(__name__)

router = APIRouter()


def _to_item(record: SeriesRecord, member_count: int) -> SeriesItem:
    return SeriesItem(
        series_id=record.series_id,
        title=record.title,
        description=record.description,
        cover_doc_id=record.cover_doc_id,
        series_type=record.series_type,
        member_count=member_count,
        created_at=record.created_at.isoformat() if record.created_at else "",
    )


@router.get("/series", response_model=SeriesListResponse)
def list_all_series(db: Session = Depends(get_db)):
    records = repo.list_series(db)
    items: list[SeriesItem] = []
    for r in records:
        members = repo.list_series_members(db, r.series_id)
        items.append(_to_item(r, member_count=len(members)))
    return SeriesListResponse(series=items, total=len(items))


@router.get("/series/{series_id}", response_model=SeriesItem)
def get_one(series_id: str, db: Session = Depends(get_db)):
    record = repo.get_series(db, series_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"시리즈를 찾을 수 없음: {series_id}")
    members = repo.list_series_members(db, series_id)
    return _to_item(record, member_count=len(members))


@router.get("/series/{series_id}/members", response_model=SeriesMembersResponse)
def list_members(series_id: str, db: Session = Depends(get_db)):
    if repo.get_series(db, series_id) is None:
        raise HTTPException(status_code=404, detail=f"시리즈를 찾을 수 없음: {series_id}")
    members = repo.list_series_members(db, series_id)
    return SeriesMembersResponse(
        series_id=series_id,
        members=[DocumentItem(**vars(to_doc_record(m))) for m in members],
    )


@router.post("/series", response_model=SeriesItem, status_code=201)
def create_one(body: SeriesCreateRequest, db: Session = Depends(get_db)):
    sid = body.series_id or f"ser_{uuid.uuid4().hex[:12]}"
    if repo.get_series(db, sid) is not None:
        raise HTTPException(status_code=409, detail=f"이미 존재하는 series_id: {sid}")
    record = repo.create_series(
        db,
        series_id=sid,
        title=body.title,
        description=body.description,
        cover_doc_id=body.cover_doc_id,
        series_type=body.series_type,
    )
    return _to_item(record, member_count=0)


@router.patch("/series/{series_id}", response_model=SeriesItem)
def update_one(series_id: str, body: SeriesPatchRequest, db: Session = Depends(get_db)):
    record = repo.update_series(
        db,
        series_id,
        title=body.title,
        description=body.description,
        cover_doc_id=body.cover_doc_id,
        series_type=body.series_type,
    )
    if record is None:
        raise HTTPException(status_code=404, detail=f"시리즈를 찾을 수 없음: {series_id}")
    members = repo.list_series_members(db, series_id)
    return _to_item(record, member_count=len(members))


@router.delete("/series/{series_id}")
def delete_one(series_id: str, db: Session = Depends(get_db)):
    """시리즈 삭제. FK ON DELETE SET NULL로 멤버 documents.series_id는 NULL로 분리됨."""
    deleted = repo.delete_series(db, series_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"시리즈를 찾을 수 없음: {series_id}")
    return {"series_id": series_id, "deleted": True}


# ── 매치 검수 ────────────────────────────────────────────────


@router.get("/series/_review/queue", response_model=list[SeriesReviewItem])
def review_queue(db: Session = Depends(get_db)):
    """auto_attached + suggested 두 큐 일람 — 관리자 검수용."""
    docs = repo.list_pending_review(db)
    items: list[SeriesReviewItem] = []
    for d in docs:
        s = repo.get_series(db, d.series_id) if d.series_id else None
        items.append(SeriesReviewItem(
            doc_id=d.doc_id,
            title=d.title,
            series_id=d.series_id,
            series_title=s.title if s else None,
            volume_number=d.volume_number,
            series_match_status=d.series_match_status or "none",
        ))
    return items


@router.post("/documents/{doc_id}/series_match/confirm", response_model=DocumentItem)
def confirm_match(doc_id: str, db: Session = Depends(get_db)):
    """auto_attached → confirmed (관리자가 자동 묶기를 확정)."""
    doc = repo.get_document(db, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"문서를 찾을 수 없음: {doc_id}")
    if doc.series_id is None:
        raise HTTPException(status_code=400, detail="series_id가 비어있어 confirm 불가. attach 먼저 수행.")
    record = repo.update_match_status(db, doc_id, "confirmed")
    return DocumentItem(**vars(to_doc_record(record)))


@router.post("/documents/{doc_id}/series_match/reject", response_model=DocumentItem)
def reject_match(doc_id: str, db: Session = Depends(get_db)):
    """auto_attached/suggested → rejected (분리 + 동일 휴리스틱 재바인딩 차단)."""
    doc = repo.get_document(db, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"문서를 찾을 수 없음: {doc_id}")
    record = repo.detach_from_series(db, doc_id, mark_rejected=True)
    return DocumentItem(**vars(to_doc_record(record)))


@router.post("/documents/{doc_id}/series_match/attach")
def attach_manual(
    doc_id: str,
    series_id: str,
    volume_number: int | None = None,
    db: Session = Depends(get_db),
):
    """수동 묶기 — 관리자가 시리즈를 직접 지정. status=confirmed로 마킹."""
    doc = repo.get_document(db, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"문서를 찾을 수 없음: {doc_id}")
    if repo.get_series(db, series_id) is None:
        raise HTTPException(status_code=404, detail=f"시리즈를 찾을 수 없음: {series_id}")
    record = repo.attach_to_series(
        db,
        doc_id,
        series_id=series_id,
        volume_number=volume_number,
        volume_title=doc.title,
        match_status="confirmed",
    )
    return DocumentItem(**vars(to_doc_record(record)))
