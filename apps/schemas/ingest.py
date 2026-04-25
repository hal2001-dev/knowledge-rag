from typing import Optional
from pydantic import BaseModel


class IngestResponse(BaseModel):
    doc_id: str
    title: str
    status: str            # "done" (sync) | "pending" (queue)
    chunk_count: int       # queue 모드는 0 (워커가 갱신)
    has_tables: bool
    has_images: bool
    duplicate: bool = False
    # TASK-018: queue 모드일 때만 채워짐
    job_id: Optional[int] = None
