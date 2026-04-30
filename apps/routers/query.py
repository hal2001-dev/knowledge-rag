import json
from typing import Iterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from langsmith.run_helpers import tracing_context
from sqlalchemy.orm import Session, sessionmaker

from apps.dependencies import get_db, get_pipeline
from apps.middleware.auth import get_request_user_id
from apps.schemas.query import QueryRequest, QueryResponse, SourceItem
from packages.code.logger import get_logger
from packages.db import conversation_repository as convo_repo
from packages.db.connection import get_engine
from packages.rag.pipeline import RAGPipeline

MAX_HISTORY = 20

logger = get_logger(__name__)
router = APIRouter()


def _sse(event: str, data) -> bytes:
    """SSE 한 이벤트 직렬화. data는 JSON 인코딩 (string도 따옴표로 감쌈)."""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")


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


@router.post("/query/stream")
def query_stream(
    request: QueryRequest,
    http_request: Request,
    pipeline: RAGPipeline = Depends(get_pipeline),
    db: Session = Depends(get_db),
):
    """TASK-024: SSE 답변 스트리밍.

    이벤트 시퀀스:
      event: meta        → {session_id}
      event: sources     → [{doc_id, title, page, ...}]
      event: token       → "부분 텍스트"          (반복)
      event: suggestions → [...]
      event: done        → {latency_ms}
      event: error       → {message}              (예외 시)

    사용자 메시지는 스트림 시작 전에 commit되어 conn drop에도 보존.
    어시스턴트 메시지는 스트림 종료 시 fresh DB session으로 commit.
    """
    user_id = get_request_user_id(http_request)
    conversation = convo_repo.get_or_create_conversation(db, request.session_id, user_id=user_id)
    session_id = conversation.session_id
    recent = convo_repo.get_recent_messages(db, session_id, limit=MAX_HISTORY)
    history = [{"role": m.role, "content": m.content} for m in recent]

    # 사용자 메시지 우선 저장 (스트림 도중 conn drop 시에도 보존)
    convo_repo.add_message(db, session_id, "user", request.question)

    def event_stream() -> Iterator[bytes]:
        try:
            yield _sse("meta", {"session_id": session_id})
            full_answer = ""
            with tracing_context(
                tags=[f"session:{session_id}", f"user:{user_id[:12]}"],
                metadata={"session_id": session_id, "user_id": user_id, "history_turns": len(history)},
            ):
                for event_type, data in pipeline.query_stream(
                    question=request.question,
                    top_k=request.top_k,
                    score_threshold=request.score_threshold,
                    history=history,
                    doc_filter=request.doc_filter,
                    category_filter=request.category_filter,
                    series_filter=request.series_filter,
                ):
                    if event_type == "done":
                        full_answer = data.get("answer", "")
                        yield _sse("done", {"latency_ms": data.get("latency_ms")})
                    else:
                        yield _sse(event_type, data)

            # 어시스턴트 메시지 영속화 — 스트림 종료 후 fresh session
            if full_answer:
                engine = get_engine()
                Session_ = sessionmaker(bind=engine)
                with Session_() as fresh_db:
                    convo_repo.add_message(fresh_db, session_id, "assistant", full_answer)
        except Exception as e:
            logger.exception("query_stream 예외")
            yield _sse("error", {"message": str(e)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # nginx 등 reverse proxy에서 버퍼링 비활성
        },
    )
