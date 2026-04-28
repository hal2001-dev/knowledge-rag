from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from packages.db.models import DocumentRecord, SeriesRecord
from packages.code.models import DocRecord


def create_document(db: Session, record: DocRecord) -> DocumentRecord:
    db_record = DocumentRecord(
        doc_id=record.doc_id,
        title=record.title,
        source=record.source,
        file_type=record.file_type,
        content_hash=record.content_hash,
        chunk_count=record.chunk_count,
        has_tables=record.has_tables,
        has_images=record.has_images,
        indexed_at=datetime.now(timezone.utc),
        status=record.status,
    )
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    return db_record


def get_document(db: Session, doc_id: str) -> Optional[DocumentRecord]:
    return db.query(DocumentRecord).filter(DocumentRecord.doc_id == doc_id).first()


def get_document_by_hash(db: Session, content_hash: str) -> Optional[DocumentRecord]:
    return (
        db.query(DocumentRecord)
        .filter(DocumentRecord.content_hash == content_hash)
        .first()
    )


def list_documents(db: Session) -> list[DocumentRecord]:
    return db.query(DocumentRecord).order_by(DocumentRecord.indexed_at.desc()).all()


def delete_document(db: Session, doc_id: str) -> bool:
    record = get_document(db, doc_id)
    if record is None:
        return False
    db.delete(record)
    db.commit()
    return True


def to_doc_record(db_record: DocumentRecord) -> DocRecord:
    return DocRecord(
        doc_id=db_record.doc_id,
        title=db_record.title,
        source=db_record.source or "",
        file_type=db_record.file_type or "pdf",
        chunk_count=db_record.chunk_count or 0,
        has_tables=db_record.has_tables or False,
        has_images=db_record.has_images or False,
        indexed_at=db_record.indexed_at.isoformat() if db_record.indexed_at else "",
        status=db_record.status or "done",
        content_hash=db_record.content_hash,
        summary=db_record.summary,
        summary_model=db_record.summary_model,
        summary_generated_at=(
            db_record.summary_generated_at.isoformat()
            if db_record.summary_generated_at
            else None
        ),
        doc_type=db_record.doc_type or "book",
        category=db_record.category,
        category_confidence=db_record.category_confidence,
        tags=list(db_record.tags or []),
        series_id=db_record.series_id,
        volume_number=db_record.volume_number,
        volume_title=db_record.volume_title,
        series_match_status=db_record.series_match_status or "none",
    )


def update_document_summary(
    db: Session,
    doc_id: str,
    summary: dict,
    model: str,
) -> Optional[DocumentRecord]:
    record = get_document(db, doc_id)
    if record is None:
        return None
    record.summary = summary
    record.summary_model = model
    record.summary_generated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)
    return record


def list_documents_without_summary(db: Session) -> list[DocumentRecord]:
    return (
        db.query(DocumentRecord)
        .filter(DocumentRecord.summary.is_(None))
        .order_by(DocumentRecord.indexed_at.desc())
        .all()
    )


def list_documents_without_category(db: Session) -> list[DocumentRecord]:
    return (
        db.query(DocumentRecord)
        .filter(DocumentRecord.category.is_(None))
        .order_by(DocumentRecord.indexed_at.desc())
        .all()
    )


def update_document_classification(
    db: Session,
    doc_id: str,
    *,
    doc_type: Optional[str] = None,
    category: Optional[str] = None,
    category_confidence: Optional[float] = None,
    tags: Optional[list[str]] = None,
) -> Optional[DocumentRecord]:
    record = get_document(db, doc_id)
    if record is None:
        return None
    if doc_type is not None:
        record.doc_type = doc_type
    if category is not None or category_confidence is not None:
        record.category = category
        record.category_confidence = category_confidence
    if tags is not None:
        record.tags = list(tags)
    db.commit()
    db.refresh(record)
    return record


# TASK-020 (ADR-029) — Series 1급 시민

def create_series(
    db: Session,
    *,
    series_id: str,
    title: str,
    description: Optional[str] = None,
    cover_doc_id: Optional[str] = None,
    series_type: str = "book",
) -> SeriesRecord:
    record = SeriesRecord(
        series_id=series_id,
        title=title,
        description=description,
        cover_doc_id=cover_doc_id,
        series_type=series_type,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_series(db: Session, series_id: str) -> Optional[SeriesRecord]:
    return db.query(SeriesRecord).filter(SeriesRecord.series_id == series_id).first()


def list_series(db: Session) -> list[SeriesRecord]:
    return db.query(SeriesRecord).order_by(SeriesRecord.created_at.desc()).all()


def update_series(
    db: Session,
    series_id: str,
    *,
    title: Optional[str] = None,
    description: Optional[str] = None,
    cover_doc_id: Optional[str] = None,
    series_type: Optional[str] = None,
) -> Optional[SeriesRecord]:
    record = get_series(db, series_id)
    if record is None:
        return None
    if title is not None:
        record.title = title
    if description is not None:
        record.description = description
    if cover_doc_id is not None:
        record.cover_doc_id = cover_doc_id
    if series_type is not None:
        record.series_type = series_type
    db.commit()
    db.refresh(record)
    return record


def delete_series(db: Session, series_id: str) -> bool:
    """series 삭제. FK ON DELETE SET NULL이라 멤버 documents.series_id는 NULL로 분리된다."""
    record = get_series(db, series_id)
    if record is None:
        return False
    db.delete(record)
    db.commit()
    return True


def list_series_members(db: Session, series_id: str) -> list[DocumentRecord]:
    return (
        db.query(DocumentRecord)
        .filter(DocumentRecord.series_id == series_id)
        .order_by(DocumentRecord.volume_number.asc().nullslast(), DocumentRecord.indexed_at.asc())
        .all()
    )


def attach_to_series(
    db: Session,
    doc_id: str,
    *,
    series_id: str,
    volume_number: Optional[int] = None,
    volume_title: Optional[str] = None,
    match_status: str = "auto_attached",
) -> Optional[DocumentRecord]:
    record = get_document(db, doc_id)
    if record is None:
        return None
    record.series_id = series_id
    if volume_number is not None:
        record.volume_number = volume_number
    if volume_title is not None:
        record.volume_title = volume_title
    record.series_match_status = match_status
    db.commit()
    db.refresh(record)
    return record


def detach_from_series(
    db: Session,
    doc_id: str,
    *,
    mark_rejected: bool = True,
) -> Optional[DocumentRecord]:
    """문서를 시리즈에서 분리. mark_rejected=True면 status=rejected로 마킹해 동일 휴리스틱의 재바인딩을 차단."""
    record = get_document(db, doc_id)
    if record is None:
        return None
    record.series_id = None
    record.volume_number = None
    record.volume_title = None
    record.series_match_status = "rejected" if mark_rejected else "none"
    db.commit()
    db.refresh(record)
    return record


def update_match_status(
    db: Session,
    doc_id: str,
    status: str,
) -> Optional[DocumentRecord]:
    record = get_document(db, doc_id)
    if record is None:
        return None
    record.series_match_status = status
    db.commit()
    db.refresh(record)
    return record


def list_pending_review(db: Session) -> list[DocumentRecord]:
    """auto_attached + suggested 상태 문서 — 관리자 검수 큐 데이터 원천."""
    return (
        db.query(DocumentRecord)
        .filter(DocumentRecord.series_match_status.in_(("auto_attached", "suggested")))
        .order_by(DocumentRecord.indexed_at.desc())
        .all()
    )
