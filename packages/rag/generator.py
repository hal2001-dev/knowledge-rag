"""답변 생성 + 후속 질문 제안 (TASK-007 Phase 1 / TASK-026 grounding 강화)."""
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

# TASK-026: evidence가 이보다 짧으면 청크 어디에나 우연 매칭될 수 있어 검증이 무의미 — 폐기
_MIN_EVIDENCE_LEN = 5

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

# TASK-026: 후속 질문을 청크 근거에 grounding. 각 질문을 {q,source,evidence} 객체로 받아,
# evidence(청크에서 그대로 복사한 구절)를 호출 측이 청크 본문과 대조해 검증한다.
_GROUNDING_RULES = (
    "GROUNDING RULES — \"suggestions\" 작성 규칙 (엄격):\n"
    "- 정확히 {n}개의 후속 질문을 생성한다.\n"
    "- 각 질문은 제공된 청크에 실제로 등장하는 구체적 사실·개념·인물·사건을 직접 겨냥한다. "
    "일반 상식·추측 기반 질문 금지.\n"
    "- 각 질문은 제공된 청크만으로 답할 수 있어야 한다.\n"
    "- `source`: 근거가 된 청크의 출처 헤더(『제목』 p.NN)를 그대로 적는다.\n"
    "- `evidence`: 그 청크 본문에서 **그대로 복사한** 10~25자 구절. 요약·바꿔쓰기 금지. "
    "질문이 청크에 근거함을 증명하는 용도다.\n"
    "- 사용자 질문과 같은 언어. 완결된 질문 형태. 중복 금지. "
    "메타 질문 금지('더 있나요?', 'Anything else?').\n"
    "- 청크에 근거가 부족하면 개수를 줄인다 — 절대 지어내지 말 것.\n"
    "- 답변이 컨텍스트 부족(\"정보 없음\" 류)이면 suggestions를 빈 배열로 둔다.\n"
)

SYSTEM_PROMPT_WITH_SUGGESTIONS = (
    SYSTEM_PROMPT_PLAIN
    + "\n\n"
    + (
        "OUTPUT FORMAT — respond with a single JSON object only, no surrounding text:\n"
        "{{\n"
        '  "answer": "<the answer, in the same language as the question>",\n'
        '  "suggestions": [\n'
        '    {{"q": "<followup question>", "source": "<『제목』 p.NN>", '
        '"evidence": "<청크에서 그대로 복사한 근거 구절>"}}\n'
        "  ]\n"
        "}}\n"
        "\n"
        "CRITICAL — \"answer\" 필드 작성 규칙:\n"
        "- 위 RESPONSE STRUCTURE / LENGTH GUIDANCE를 그대로 따른다 (단계별, 인용, 최소 길이).\n"
        "- JSON 문자열 안에서도 줄바꿈(\\n)·마크다운(#, **, -, 인용 따옴표)을 적극 사용해 가독성 확보.\n"
        "- 한 줄로 압축하지 말 것. 짧은 사실 질문이라도 핵심 답변 + 근거 분리.\n"
        "\n"
    )
    + _GROUNDING_RULES
)


def _format_chunks(chunks: list[ScoredChunk]) -> str:
    """청크를 출처 헤더와 함께 LLM 컨텍스트 문자열로 직렬화.

    출처 제목·페이지를 헤더에 명시 — LLM이 답변·후속 질문에 책 제목을 정확히
    인용하고, suggestions의 `source`/`evidence`를 청크와 맞출 수 있도록.
    """
    parts = []
    for c in chunks:
        title = c.metadata.get("title") or "(제목 없음)"
        page = c.metadata.get("page")
        ct = c.metadata.get("content_type", "text")
        page_str = f" p.{page}" if page else ""
        parts.append(f"[{ct}] 출처: 『{title}』{page_str}\n{c.content}")
    return "\n\n---\n\n".join(parts)


def _build_messages(
    question: str,
    chunks: list[ScoredChunk],
    history: list[dict] | None,
    system_prompt: str,
) -> list:
    context = _format_chunks(chunks)
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


def _normalize(s: str) -> str:
    """evidence 대조용 정규화 — 공백·개행 제거 후 소문자."""
    return "".join(s.split()).lower()


