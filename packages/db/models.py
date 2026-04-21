from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class DocumentRecord(Base):
    __tablename__ = "documents"

    doc_id = Column(String, primary_key=True)
    title = Column(Text, nullable=False)
    source = Column(Text, default="")
    file_type = Column(String(16), default="pdf")
    content_hash = Column(String(64), unique=True, index=True, nullable=True)
    chunk_count = Column(Integer, default=0)
    has_tables = Column(Boolean, default=False)
    has_images = Column(Boolean, default=False)
    indexed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status = Column(String(32), default="done")


class ConversationRecord(Base):
    __tablename__ = "conversations"

    session_id = Column(String, primary_key=True)
    title = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    messages = relationship(
        "MessageRecord",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="MessageRecord.created_at",
    )


class MessageRecord(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        String,
        ForeignKey("conversations.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    role = Column(String(16), nullable=False)  # "user" | "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    conversation = relationship("ConversationRecord", back_populates="messages")

    __table_args__ = (
        Index("ix_messages_session_created", "session_id", "created_at"),
    )
