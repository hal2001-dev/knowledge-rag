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
    doc_filter: Optional[str] = Field(
        None,
        description="TASK-016: 특정 doc_id에 한정해 검색. 도서관 탭의 '이 책에 대해 묻기'.",
    )
    category_filter: Optional[str] = Field(
        None,
        description="TASK-019: 특정 카테고리(`payload.metadata.category`)에 한정해 검색. "
                    "상단 카테고리 칩·도서관 카테고리 [이 카테고리에 묻기].",
    )
    series_filter: Optional[str] = Field(
        None,
        description="TASK-020 (ADR-029): 특정 series_id에 한정해 검색. "
                    "도서관 시리즈 카드 [이 시리즈에 대해 묻기]. doc_filter > category_filter 보다 후순위.",
    )


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
