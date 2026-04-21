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
