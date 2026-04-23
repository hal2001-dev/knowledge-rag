import json
from collections import Counter
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from apps.config import get_settings
from apps.dependencies import get_db, get_pipeline
from apps.schemas.documents import (
    ChunkPreview,
    ChunkPreviewResponse,
    DeleteResponse,
    DocumentItem,
    DocumentListResponse,
    IndexOverviewResponse,
)
from packages.code.logger import get_logger
from packages.db.repository import delete_document, get_document, list_documents, to_doc_record
from packages.rag.pipeline import RAGPipeline

logger = get_logger(__name__)
router = APIRouter()

# 인메모리 캐시 — 업로드·삭제 시 `invalidate_index_overview_cache()`로 무효화
_overview_cache: dict | None = None
_overview_cache_key: tuple | None = None  # (doc_count, sorted doc_ids) 기반 key


def invalidate_index_overview_cache() -> None:
    """문서 업로드/삭제 시 호출해 인덱스 요약 캐시를 비운다."""
    global _overview_cache, _overview_cache_key
    _overview_cache = None
    _overview_cache_key = None


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

    # 디스크 고아 파일 동반 정리 (TASK-009): data/uploads/{doc_id}.*, data/markdown/{doc_id}.md
    settings = get_settings()
    removed_files: list[str] = []
    for p in Path(settings.upload_dir).glob(f"{doc_id}.*"):
        try:
            p.unlink()
            removed_files.append(str(p))
        except Exception as e:
            logger.warning(f"업로드 원본 삭제 실패 {p}: {e}")
    md_path = Path(settings.markdown_dir) / f"{doc_id}.md"
    if md_path.exists():
        try:
            md_path.unlink()
            removed_files.append(str(md_path))
        except Exception as e:
            logger.warning(f"마크다운 삭제 실패 {md_path}: {e}")
    if removed_files:
        logger.info(f"doc_id={doc_id} 디스크 정리 완료: {len(removed_files)}개 파일")

    invalidate_index_overview_cache()
    return DeleteResponse(doc_id=doc_id, deleted=True)


@router.get("/index/overview", response_model=IndexOverviewResponse)
def index_overview(
    pipeline: RAGPipeline = Depends(get_pipeline),
    db: Session = Depends(get_db),
):
    """
    빈 채팅 empty state용 — 현재 인덱싱된 문서들의 요약 + 예시 질문 5개.
    문서 목록 변동 없으면 인메모리 캐시 사용 (LLM 반복 호출 방지).
    """
    settings = get_settings()
    if not settings.index_overview_enabled:
        return IndexOverviewResponse(
            doc_count=0, titles=[], top_headings=[], summary="", suggested_questions=[]
        )

    global _overview_cache, _overview_cache_key

    records = list_documents(db)
    doc_count = len(records)
    doc_ids = sorted(r.doc_id for r in records)
    cache_key = (doc_count, tuple(doc_ids))

    if _overview_cache is not None and _overview_cache_key == cache_key:
        return IndexOverviewResponse(**_overview_cache)

    if doc_count == 0:
        response = IndexOverviewResponse(
            doc_count=0,
            titles=[],
            top_headings=[],
            summary="아직 인덱싱된 문서가 없습니다. 문서 탭에서 업로드해 보세요.",
            suggested_questions=[],
        )
        _overview_cache = response.model_dump()
        _overview_cache_key = cache_key
        return response

    # 1) heading 집계: 문서당 상위 청크를 sample로 heading_path의 최상위 원소 빈도 계산
    heading_counter: Counter = Counter()
    titles = []
    for r in records:
        titles.append(r.title)
        try:
            sample_chunks = pipeline._store.scroll_by_doc_id(r.doc_id, limit=50)
        except Exception as e:
            logger.warning(f"heading 집계 실패 doc={r.doc_id}: {e}")
            continue
        for c in sample_chunks:
            hp = c.metadata.get("heading_path") or []
            if hp:
                # 최상위 heading (장/부) 선호
                heading_counter[hp[0]] += 1

    top_headings = [h for h, _ in heading_counter.most_common(10)]

    # 2) LLM 1회 호출 — 요약 2~3줄 + 예시 질문 5개
    llm_input = (
        f"인덱싱된 문서 ({doc_count}개):\n"
        + "\n".join(f"- {t}" for t in titles[:20])
        + "\n\n"
        + f"자주 등장하는 주제(heading): {', '.join(top_headings[:10]) or '(없음)'}\n"
    )

    prompt = (
        "You are introducing a RAG knowledge base to a new user. "
        "Given the document titles and frequent heading topics, respond in a JSON object with two fields:\n"
        '  {"summary": "<한국어 2~3문장. 이 시스템이 어떤 분야의 무엇을 알고 있는지>", '
        '"suggested_questions": ["<질문1>", ..., "<질문5>"]}\n'
        "Rules:\n"
        "- summary는 한국어 2~3문장, 사용자가 이 시스템의 범위를 즉시 파악할 수 있게\n"
        "- suggested_questions는 한국어로 정확히 5개, 실제 답변 가능한 구체적 질문\n"
        "- 중복·메타질문(예: '무엇이 있나요?') 금지\n"
        "\n" + llm_input
    )

    summary = ""
    suggested_questions: list[str] = []
    try:
        raw = pipeline._llm.invoke(
            prompt, response_format={"type": "json_object"}
        ).content or ""
        parsed = json.loads(raw)
        summary = (parsed.get("summary") or "").strip()
        qs = parsed.get("suggested_questions") or []
        if isinstance(qs, list):
            suggested_questions = [q.strip() for q in qs if isinstance(q, str) and q.strip()][:5]
    except Exception as e:
        logger.warning(f"index overview LLM 생성 실패: {e}")
        summary = f"현재 {doc_count}개 문서가 인덱싱되어 있습니다."
        suggested_questions = []

    response = IndexOverviewResponse(
        doc_count=doc_count,
        titles=titles[:20],
        top_headings=top_headings[:10],
        summary=summary,
        suggested_questions=suggested_questions,
    )
    _overview_cache = response.model_dump()
    _overview_cache_key = cache_key
    return response


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