def _ground_suggestions(raw_items, chunks: list[ScoredChunk], count: int) -> list[str]:
    """LLM이 낸 후속 질문 객체 배열을 청크 evidence로 검증해 q 문자열만 남긴다 (TASK-026).

    각 항목은 {"q","source","evidence"} 기대. evidence가 청크 본문에 (공백 무시)
    부분 일치하지 않으면 grounding 실패로 폐기 — "LLM이 지어낸" 질문을 거르는 장치.
    스키마를 벗어난 평문 문자열 항목도 검증 불가로 폐기한다.
    """
    if not isinstance(raw_items, list):
        return []
    corpus = _normalize("\n".join(c.content for c in chunks))
    grounded: list[str] = []
    dropped = 0
    for item in raw_items:
        if not isinstance(item, dict):
            dropped += 1
            continue
        q = (item.get("q") or "").strip()
        evidence = (item.get("evidence") or "").strip()
        if not q:
            continue
        norm_ev = _normalize(evidence)
        if len(norm_ev) >= _MIN_EVIDENCE_LEN and norm_ev in corpus:
            grounded.append(q)
        else:
            dropped += 1
            logger.info(
                f"suggestion 폐기 (evidence 미검증): q='{q[:40]}' "
                f"source='{item.get('source', '')}' evidence='{evidence[:30]}'"
            )
    if grounded or dropped:
        logger.info(f"suggestion grounding: {len(grounded)}개 통과, {dropped}개 폐기")
    return grounded[:count]


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
    suggestions는 청크 근거 기반으로 생성되고 evidence 검증을 통과한 것만 반환된다 (TASK-026).
    """
    if not suggestions_enabled:
        messages = _build_messages(question, chunks, history, SYSTEM_PROMPT_PLAIN)
        response = llm.invoke(messages)
        return {"answer": response.content, "suggestions": []}

    # 폐기 대비 +1개 더 생성하도록 요청 — 검증 통과분에서 상위 suggestions_count개 사용
    system = SYSTEM_PROMPT_WITH_SUGGESTIONS.format(n=suggestions_count + 1)
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
        suggestions = _ground_suggestions(parsed.get("suggestions"), chunks, suggestions_count)
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


# TASK-026: 스트리밍 경로의 후속 질문도 청크 근거에 grounding.
# 청크 본문을 입력으로 받아 {q,source,evidence} 스키마로 생성 — answer만 보던 기존 방식은
# 답변의 2차 추상화라 책 고유 디테일이 소실돼 "LLM이 지어낸" 질문이 나왔다.
_SUGGESTIONS_SYSTEM = (
    "You are given source chunks, a user question, and the assistant's answer.\n"
    "Generate {n} followup questions, each grounded in the source chunks.\n"
    "\n"
    "GROUNDING RULES (strict):\n"
    "- Each question MUST target a concrete fact, concept, person, or event that "
    "actually appears in the provided chunks — never general knowledge or guesses.\n"
    "- Each question MUST be answerable using ONLY the provided chunks.\n"
    "- 'source': the origin header of the chunk it relies on (『title』 p.NN).\n"
    "- 'evidence': a 10~25 char phrase copied VERBATIM from that chunk — no summary or "
    "paraphrase. It proves the question is grounded in the chunk.\n"
    "- Same language as the user question. Each is a complete question. No duplicates. "
    "No meta-questions like '더 있나요?' or 'Anything else?'.\n"
    "- If the chunks lack concrete material, generate fewer — never invent.\n"
    "- If the answer says the context is insufficient, return an empty list.\n"
    "Output a single JSON object only, no surrounding text:\n"
    '{{"suggestions": [{{"q": "...", "source": "<『title』 p.NN>", "evidence": "..."}}]}}'
)


def generate_suggestions(
    llm: ChatOpenAI,
    question: str,
    answer: str,
    chunks: list[ScoredChunk],
    count: int,
) -> list[str]:
    """TASK-024/026: 답변이 끝난 뒤 후속 질문을 청크 근거 기반으로 생성·검증.

    스트리밍 응답 종료 직후 동기 호출. 답변뿐 아니라 retrieve된 청크 본문을 입력으로
    받아, 각 후속 질문이 청크의 구체적 내용을 겨냥하도록 한다. LLM이 함께 낸 evidence
    구절을 청크 본문과 대조해 검증하고, 통과하지 못한 질문은 폐기한다 (TASK-026).
    """
    if not answer or not count or any(m in answer for m in INSUFFICIENT_MARKERS):
        return []
    if not chunks:
        return []
    # 폐기 대비 +1개 더 생성하도록 요청
    system = _SUGGESTIONS_SYSTEM.format(n=count + 1)
    context = _format_chunks(chunks)
    messages = [
        SystemMessage(content=system),
        HumanMessage(
            content=f"Source chunks:\n{context}\n\nQuestion: {question}\n\nAnswer: {answer}"
        ),
    ]
    try:
        response = llm.invoke(messages, response_format={"type": "json_object"})
    except TypeError:
        response = llm.invoke(messages)
    raw = getattr(response, "content", "") or ""
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, AttributeError) as e:
        logger.warning(f"suggestions JSON 파싱 실패 ({type(e).__name__})")
        return []
    return _ground_suggestions(parsed.get("suggestions"), chunks, count)
