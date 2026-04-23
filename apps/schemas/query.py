from typing import Optional
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    session_id: Optional[str] = Field(
        None,
        description="대화 세션 ID. 없으면 새 세션이 생성됩니다.",
    )
    top_k: Optional[int] = None
    score_threshold: Optional[float] = None


class SourceItem(BaseModel):
    doc_id: str
    title: str
    page: Optional[int] = None
    content_type: str = "text"
    score: float
    excerpt: str


class QueryResponse(BaseModel):
    session_id: str
    answer: str
    sources: list[SourceItem]
    latency_ms: int
    suggestions: list[str] = []
