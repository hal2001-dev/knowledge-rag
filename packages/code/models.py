from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Document:
    content: str
    metadata: dict = field(default_factory=dict)
    # metadata keys: doc_id, title, source, page, chunk_index,
    #                indexed_at, language, content_type (text|table|image)


@dataclass
class DocRecord:
    doc_id: str
    title: str
    source: str
    file_type: str
    chunk_count: int
    has_tables: bool
    has_images: bool
    indexed_at: str
    status: str = "done"
    content_hash: Optional[str] = None
    summary: Optional[dict] = None
    summary_model: Optional[str] = None
    summary_generated_at: Optional[str] = None
    doc_type: str = "book"
    category: Optional[str] = None
    category_confidence: Optional[float] = None
    tags: list = field(default_factory=list)
    # TASK-020 (ADR-029)
    series_id: Optional[str] = None
    volume_number: Optional[int] = None
    volume_title: Optional[str] = None
    series_match_status: str = "none"
    # ISSUE-010: 텍스트 추출 품질 (NULL/None = 미평가/ok 취급)
    extraction_quality: Optional[str] = None


@dataclass
class ScoredChunk:
    content: str
    metadata: dict
    score: float
