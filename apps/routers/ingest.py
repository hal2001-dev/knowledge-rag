import asyncio
import hashlib
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from apps.config import get_settings
from apps.dependencies import get_db, get_pipeline
from apps.routers.documents import (
    classify_and_summarize_for_doc,
    generate_summary_for_doc,
    invalidate_index_overview_cache,
)
from apps.schemas.ingest import IngestResponse
from packages.db.repository import (
    create_document,
    get_document_by_hash,
    to_doc_record,
    update_document_classification,
)
from packages.jobs.queue import enqueue_job
from packages.rag.pipeline import RAGPipeline

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(...),
    source: str = Form(""),
    doc_type: str | None = Form(None),
    category: str | None = Form(None),
    tags: str | None = Form(None),
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

    # 사용자 명시 분류값 파싱 (큐·sync 모드 공통)
    parsed_tags: list[str] | None = None
    if tags is not None:
        parsed_tags = [t.strip() for t in tags.split(",") if t.strip()]

    # ─── 큐 모드 (TASK-018, ADR-028) ────────────────────────────
    if settings.ingest_mode == "queue":
        try:
            job = enqueue_job(
                db,
                doc_id=doc_id,
                file_path=str(upload_path),
                title=title,
                source=source or file.filename or "",
                content_hash=content_hash,
                user_doc_type=doc_type,
                user_category=category,
                user_tags=parsed_tags,
            )
        except Exception:
            upload_path.unlink(missing_ok=True)
            raise

        return IngestResponse(
            doc_id=doc_id,
            title=title,
            status="pending",
            chunk_count=0,
            has_tables=False,
            has_images=False,
            duplicate=False,
            job_id=job.id,
        )

    # ─── sync 모드 (회귀용) ─────────────────────────────────────
    # async 라우트 안의 sync 호출은 event loop를 막으므로 스레드풀로 위임
    try:
        record = await asyncio.to_thread(
            pipeline.ingest,
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

    invalidate_index_overview_cache()

    user_provided_category = any(v is not None for v in (doc_type, category, parsed_tags))
    if user_provided_category:
        update_document_classification(
            db,
            doc_id=doc.doc_id,
            doc_type=doc_type,
            category=category,
            category_confidence=1.0 if category else None,
            tags=parsed_tags,
        )
        pipeline._store.set_classification_payload(
            doc_id=doc.doc_id,
            doc_type=doc_type,
            category=category if category is not None else "",
            tags=parsed_tags,
        )

    if settings.summary_enabled:
        if user_provided_category:
            background_tasks.add_task(generate_summary_for_doc, doc.doc_id)
        else:
            background_tasks.add_task(classify_and_summarize_for_doc, doc.doc_id)

    return IngestResponse(
        doc_id=doc.doc_id,
        title=doc.title,
        status=doc.status,
        chunk_count=doc.chunk_count,
        has_tables=doc.has_tables,
        has_images=doc.has_images,
        duplicate=False,
    )
