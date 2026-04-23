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


class IndexOverviewResponse(BaseModel):
    doc_count: int
    titles: list[str]
    top_headings: list[str]
    summary: str
    suggested_questions: list[str]
