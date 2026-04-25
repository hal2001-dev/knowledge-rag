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
    DocumentPatchRequest,
    IndexOverviewResponse,
    RecentDocItem,
    SummaryResponse,
)
import yaml as _yaml
from pathlib import Path as _Path
from packages.classifier import CategoryClassifier
from packages.code.logger import get_logger
from packages.db.connection import get_session
from packages.db.repository import (
    delete_document,
    get_document,
    list_documents,
    to_doc_record,
    update_document_classification,
    update_document_summary,
)
from packages.rag.pipeline import RAGPipeline
from packages.summarizer.document_summarizer import summarize_document

VALID_DOC_TYPES = {"book", "article", "paper", "note", "report", "web", "other"}

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


def _classify_doc(db, pipeline, settings, record) -> None:
    """단일 문서 자동 분류 — DB + Qdrant payload 동시 갱신. 실패는 logger.warning."""
    try:
        classifier = CategoryClassifier.from_settings(settings)
        classifier.llm = pipeline._llm  # 기존 LLM 인스턴스 재사용
        result = classifier.classify(
            title=record.title or record.doc_id,
            file_type=record.file_type or "pdf",
            source=record.source or "",
            summary=record.summary,
        )
        update_document_classification(
            db,
            doc_id=record.doc_id,
            doc_type=result.doc_type,
            category=result.category,
            category_confidence=result.confidence,
            tags=result.tags,
        )
        pipeline._store.set_classification_payload(
            doc_id=record.doc_id,
            doc_type=result.doc_type,
            category=result.category if result.category is not None else "",
            tags=result.tags,
        )
        logger.info(
            f"분류 완료 doc_id={record.doc_id} doc_type={result.doc_type} "
            f"category={result.category} method={result.method}"
        )
    except Exception as e:
        logger.warning(f"classify 실패 doc_id={record.doc_id}: {e}")


def classify_and_summarize_for_doc(doc_id: str) -> None:
    """배경 작업 — summary 생성 후 같은 turn에 자동 분류 (TASK-014 + TASK-015)."""
    settings = get_settings()
    pipeline = get_pipeline()

    db_gen = get_session()
    db = next(db_gen)
    try:
        # summary 먼저
        if settings.summary_enabled:
            _generate_summary_inner(db, pipeline, settings, doc_id)
            db.expire_all()  # summary가 채워진 record를 다시 읽도록

        record = get_document(db, doc_id)
        if record is None:
            return
        _classify_doc(db, pipeline, settings, record)
    finally:
        db.close()


def _generate_summary_inner(db, pipeline, settings, doc_id: str) -> None:
    """공유 summary 생성 로직. db/pipeline은 호출자 책임."""
    record = get_document(db, doc_id)
    if record is None:
        logger.warning(f"summary 생성: 문서 없음 doc_id={doc_id}")
        return
    try:
        chunks = pipeline._store.scroll_by_doc_id(doc_id, limit=10)
    except Exception as e:
        logger.warning(f"summary scroll 실패 doc_id={doc_id}: {e}")
        return
    if not chunks:
        return
    try:
        result = summarize_document(
            title=record.title or doc_id,
            chunks=chunks,
            settings=settings,
            llm=pipeline._llm,
        )
    except Exception as e:
        logger.warning(f"summary LLM 실패 doc_id={doc_id}: {e}")
        return
    if not result.one_liner and not result.abstract:
        return
    update_document_summary(
        db, doc_id=doc_id, summary=result.to_dict(), model=result.model
    )
    logger.info(
        f"summary 생성 완료 doc_id={doc_id} model={result.model} "
        f"one_liner={result.one_liner!r}"
    )


