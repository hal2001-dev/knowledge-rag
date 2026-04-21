from pydantic import BaseModel


class IngestResponse(BaseModel):
    doc_id: str
    title: str
    status: str
    chunk_count: int
    has_tables: bool
    has_images: bool
    duplicate: bool = False
