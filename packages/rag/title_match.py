"""질문 본문에 명시된 책/문서 제목을 implicit doc_filter로 매칭.

배경: chunk text에는 책 제목이 직접 들어가지 않으므로(heading_path만 prepend),
사용자가 "『2001 스페이스 오디세이』에서 HAL은?" 처럼 책 제목을 명시해도 retrieval이
다른 책의 정의문에 밀려 정작 본인이 원한 책 청크를 못 끌어오는 경우 발생.

해결: 질문 토큰을 정규화하고 모든 documents.title과 substring 매칭 → 가장 긴 매칭 1건이 있으면
해당 doc_id를 implicit doc_filter로 사용. 호출자가 explicit doc_filter/category/series_filter 중
하나라도 지정한 경우엔 우회.
"""
from __future__ import annotations

import re
import time

from sqlalchemy import text

from packages.code.logger import get_logger
from packages.db.connection import get_engine

logger = get_logger(__name__)

# 정규화: 공백·언더스코어·하이픈·점 → 단일 공백, 소문자, 다중 공백 압축
_NORMALIZE_RE = re.compile(r"[\s_\-\.·]+")
# 매칭 후보로 의미가 있을 만한 최소 정규화 길이 (영문 4자/한글 2자 이상)
_MIN_TITLE_LEN = 4

# 모듈 레벨 캐시 (TTL 60초). 색인이 잦지 않은 운영 환경에선 충분.
_TITLE_CACHE: list[tuple[str, str, str]] = []  # (doc_id, original_title, normalized_title)
_CACHE_TS = 0.0
_CACHE_TTL = 60.0


def _normalize(text_: str) -> str:
    if not text_:
        return ""
    return _NORMALIZE_RE.sub(" ", text_).lower().strip()


def _refresh_cache() -> None:
    global _TITLE_CACHE, _CACHE_TS
    engine = get_engine()
    with engine.connect() as c:
        rows = c.execute(text("SELECT doc_id, title FROM documents")).fetchall()
    _TITLE_CACHE = [
        (r.doc_id, r.title, _normalize(r.title))
        for r in rows
        if r.title and len(_normalize(r.title)) >= _MIN_TITLE_LEN
    ]
    _CACHE_TS = time.monotonic()


def detect_implicit_doc_filter(question: str) -> tuple[str, str] | None:
    """질문에 책 제목이 substring으로 들어 있으면 (doc_id, title)을 반환.

    여러 책이 매칭되면 가장 긴 정규화 제목 1건을 선택 (가장 구체적인 매칭).
    동률 시 None — 모호하므로 implicit filter를 적용하지 않음.
    """
    if not question:
        return None
    norm_q = _normalize(question)
    if not norm_q:
        return None

    if not _TITLE_CACHE or (time.monotonic() - _CACHE_TS) > _CACHE_TTL:
        try:
            _refresh_cache()
        except Exception as e:
            logger.warning(f"title cache refresh 실패: {e}")
            return None

    matches: list[tuple[str, str, int]] = []  # (doc_id, title, norm_len)
    for doc_id, title, norm_t in _TITLE_CACHE:
        if norm_t and norm_t in norm_q:
            matches.append((doc_id, title, len(norm_t)))

    if not matches:
        return None

    # 길이 desc로 정렬. 최장 매칭이 유일하면 채택, 동률이면 모호하다고 보고 None.
    matches.sort(key=lambda x: -x[2])
    longest = matches[0][2]
    top = [m for m in matches if m[2] == longest]
    if len(top) == 1:
        return (top[0][0], top[0][1])
    return None
