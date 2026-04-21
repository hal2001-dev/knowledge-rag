from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.dependencies import get_db, get_pipeline
from apps.schemas.documents import DeleteResponse, DocumentItem, DocumentListResponse
from packages.db.repository import delete_document, list_documents, to_doc_record
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
