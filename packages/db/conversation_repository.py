import uuid
from typing import Optional

from sqlalchemy.orm import Session

from packages.db.models import ConversationRecord, MessageRecord


def create_conversation(
    db: Session,
    user_id: str,
    title: str = "",
    session_id: Optional[str] = None,
) -> ConversationRecord:
    record = ConversationRecord(
        session_id=session_id or str(uuid.uuid4()),
        user_id=user_id,
        title=title,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_conversation(
    db: Session,
    session_id: str,
    user_id: Optional[str] = None,
) -> Optional[ConversationRecord]:
    """세션 조회. user_id가 주어지면 owner 검증까지 포함 — 다른 사용자 세션은 None.

    user_id를 명시하지 않으면 호출자가 직접 owner 검증을 책임짐 (예: 내부 헬퍼).
    """
    q = db.query(ConversationRecord).filter(
        ConversationRecord.session_id == session_id
    )
    if user_id is not None:
        q = q.filter(ConversationRecord.user_id == user_id)
    return q.first()


def get_or_create_conversation(
    db: Session,
    session_id: Optional[str],
    user_id: str,
) -> ConversationRecord:
    """세션 ID가 주어지면 user_id의 세션인지 확인 후 반환, 아니면 새로 생성.

    다른 사용자의 세션을 우연히 알아도 user_id 필터로 차단되어 새 세션이 생성됨.
    """
    if session_id:
        existing = get_conversation(db, session_id, user_id=user_id)
        if existing is not None:
            return existing
    return create_conversation(db, user_id=user_id, session_id=session_id)


def list_conversations(db: Session, user_id: str) -> list[ConversationRecord]:
    return (
        db.query(ConversationRecord)
        .filter(ConversationRecord.user_id == user_id)
        .order_by(ConversationRecord.updated_at.desc())
        .all()
    )


def delete_conversation(db: Session, session_id: str, user_id: str) -> bool:
    record = get_conversation(db, session_id, user_id=user_id)
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
