import hashlib
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from apps.config import get_settings
from apps.dependencies import get_db, get_pipeline
from apps.schemas.ingest import IngestResponse
from packages.db.repository import create_document, get_document_by_hash, to_doc_record
from packages.rag.pipeline import RAGPipeline

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    file: UploadFile = File(...),
    title: str = Form(...),
    source: str = Form(""),
    pipeline: RAGPipeline = Depends(get_pipeline),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    ext = Path(file.filename or "").suffix.lower()
    if ext not in {".pdf", ".txt", ".md", ".docx"}:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 파일 형식: {ext}")

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.max_upload_size_mb:
        raise HTTPException(
            status_code=413,
            detail=f"파일 크기 초과: {size_mb:.1f}MB (최대 {settings.max_upload_size_mb}MB)",
        )

    content_hash = hashlib.sha256(content).hexdigest()
    existing = get_document_by_hash(db, content_hash)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "이미 등록된 문서입니다.",
                "doc_id": existing.doc_id,
                "title": existing.title,
                "content_hash": content_hash,
            },
        )

    doc_id = str(uuid.uuid4())
    upload_path = Path(settings.upload_dir) / f"{doc_id}{ext}"
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path.write_bytes(content)

    # 원본 파일은 data/uploads/{doc_id}{ext}로 영구 보관한다 (재인덱싱 가능하도록).
    # 인덱싱 실패 시에만 업로드 파일을 제거한다.
    try:
        record = pipeline.ingest(
            file_path=str(upload_path),
            title=title,
            source=source or file.filename or "",
            doc_id=doc_id,
            content_hash=content_hash,
        )
        db_record = create_document(db, record)
        doc = to_doc_record(db_record)
    except Exception:
        upload_path.unlink(missing_ok=True)
        raise

    return IngestResponse(
        doc_id=doc.doc_id,
        title=doc.title,
        status=doc.status,
        chunk_count=doc.chunk_count,
        has_tables=doc.has_tables,
        has_images=doc.has_images,
        duplicate=False,
    )
