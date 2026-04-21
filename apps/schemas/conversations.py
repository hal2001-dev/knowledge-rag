from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MessageItem(BaseModel):
    role: str
    content: str
    created_at: datetime


class ConversationSummary(BaseModel):
    session_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationDetail(BaseModel):
    session_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageItem]


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummary]
    total: int


class CreateConversationRequest(BaseModel):
    title: Optional[str] = ""
