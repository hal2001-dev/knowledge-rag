"""문서 단위 자동 요약 (TASK-014, ADR-024).

- 모델: gpt-4o-mini (기존 LLM_BACKEND=openai 인프라 재활용, 신규 키 불필요)
- 입력: 문서 첫 5~10청크(약 2~4K 토큰)
- 출력 스키마(JSON): one_liner, abstract, topics[], target_audience, sample_questions[]
- 환각 방지: prompts.py의 system + few-shot, JSON 모드 강제
- 회귀: SUMMARY_ENABLED=false 또는 환경 변수로 비활성 가능
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from apps.config import Settings
from packages.code.logger import get_logger
from packages.code.models import ScoredChunk
from packages.llm.chat import build_chat
from packages.summarizer.prompts import (
    SYSTEM_PROMPT,
    build_few_shot_messages,
    build_user_prompt,
)

logger = get_logger(__name__)

# 입력 청크 상한 — 너무 길면 비용·환각 위험. 첫 N개로 자른다.
_HEAD_CHUNK_LIMIT = 8
# 청크당 본문 길이 상한(문자) — 책 한 챕터가 1청크일 수도 있어 분량 보호
_CHUNK_CHAR_LIMIT = 1500


@dataclass
class SummaryResult:
    one_liner: str = ""
    abstract: str = ""
    topics: list[str] = field(default_factory=list)
    target_audience: str = ""
    sample_questions: list[str] = field(default_factory=list)
    model: str = ""

    def to_dict(self) -> dict:
        # DB JSONB에는 model을 제외한 본문만 저장 (model은 별도 컬럼)
        return {
            "one_liner": self.one_liner,
            "abstract": self.abstract,
            "topics": list(self.topics),
            "target_audience": self.target_audience,
            "sample_questions": list(self.sample_questions),
        }


def _build_head_text(chunks: list[ScoredChunk]) -> str:
    """첫 N개 청크를 단일 텍스트로 연결. heading_path가 있으면 머리에 붙여 맥락 보강."""
    parts: list[str] = []
    for c in chunks[:_HEAD_CHUNK_LIMIT]:
        body = (c.content or "")[:_CHUNK_CHAR_LIMIT]
        heading = c.metadata.get("heading_path") if isinstance(c.metadata, dict) else None
        if heading:
            parts.append(f"[{' > '.join(heading)}]\n{body}")
        else:
            parts.append(body)
    return "\n\n".join(parts).strip()


def _coerce_summary(raw: dict, model: str) -> SummaryResult:
    """LLM 응답 → SummaryResult. 누락 필드는 기본값으로 복원."""
    def _str_list(v) -> list[str]:
        if not isinstance(v, list):
            return []
        return [str(x).strip() for x in v if isinstance(x, str) and str(x).strip()]

    return SummaryResult(
        one_liner=str(raw.get("one_liner") or "").strip()[:80],
        abstract=str(raw.get("abstract") or "").strip(),
        topics=_str_list(raw.get("topics"))[:10],
        target_audience=str(raw.get("target_audience") or "").strip()[:80],
        sample_questions=_str_list(raw.get("sample_questions"))[:5],
        model=model,
    )


def summarize_document(
    title: str,
    chunks: list[ScoredChunk],
    settings: Settings,
    llm: Optional[ChatOpenAI] = None,
) -> SummaryResult:
    """문서 단위 요약을 1회 LLM 호출로 생성.

    Args:
        title: 문서 제목 (메타데이터의 title)
        chunks: 해당 문서의 청크 (chunk_index 오름차순 권장). 첫 _HEAD_CHUNK_LIMIT 개만 사용.
        settings: Settings (LLM 토글 정보)
        llm: 선택적 ChatOpenAI 인스턴스. 없으면 build_chat으로 생성.

    Returns:
        SummaryResult — 실패 시 모든 필드 빈값으로 반환 (호출 측 graceful 처리).
    """
    if not chunks:
        logger.warning(f"summarize: 청크가 비어있음 — title={title!r}")
        return SummaryResult()

    llm = llm or build_chat(settings)
    head = _build_head_text(chunks)
    if not head:
        logger.warning(f"summarize: 본문이 비어있음 — title={title!r}")
        return SummaryResult()

    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    for m in build_few_shot_messages():
        cls = HumanMessage if m["role"] == "user" else AIMessage
        messages.append(cls(content=m["content"]))
    messages.append(HumanMessage(content=build_user_prompt(title, head)))

    model_name = getattr(llm, "model_name", None) or getattr(llm, "model", "") or ""
    try:
        resp = llm.invoke(messages, response_format={"type": "json_object"})
        content = resp.content or ""
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        logger.warning(f"summarize: JSON 파싱 실패 title={title!r}: {e}")
        return SummaryResult(model=model_name)
    except Exception as e:
        logger.warning(f"summarize: LLM 호출 실패 title={title!r}: {e}")
        return SummaryResult(model=model_name)

    return _coerce_summary(parsed, model_name)
