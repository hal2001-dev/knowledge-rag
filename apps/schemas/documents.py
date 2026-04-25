from typing import Optional
from pydantic import BaseModel


class DocumentItem(BaseModel):
    doc_id: str
    title: str
    source: str
    file_type: str
    chunk_count: int
    has_tables: bool
    has_images: bool
    indexed_at: str
    status: str
    summary: Optional[dict] = None
    summary_model: Optional[str] = None
    summary_generated_at: Optional[str] = None
    doc_type: str = "book"
    category: Optional[str] = None
    category_confidence: Optional[float] = None
    tags: list[str] = []


class DocumentPatchRequest(BaseModel):
    """TASK-015: 사용자 메타데이터 수정용. 모두 optional, None은 'no-op'."""
    doc_type: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[list[str]] = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentItem]
    total: int


class DeleteResponse(BaseModel):
    doc_id: str
    deleted: bool


class ChunkPreview(BaseModel):
    chunk_index: Optional[str] = None
    heading_path: list[str] = []
    page: Optional[int] = None
    content_type: str = "text"
    content: str  # 일정 길이로 자른 본문


class ChunkPreviewResponse(BaseModel):
    doc_id: str
    total_previewed: int
    chunks: list[ChunkPreview]


class RecentDocItem(BaseModel):
    """TASK-017: 랜딩 카드용 최근 문서 미니 정보."""
    doc_id: str
    title: str
    one_liner: Optional[str] = None
    category: Optional[str] = None


class IndexOverviewResponse(BaseModel):
    doc_count: int
    titles: list[str]
    top_headings: list[str]
    summary: str
    suggested_questions: list[str]
    # TASK-017: K014 요약 + K015 분류 데이터를 활용한 확장
    top_tags: list[str] = []
    categories: list[dict] = []   # [{id, label, count}]
    recent_docs: list[RecentDocItem] = []


class SummaryResponse(BaseModel):
    """TASK-014: 문서 요약 조회/재생성 응답."""
    doc_id: str
    title: str
    summary: Optional[dict] = None       # JSON 본문 (NULL이면 미생성)
    summary_model: Optional[str] = None
    summary_generated_at: Optional[str] = None
