from pathlib import Path

from packages.loaders.base import BaseLoader
from packages.loaders.docling_loader import DoclingDocumentLoader

_SUPPORTED = {".pdf", ".txt", ".md", ".docx"}


def get_loader(file_path: str, markdown_save_dir: str | None = None) -> BaseLoader:
    ext = Path(file_path).suffix.lower()
    if ext not in _SUPPORTED:
        raise ValueError(f"지원하지 않는 파일 형식: {ext}. 지원: {_SUPPORTED}")
    return DoclingDocumentLoader(markdown_save_dir=markdown_save_dir)
