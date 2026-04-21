from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.dependencies import get_db
from apps.schemas.conversations import (
    ConversationDetail,
    ConversationListResponse,
    ConversationSummary,
    CreateConversationRequest,
    MessageItem,
)
from packages.db import conversation_repository as convo_repo

router = APIRouter(prefix="/conversations")


@router.post("", response_model=ConversationSummary)
def create_conversation(
    request: CreateConversationRequest,
    db: Session = Depends(get_db),
):
    record = convo_repo.create_conversation(db, title=request.title or "")
    return ConversationSummary(
        session_id=record.session_id,
        title=record.title or "",
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get("", response_model=ConversationListResponse)
def list_conversations(db: Session = Depends(get_db)):
    records = convo_repo.list_conversations(db)
    items = [
        ConversationSummary(
            session_id=r.session_id,
            title=r.title or "",
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in records
    ]
    return ConversationListResponse(conversations=items, total=len(items))


@router.get("/{session_id}", response_model=ConversationDetail)
def get_conversation(session_id: str, db: Session = Depends(get_db)):
    record = convo_repo.get_conversation(db, session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    messages = [
        MessageItem(role=m.role, content=m.content, created_at=m.created_at)
        for m in record.messages
    ]
    return ConversationDetail(
        session_id=record.session_id,
        title=record.title or "",
        created_at=record.created_at,
        updated_at=record.updated_at,
        messages=messages,
    )


@router.delete("/{session_id}")
def delete_conversation(session_id: str, db: Session = Depends(get_db)):
    if not convo_repo.delete_conversation(db, session_id):
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    return {"deleted": session_id}
