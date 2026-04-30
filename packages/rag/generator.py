"""답변 생성 + 후속 질문 제안 (TASK-007 Phase 1)."""
from __future__ import annotations

import json
from typing import Iterator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from packages.code.logger import get_logger
from packages.code.models import ScoredChunk

logger = get_logger(__name__)

# 답변이 "정보 없음" 류일 때 suggestions를 강제로 비우기 위한 마커
INSUFFICIENT_MARKERS = ["관련 문서를 찾지 못했습니다", "insufficient", "cannot answer", "제공된 정보에는"]

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
    "   인용·설명 시 출처 문서의 **책/문서 제목을 본문에 자연스럽게 포함**할 것 (예: '『2001 스페이스 오디세이』 p.274에서…').\n"
    "   **인용 직후에 출처 페이지를 반드시 인라인으로 붙일 것** (예: '\"속이 텅 비었어\" (『2001 스페이스 오디세이』 p.290)').\n"
    "   각 인용문은 가져온 청크의 헤더(`출처: 『제목』 p.NN`)와 정확히 일치해야 하며 추측·복사 금지.\n"
    "3) **유의사항·예외** — 컨텍스트에 명시된 제약·조건·예외가 있다면 별도 항목으로.\n"
    "4) **답변 가능 범위** — 일부만 답변 가능하다면 무엇이 답변됐고 무엇이 부족한지 끝에 한 줄로.\n"
    "5) **참고 문서** — 답변에 사용한 출처를 끝에 한 줄로 명시 (예: '참고 문서: 『2001 스페이스 오디세이』 p.274, p.290').\n"
    "   여러 권에서 인용한 경우 모두 나열. 같은 책 다중 페이지면 페이지만 묶어 표기.\n"
    "   컨텍스트가 답에 충분치 않아 \"정보 없음\" 류로 답할 때는 이 항목 생략 가능.\n"
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
    # 출처 제목·페이지를 청크 헤더에 명시 — LLM이 답변에 책 제목을 정확히 인용할 수 있도록.
    parts = []
    for c in chunks:
        title = c.metadata.get("title") or "(제목 없음)"
        page = c.metadata.get("page")
        ct = c.metadata.get("content_type", "text")
        page_str = f" p.{page}" if page else ""
        parts.append(f"[{ct}] 출처: 『{title}』{page_str}\n{c.content}")
    context = "\n\n---\n\n".join(parts)
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
    if any(m in answer for m in INSUFFICIENT_MARKERS):
        suggestions = []

    return {"answer": answer, "suggestions": suggestions}


def generate_stream(
    llm: ChatOpenAI,
    question: str,
    chunks: list[ScoredChunk],
    history: list[dict] | None = None,
) -> Iterator[str]:
    """TASK-024: 답변 토큰 스트리밍.

    suggestions는 본 호출에서 생성하지 않고, 호출 측이 토큰을 모두 수집한 뒤
    `generate_suggestions(...)`로 별도 발급한다. JSON 모드 streaming은 부분 JSON
    파싱이 까다롭고 토큰 시작이 `"answer":` 헤더를 거쳐야 해 첫 토큰 지연.
    분리해서 파이프라인 단순성 + 첫 토큰 ~500ms 확보.
    """
    messages = _build_messages(question, chunks, history, SYSTEM_PROMPT_PLAIN)
    for chunk in llm.stream(messages):
        text = getattr(chunk, "content", "") or ""
        if text:
            yield text


_SUGGESTIONS_SYSTEM = (
    "Given a user question and the assistant's answer, generate exactly {n} concrete "
    "followup questions a user might naturally ask next. Same language as the question. "
    "Each is a complete question (not a phrase or keyword). No duplicates. "
    "No meta-questions like '더 있나요?' or 'Anything else?'. "
    "If the answer says the context is insufficient, return an empty list.\n"
    "Output a single JSON object only, no surrounding text:\n"
    '{{"suggestions": ["...", "..."]}}'
)


def generate_suggestions(
    llm: ChatOpenAI,
    question: str,
    answer: str,
    count: int,
) -> list[str]:
    """TASK-024: 답변이 끝난 뒤 후속 질문만 별도 LLM 호출로 빠르게 생성.

    스트리밍 응답 종료 직후 동기 호출. 출력 토큰 수가 적어 ~1~2초 추가.
    """
    if not answer or not count or any(m in answer for m in INSUFFICIENT_MARKERS):
        return []
    system = _SUGGESTIONS_SYSTEM.format(n=count)
    messages = [
        SystemMessage(content=system),
        HumanMessage(content=f"Question: {question}\n\nAnswer: {answer}"),
    ]
    try:
        response = llm.invoke(messages, response_format={"type": "json_object"})
    except TypeError:
        response = llm.invoke(messages)
    raw = getattr(response, "content", "") or ""
    try:
        parsed = json.loads(raw)
        items = parsed.get("suggestions") or []
        if not isinstance(items, list):
            return []
        return [s.strip() for s in items if isinstance(s, str) and s.strip()][:count]
    except (json.JSONDecodeError, AttributeError) as e:
        logger.warning(f"suggestions JSON 파싱 실패 ({type(e).__name__})")
        return []
