"""답변 생성 + 후속 질문 제안 (TASK-007 Phase 1)."""
from __future__ import annotations

import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from packages.code.logger import get_logger
from packages.code.models import ScoredChunk

logger = get_logger(__name__)

SYSTEM_PROMPT_PLAIN = (
    "You are a helpful assistant that answers questions based on the provided context.\n"
    "Answer in the same language as the question (Korean or English).\n"
    "If the context does not contain enough information to answer, say so clearly.\n"
    "Do not fabricate information.\n"
    "Use the prior conversation to resolve references (e.g., pronouns, follow-up questions)."
)

SYSTEM_PROMPT_WITH_SUGGESTIONS = (
    SYSTEM_PROMPT_PLAIN
    + "\n\n"
    + (
        "OUTPUT FORMAT — respond with a single JSON object only, no surrounding text:\n"
        "{{\n"
        '  "answer": "<the answer, in the same language as the question>",\n'
        '  "suggestions": ["<followup question 1>", "<followup question 2>", ...]\n'
        "}}\n"
        "Rules for suggestions:\n"
        "- Generate exactly {n} concrete followup questions a user might naturally ask next.\n"
        "- Written in the same language as the user question.\n"
        "- Each is a full question (not a phrase/keyword).\n"
        "- No duplicates, no meta-questions (avoid things like '더 있나요?', 'Anything else?').\n"
        "- If the answer says the context is insufficient, return an empty suggestions list.\n"
    )
)


def _build_messages(
    question: str,
    chunks: list[ScoredChunk],
    history: list[dict] | None,
    system_prompt: str,
) -> list:
    context = "\n\n---\n\n".join(
        f"[{c.metadata.get('content_type', 'text')}] {c.content}" for c in chunks
    )
    messages = [SystemMessage(content=system_prompt)]
    for turn in history or []:
        role = turn.get("role")
        content = turn.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
    messages.append(
        HumanMessage(content=f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:")
    )
    return messages


def generate(
    llm: ChatOpenAI,
    question: str,
    chunks: list[ScoredChunk],
    history: list[dict] | None = None,
    suggestions_enabled: bool = False,
    suggestions_count: int = 3,
) -> dict:
    """
    반환: {"answer": str, "suggestions": list[str]}

    suggestions_enabled=False면 LLM 호출 1회로 답변만 생성 (기존 동작).
    True면 동일 LLM 호출에서 JSON 모드로 answer + suggestions 동시 생성.
    """
    if not suggestions_enabled:
        messages = _build_messages(question, chunks, history, SYSTEM_PROMPT_PLAIN)
        response = llm.invoke(messages)
        return {"answer": response.content, "suggestions": []}

    system = SYSTEM_PROMPT_WITH_SUGGESTIONS.format(n=suggestions_count)
    messages = _build_messages(question, chunks, history, system)

    # OpenAI-호환 JSON 모드 — `model_kwargs`로 전달 (GLM 등 일부 공급자는 무시될 수 있음)
    try:
        response = llm.invoke(
            messages,
            response_format={"type": "json_object"},
        )
    except TypeError:
        # response_format 미지원 모델 — 평문 응답 요청
        response = llm.invoke(messages)

    raw = response.content or ""

    # JSON 파싱 (실패 시 평문을 answer로, suggestions는 빈 배열로 graceful degrade)
    try:
        parsed = json.loads(raw)
        answer = parsed.get("answer", raw).strip()
        suggestions = parsed.get("suggestions") or []
        if not isinstance(suggestions, list):
            suggestions = []
        suggestions = [s.strip() for s in suggestions if isinstance(s, str) and s.strip()]
        suggestions = suggestions[:suggestions_count]
    except (json.JSONDecodeError, AttributeError) as e:
        logger.warning(f"suggestions JSON 파싱 실패 ({type(e).__name__}): 원문을 answer로 사용")
        answer = raw.strip()
        suggestions = []

    # 답변이 불충분 응답인 경우 suggestions 강제 비움
    insufficient_markers = ["관련 문서를 찾지 못했습니다", "insufficient", "cannot answer", "제공된 정보에는"]
    if any(m in answer for m in insufficient_markers):
        suggestions = []

    return {"answer": answer, "suggestions": suggestions}