def generate_summary_for_doc(doc_id: str) -> None:
    """배경 작업 — 인덱싱 직후 또는 강제 재생성 시 호출 (TASK-014).

    사용자가 분류값을 명시한 경우에만 호출됨(분류 자동화는 classify_and_summarize_for_doc).
    """
    settings = get_settings()
    if not settings.summary_enabled:
        return
    pipeline = get_pipeline()
    db_gen = get_session()
    db = next(db_gen)
    try:
        _generate_summary_inner(db, pipeline, settings, doc_id)
    finally:
        db.close()


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

    # 3) TASK-017 — K014/K015 데이터 합성: 주제 칩(top_tags), 카테고리 분포, 최근 문서 카드
    tag_counter: Counter = Counter()
    cat_counter: Counter = Counter()
    for r in records:
        for t in (r.tags or []):
            if isinstance(t, str) and t.strip():
                tag_counter[t.strip()] += 1
        if r.category:
            cat_counter[r.category] += 1

    top_tags = [t for t, _ in tag_counter.most_common(12)]

    # 카테고리 label 보강: categories.yaml과 매칭. 없으면 id 그대로.
    cat_labels: dict[str, str] = {}
    try:
        cats_path = _Path(__file__).parent.parent.parent / "config" / "categories.yaml"
        if cats_path.exists():
            data = _yaml.safe_load(cats_path.read_text(encoding="utf-8")) or {}
            for c in data.get("categories", []):
                cat_labels[c["id"]] = c.get("label", c["id"])
    except Exception:
        pass
    categories_dist = [
        {"id": cid, "label": cat_labels.get(cid, cid), "count": cnt}
        for cid, cnt in cat_counter.most_common()
    ]

    # 최근 문서 카드(상위 6개) — recent ordered already(list_documents desc)
    recent_docs: list[RecentDocItem] = []
    for r in records[:6]:
        sm = r.summary or {}
        recent_docs.append(
            RecentDocItem(
                doc_id=r.doc_id,
                title=r.title or r.doc_id,
                one_liner=(sm.get("one_liner") or "").strip() or None,
                category=r.category,
            )
        )

    response = IndexOverviewResponse(
        doc_count=doc_count,
        titles=titles[:20],
        top_headings=top_headings[:10],
        summary=summary,
        suggested_questions=suggested_questions,
        top_tags=top_tags,
        categories=categories_dist,
        recent_docs=recent_docs,
    )
    _overview_cache = response.model_dump()
    _overview_cache_key = cache_key
    return response


@router.patch("/documents/{doc_id}", response_model=DocumentItem)
def patch_document(
    doc_id: str,
    payload: DocumentPatchRequest,
    pipeline: RAGPipeline = Depends(get_pipeline),
    db: Session = Depends(get_db),
):
    """TASK-015: 사용자가 자동 분류 결과를 수정. 인증 미도입 단계라 로컬 LAN 전용."""
    if get_document(db, doc_id) is None:
        raise HTTPException(status_code=404, detail=f"문서를 찾을 수 없음: {doc_id}")

    if payload.doc_type is not None and payload.doc_type not in VALID_DOC_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"doc_type은 {sorted(VALID_DOC_TYPES)} 중 하나여야 합니다.",
        )

    confidence = 1.0 if payload.category is not None else None
    updated = update_document_classification(
        db,
        doc_id=doc_id,
        doc_type=payload.doc_type,
        category=payload.category,
        category_confidence=confidence,
        tags=payload.tags,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail=f"문서를 찾을 수 없음: {doc_id}")

    pipeline._store.set_classification_payload(
        doc_id=doc_id,
        doc_type=payload.doc_type,
        category=payload.category,
        tags=payload.tags,
    )

    return DocumentItem(**vars(to_doc_record(updated)))


@router.get("/documents/{doc_id}/summary", response_model=SummaryResponse)
def get_summary(doc_id: str, db: Session = Depends(get_db)):
    """TASK-014: 문서 요약 조회. 미생성이면 summary=null 로 반환."""
    record = get_document(db, doc_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"문서를 찾을 수 없음: {doc_id}")
    return SummaryResponse(
        doc_id=record.doc_id,
        title=record.title,
        summary=record.summary,
        summary_model=record.summary_model,
        summary_generated_at=(
            record.summary_generated_at.isoformat()
            if record.summary_generated_at
            else None
        ),
    )


@router.post("/documents/{doc_id}/summary/regenerate", response_model=SummaryResponse)
def regenerate_summary(
    doc_id: str,
    pipeline: RAGPipeline = Depends(get_pipeline),
    db: Session = Depends(get_db),
):
    """TASK-014: 동기 강제 재생성. 인증 미도입 단계라 로컬 LAN 전용으로 사용."""
    settings = get_settings()
    if not settings.summary_enabled:
        raise HTTPException(status_code=503, detail="summary_enabled=false")

    record = get_document(db, doc_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"문서를 찾을 수 없음: {doc_id}")

    chunks = pipeline._store.scroll_by_doc_id(doc_id, limit=10)
    if not chunks:
        raise HTTPException(status_code=409, detail="해당 문서의 청크가 없습니다.")

    result = summarize_document(
        title=record.title or doc_id,
        chunks=chunks,
        settings=settings,
        llm=pipeline._llm,
    )
    if not result.one_liner and not result.abstract:
        raise HTTPException(status_code=502, detail="요약 생성 실패 (빈 결과)")

    updated = update_document_summary(
        db, doc_id=doc_id, summary=result.to_dict(), model=result.model
    )
    return SummaryResponse(
        doc_id=updated.doc_id,
        title=updated.title,
        summary=updated.summary,
        summary_model=updated.summary_model,
        summary_generated_at=(
            updated.summary_generated_at.isoformat()
            if updated.summary_generated_at
            else None
        ),
    )


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
