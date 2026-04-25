from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from packages.db.models import DocumentRecord
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
