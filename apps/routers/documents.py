from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from apps.dependencies import get_db, get_pipeline
from apps.schemas.documents import (
    ChunkPreview,
    ChunkPreviewResponse,
    DeleteResponse,
    DocumentItem,
    DocumentListResponse,
)
from packages.db.repository import delete_document, get_document, list_documents, to_doc_record
from packages.rag.pipeline import RAGPipeline

router = APIRouter()


@router.get("/documents", response_model=DocumentListResponse)
def list_docs(db: Session = Depends(get_db)):
    records = list_documents(db)
    items = [
        DocumentItem(**vars(to_doc_record(r)))
        for r in records
    ]
    return DocumentListResponse(documents=items, total=len(items))


@router.delete("/documents/{doc_id}", response_model=DeleteResponse)
def delete_doc(
    doc_id: str,
    pipeline: RAGPipeline = Depends(get_pipeline),
    db: Session = Depends(get_db),
):
    vector_deleted = pipeline._store.delete_by_doc_id(doc_id)
    db_deleted = delete_document(db, doc_id)

    if not db_deleted and not vector_deleted:
        raise HTTPException(status_code=404, detail=f"문서를 찾을 수 없음: {doc_id}")

    return DeleteResponse(doc_id=doc_id, deleted=True)


@router.get("/documents/{doc_id}/chunks", response_model=ChunkPreviewResponse)
def preview_chunks(
    doc_id: str,
    limit: int = Query(10, ge=1, le=50),
    pipeline: RAGPipeline = Depends(get_pipeline),
    db: Session = Depends(get_db),
):
    """관리자 UI용 청크 미리보기 — Qdrant payload scroll로 상위 N개 반환."""
    if get_document(db, doc_id) is None:
        raise HTTPException(status_code=404, detail=f"문서를 찾을 수 없음: {doc_id}")

    scored = pipeline._store.scroll_by_doc_id(doc_id, limit=limit)
    previews = [
        ChunkPreview(
            chunk_index=str(c.metadata.get("chunk_index")) if c.metadata.get("chunk_index") is not None else None,
            heading_path=c.metadata.get("heading_path") or [],
            page=c.metadata.get("page"),
            content_type=c.metadata.get("content_type", "text"),
            content=c.content[:500],
        )
        for c in scored
    ]
    return ChunkPreviewResponse(doc_id=doc_id, total_previewed=len(previews), chunks=previews)
