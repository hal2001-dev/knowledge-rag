"""문서 카테고리 자동 분류 (TASK-015, ADR-025).

알고리즘:
1. summary.topics[] + 제목을 정규화한 텍스트로 categories.yaml의 키워드 매칭 점수 계산
2. 가장 높은 점수의 카테고리 채택 — 신뢰도 = matched_keywords / max(1, len(category.keywords))
3. 매칭 점수 0이면 LLM fallback (gpt-4o-mini, JSON mode) — 카테고리 ID + 신뢰도 한 번에
4. LLM 응답이 enum에 없거나 신뢰도가 임계 미만이면 category=None + admin "검토 필요" 배지

doc_type은 LLM 호출 없이 file_type 휴리스틱으로 결정 (정확도 충분, 비용 0).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from apps.config import Settings
from packages.code.logger import get_logger
from packages.llm.chat import build_chat

logger = get_logger(__name__)

DEFAULT_CATEGORIES_PATH = Path(__file__).parent.parent.parent / "config" / "categories.yaml"
LLM_CONFIDENCE_FLOOR = 0.4  # 이보다 낮으면 NULL — admin 검수 배지
MAX_TAG_COUNT = 8           # tags 상한 (요약 topics이 그대로 들어옴)


@dataclass
class CategoryDef:
    id: str
    label: str
    keywords: list[str] = field(default_factory=list)

    @property
    def keywords_lower(self) -> list[str]:
        return [k.lower() for k in self.keywords]


@dataclass
class ClassifyResult:
    doc_type: str = "book"
    category: Optional[str] = None
    confidence: Optional[float] = None
    tags: list[str] = field(default_factory=list)
    method: str = "rule"  # "rule" | "llm" | "fallback_unknown"


def load_categories(path: Path | str | None = None) -> list[CategoryDef]:
    """categories.yaml 로드. 'other'는 항상 마지막에 배치."""
    p = Path(path) if path else DEFAULT_CATEGORIES_PATH
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    raw = data.get("categories") or []
    cats = [CategoryDef(id=c["id"], label=c.get("label", c["id"]), keywords=c.get("keywords") or []) for c in raw]
    # 'other'를 마지막으로 (분류 우선순위에서 fallback 의미)
    others = [c for c in cats if c.id == "other"]
    nonothers = [c for c in cats if c.id != "other"]
    return nonothers + others


def infer_doc_type(file_type: str, source: str = "") -> str:
    """간단 휴리스틱 — 사용자 지정 우선이라 보수적으로."""
    ft = (file_type or "").lower().lstrip(".")
    src = (source or "").lower()
    if "://" in src and src.startswith(("http", "ftp")):
        return "web"
    if ft in {"pdf"}:
        return "book"
    if ft in {"docx", "doc"}:
        return "report"
    if ft in {"md", "markdown", "txt"}:
        return "note"
    return "other"


def _build_match_text(title: str, topics: list[str]) -> str:
    parts = [title or ""]
    parts.extend(topics or [])
    return " ".join(parts).lower()


def _rule_score(text: str, cat: CategoryDef) -> int:
    if not cat.keywords:
        return 0
    return sum(1 for kw in cat.keywords_lower if kw in text)


def _llm_classify(
    title: str,
    summary: dict,
    categories: list[CategoryDef],
    llm: Optional[ChatOpenAI],
    settings: Settings,
) -> tuple[Optional[str], float, str]:
    """LLM에 카테고리 ID 1개와 신뢰도(0~1)를 묻는다. 실패 시 (None, 0.0, 'fallback_unknown')."""
    llm = llm or build_chat(settings)
    cat_lines = "\n".join(f"- {c.id}: {c.label}" for c in categories)
    prompt_user = (
        f"문서 제목: {title}\n"
        f"한 줄 요약: {summary.get('one_liner') or ''}\n"
        f"개요: {summary.get('abstract') or ''}\n"
        f"주제: {', '.join(summary.get('topics') or [])}\n\n"
        f"위 문서를 아래 카테고리 중 가장 적합한 1개에 배치하세요.\n"
        f"카테고리 목록:\n{cat_lines}\n\n"
        f'JSON으로 응답: {{"id": "<카테고리 id>", "confidence": <0~1 실수>}}\n'
        f'- 적합한 카테고리가 없으면 id="other", confidence는 낮게'
    )
    system = (
        "당신은 문서 분류기입니다. 반드시 주어진 카테고리 ID 중 하나를 고르고, "
        "확신이 약하면 confidence를 낮게 보고하세요. JSON만 출력하세요."
    )
    try:
        resp = llm.invoke(
            [SystemMessage(content=system), HumanMessage(content=prompt_user)],
            response_format={"type": "json_object"},
        )
        parsed = json.loads(resp.content or "{}")
        cid = (parsed.get("id") or "").strip()
        conf = float(parsed.get("confidence") or 0.0)
    except Exception as e:
        logger.warning(f"classify LLM 실패 title={title!r}: {e}")
        return None, 0.0, "fallback_unknown"

    valid_ids = {c.id for c in categories}
    if cid not in valid_ids:
        return None, 0.0, "fallback_unknown"
    return cid, max(0.0, min(1.0, conf)), "llm"


@dataclass
class CategoryClassifier:
    """문서 분류기 — 키워드 매칭 우선, LLM fallback. 인스턴스 1개를 재사용 권장."""

    categories: list[CategoryDef]
    settings: Settings
    llm: Optional[ChatOpenAI] = None

    @classmethod
    def from_settings(cls, settings: Settings, categories_path: Path | str | None = None) -> "CategoryClassifier":
        return cls(categories=load_categories(categories_path), settings=settings)

    def classify(
        self,
        title: str,
        file_type: str,
        source: str,
        summary: Optional[dict],
    ) -> ClassifyResult:
        doc_type = infer_doc_type(file_type, source)
        topics = (summary or {}).get("topics") or []
        tags = [str(t).strip() for t in topics if isinstance(t, str) and str(t).strip()][:MAX_TAG_COUNT]

        # 1) 룰 기반 매칭
        text = _build_match_text(title, topics)
        scored = [(c, _rule_score(text, c)) for c in self.categories if c.id != "other"]
        scored.sort(key=lambda x: -x[1])
        if scored and scored[0][1] > 0:
            top, hits = scored[0]
            confidence = round(min(1.0, hits / max(1, len(top.keywords)) * 1.5), 3)
            return ClassifyResult(
                doc_type=doc_type,
                category=top.id,
                confidence=confidence,
                tags=tags,
                method="rule",
            )

        # 2) LLM fallback (요약이 있는 경우만 의미 있음)
        if not summary:
            return ClassifyResult(doc_type=doc_type, category=None, confidence=None, tags=tags, method="fallback_unknown")

        cid, conf, method = _llm_classify(
            title=title, summary=summary, categories=self.categories,
            llm=self.llm, settings=self.settings,
        )
        if cid is None or conf < LLM_CONFIDENCE_FLOOR:
            return ClassifyResult(
                doc_type=doc_type,
                category=None if cid is None else cid,
                confidence=conf if cid else None,
                tags=tags,
                method=method,
            )
        return ClassifyResult(doc_type=doc_type, category=cid, confidence=conf, tags=tags, method=method)
