from datetime import datetime, timezone
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
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
    summary = Column(JSONB, nullable=True)
    summary_model = Column(Text, nullable=True)
    summary_generated_at = Column(DateTime(timezone=True), nullable=True)

    # TASK-015 (ADR-025): 카테고리 메타데이터
    doc_type = Column(String(16), nullable=False, default="book")
    category = Column(String(64), nullable=True)
    category_confidence = Column(Float, nullable=True)
    tags = Column(JSONB, nullable=False, default=list)

    # TASK-020 (ADR-029): 시리즈/묶음 1급 시민. NULL이면 단일 문서, 값이면 series 테이블 멤버.
    series_id = Column(String, ForeignKey("series.series_id", ondelete="SET NULL"), nullable=True, index=True)
    volume_number = Column(Integer, nullable=True)
    volume_title = Column(Text, nullable=True)
    series_match_status = Column(String(16), nullable=False, default="none")

    __table_args__ = (
        CheckConstraint(
            "doc_type IN ('book','article','paper','note','report','web','other')",
            name="documents_doc_type_check",
        ),
        CheckConstraint(
            "series_match_status IN ('none','auto_attached','suggested','confirmed','rejected')",
            name="documents_series_match_status_check",
        ),
    )


class SeriesRecord(Base):
    """TASK-020 (ADR-029): 한 저작이 여러 파일로 쪼개진 경우의 묶음 단위.

    멤버 = `documents.series_id == series.series_id`인 행들. 시리즈 자체는 별도 카테고리·태그·요약을
    갖지 않고(의도적 제외), 멤버 메타를 표면에서 집계해 사용한다.
    """
    __tablename__ = "series"

    series_id = Column(String, primary_key=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    cover_doc_id = Column(String, nullable=True)
    series_type = Column(String(16), nullable=False, default="book")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "series_type IN ('book','series','volume')",
            name="series_type_check",
        ),
    )


class ConversationRecord(Base):
    __tablename__ = "conversations"

    session_id = Column(String, primary_key=True)
    # TASK-019 (ADR-030): Clerk user_id 또는 'admin' (Streamlit/로컬 호출).
    # 모델 레벨 default 미지정 — 모든 신규 INSERT는 미들웨어가 명시적으로 user_id 주입.
    # DB DEFAULT 'admin'은 마이그레이션 백필용으로만 사용.
    user_id = Column(String, nullable=False, index=True)
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


class IngestJobRecord(Base):
    """TASK-018: 색인 작업 큐 — FastAPI는 enqueue, indexer 워커가 SKIP LOCKED claim."""
    __tablename__ = "ingest_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(Text, nullable=True, index=True)
    file_path = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    source = Column(Text, nullable=False, default="")
    content_hash = Column(String(64), nullable=True)
    user_doc_type = Column(String(16), nullable=True)
    user_category = Column(String(64), nullable=True)
    user_tags = Column(JSONB, nullable=True)
    status = Column(String(16), nullable=False, default="pending")
    retry_count = Column(Integer, nullable=False, default=0)
    error = Column(Text, nullable=True)
    enqueued_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','in_progress','done','failed','cancelled')",
            name="ingest_jobs_status_check",
        ),
        Index("ix_ingest_jobs_status_enqueued", "status", "enqueued_at"),
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
