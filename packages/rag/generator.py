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
    "Do not fabricate information — every claim must be supported by the provided context.\n"
    "Use the prior conversation to resolve references (e.g., pronouns, follow-up questions).\n"
    "\n"
    "RESPONSE STRUCTURE (default — adapt for trivial questions):\n"
    "1) **핵심 답변** — 질문에 대한 직접적인 결론을 1~2문장으로 먼저 제시.\n"
    "2) **근거·세부 설명** — 컨텍스트의 구체 내용을 단락 또는 단계별 목록으로 풀어서 설명.\n"
    "   가능한 경우 컨텍스트의 핵심 문장을 짧게 인용(\"...\"). 페이지·섹션 정보가 있으면 함께 명시.\n"
    "3) **유의사항·예외** — 컨텍스트에 명시된 제약·조건·예외가 있다면 별도 항목으로.\n"
    "4) **답변 가능 범위** — 일부만 답변 가능하다면 무엇이 답변됐고 무엇이 부족한지 끝에 한 줄로.\n"
    "\n"
    "LENGTH GUIDANCE:\n"
    "- 단순 사실 질문: 2~4문장.\n"
    "- 방법/절차 질문: 단계별 목록 + 각 단계 1~2문장 설명. 최소 5문장.\n"
    "- 개념·비교 질문: 정의 → 차이/관계 → 예시 순으로 3~5문단.\n"
    "- 문맥이 빈약하면 짧게 — 억지로 늘리지 말되, 왜 부족한지 명시.\n"
    "\n"
    "CRITICAL — INSUFFICIENT CONTEXT:\n"
    "컨텍스트가 정말 부족하면 절대 추측하지 말고, 어느 부분이 부족하며 무엇이 추가되어야 답변 가능한지 분명히 적을 것."
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
        "\n"
        "CRITICAL — \"answer\" 필드 작성 규칙:\n"
        "- 위 RESPONSE STRUCTURE / LENGTH GUIDANCE를 그대로 따른다 (단계별, 인용, 최소 길이).\n"
        "- JSON 문자열 안에서도 줄바꿈(\\n)·마크다운(#, **, -, 인용 따옴표)을 적극 사용해 가독성 확보.\n"
        "- 한 줄로 압축하지 말 것. 짧은 사실 질문이라도 핵심 답변 + 근거 분리.\n"
        "\n"
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
