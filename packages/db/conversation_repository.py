import uuid
from typing import Optional

from sqlalchemy.orm import Session

from packages.db.models import ConversationRecord, MessageRecord


def create_conversation(db: Session, title: str = "", session_id: Optional[str] = None) -> ConversationRecord:
    record = ConversationRecord(
        session_id=session_id or str(uuid.uuid4()),
        title=title,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_conversation(db: Session, session_id: str) -> Optional[ConversationRecord]:
    return (
        db.query(ConversationRecord)
        .filter(ConversationRecord.session_id == session_id)
        .first()
    )


def get_or_create_conversation(db: Session, session_id: Optional[str]) -> ConversationRecord:
    if session_id:
        existing = get_conversation(db, session_id)
        if existing is not None:
            return existing
    return create_conversation(db, session_id=session_id)


def list_conversations(db: Session) -> list[ConversationRecord]:
    return (
        db.query(ConversationRecord)
        .order_by(ConversationRecord.updated_at.desc())
        .all()
    )


def delete_conversation(db: Session, session_id: str) -> bool:
    record = get_conversation(db, session_id)
    if record is None:
        return False
    db.delete(record)
    db.commit()
    return True


def add_message(db: Session, session_id: str, role: str, content: str) -> MessageRecord:
    message = MessageRecord(session_id=session_id, role=role, content=content)
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def get_recent_messages(db: Session, session_id: str, limit: int = 20) -> list[MessageRecord]:
    """최근 N개 메시지를 시간 오름차순으로 반환 (LLM 프롬프트 주입용)."""
    rows = (
        db.query(MessageRecord)
        .filter(MessageRecord.session_id == session_id)
        .order_by(MessageRecord.created_at.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(rows))
