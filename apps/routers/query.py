from fastapi import APIRouter, Depends, Request
from langsmith.run_helpers import tracing_context
from sqlalchemy.orm import Session

from apps.dependencies import get_db, get_pipeline
from apps.middleware.auth import get_request_user_id
from apps.schemas.query import QueryRequest, QueryResponse, SourceItem
from packages.db import conversation_repository as convo_repo
from packages.rag.pipeline import RAGPipeline

MAX_HISTORY = 20

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
def query(
    request: QueryRequest,
    http_request: Request,
    pipeline: RAGPipeline = Depends(get_pipeline),
    db: Session = Depends(get_db),
):
    user_id = get_request_user_id(http_request)
    conversation = convo_repo.get_or_create_conversation(db, request.session_id, user_id=user_id)
    session_id = conversation.session_id

    # 최근 MAX_HISTORY개 메시지를 LLM 컨텍스트로 주입 (현재 질문 저장 전 스냅샷)
    recent = convo_repo.get_recent_messages(db, session_id, limit=MAX_HISTORY)
    history = [{"role": m.role, "content": m.content} for m in recent]

    # LangSmith 트레이스에 session_id·user_id·히스토리 길이를 메타데이터로 남긴다.
    with tracing_context(
        tags=[f"session:{session_id}", f"user:{user_id[:12]}"],
        metadata={"session_id": session_id, "user_id": user_id, "history_turns": len(history)},
    ):
        result = pipeline.query(
            question=request.question,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
            history=history,
            doc_filter=request.doc_filter,
            category_filter=request.category_filter,
            series_filter=request.series_filter,
        )

    # 사용자 질문 + 어시스턴트 답변 저장
    convo_repo.add_message(db, session_id, "user", request.question)
    convo_repo.add_message(db, session_id, "assistant", result["answer"])

    sources = [SourceItem(**s) for s in result["sources"]]
    return QueryResponse(
        session_id=session_id,
        answer=result["answer"],
        sources=sources,
        latency_ms=result["latency_ms"],
        suggestions=result.get("suggestions", []),
    )
