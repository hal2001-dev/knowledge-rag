"""TASK-020 (ADR-029): 시리즈 휴리스틱 매처.

문서가 인덱싱될 때 같은 저작의 다른 챕터·권을 찾아 시리즈로 묶을 후보를 산출한다.

휴리스틱 (사용자 합의):
- 동일 source 폴더(상위 디렉터리 동일)
- 공통 prefix ≥ 8자 (정규화된 제목 기준)
- 동일 doc_type
- 숫자 시퀀스 추출 가능 (Chapter N / Vol N / 단순 번호 / 'Nth')

신뢰도:
- High   = 4조건 모두 만족 → 자동 묶기 (auto_attached)
- Medium = 3조건 만족 (숫자 시퀀스 또는 폴더 누락 허용) → 검수 큐 (suggested)
- Low    = 그 외 → 처리 없음 (none)

LLM/임베딩 호출 없음 — 규칙 기반.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class SeriesCandidate:
    """매처 결과 — find_candidates가 반환하는 단일 후보.

    series_id: 기존 시리즈와 매칭됐다면 그 id, 신규면 None (호출자가 발급)
    members: 동일 묶음 후보 doc_id (자기 자신 포함)
    series_title: 공통 prefix 기반 제안 제목 (호출자가 수정 가능)
    volume_number: 자기 문서의 권 번호 추정 (없으면 None)
    confidence: high|medium|low — 인덱서 워커가 분기 기준으로 사용
    """
    series_id: Optional[str]
    members: list[str]
    series_title: str
    volume_number: Optional[int]
    confidence: Confidence


# ─────────────────────────────────────────────────────
# 정규화 + 보조 함수
# ─────────────────────────────────────────────────────


_VOL_PATTERNS = [
    # "Chapter 12", "Ch.12", "ch12"
    re.compile(r"chapter\s*(\d{1,3})", re.IGNORECASE),
    re.compile(r"\bch\.?\s*(\d{1,3})\b", re.IGNORECASE),
    # "Vol 3", "Volume 3", "volume3"
    re.compile(r"\bvol\.?(?:ume)?\s*(\d{1,3})\b", re.IGNORECASE),
    # 한국어 "1권", "제 3권", "12부"
    re.compile(r"제?\s*(\d{1,3})\s*[권부편장]"),
    # 12편, 12장 등 어절 끝 숫자
    # 일반 끝 숫자 — "TitleName 03", "TitleName 3"
    re.compile(r"\s(\d{1,3})\s*$"),
    # 파일 이름 끝의 _01, -01
    re.compile(r"[\s_\-](\d{1,3})(?:\.[A-Za-z0-9]{1,5})?$"),
    # 순서 표현 "1st", "2nd" — 영어
    re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)\b", re.IGNORECASE),
]


def extract_volume_number(text: str) -> Optional[int]:
    """제목/파일명에서 권 번호를 추출. 첫 매칭만 사용."""
    if not text:
        return None
    for pat in _VOL_PATTERNS:
        m = pat.search(text)
        if m:
            try:
                n = int(m.group(1))
            except (ValueError, IndexError):
                continue
            # 1900년대·2000년대 같은 4자리 연도는 권 번호로 보지 않음
            if 1 <= n <= 999:
                return n
    return None


def _normalize_for_prefix(text: str) -> str:
    """제목 prefix 비교용 정규화.

    - 소문자
    - 공백·구두점 압축
    - 권 번호 패턴(Chapter N / Vol N / N권 / N장 / 끝의 숫자) 제거
    공통 prefix 길이가 권 번호 차이 때문에 짧아지는 것을 막는다.
    """
    if not text:
        return ""
    t = text.lower().strip()
    # 권 번호 패턴 제거 (extract와 같은 패턴 사용)
    for pat in _VOL_PATTERNS:
        t = pat.sub(" ", t)
    # 다중 공백·구두점 정규화
    t = re.sub(r"[\s\W_]+", " ", t, flags=re.UNICODE).strip()
    return t


def common_prefix(a: str, b: str) -> str:
    """두 문자열의 공통 prefix를 정규화 후 반환. 단어 경계까지만 잘라 자연스러움 유지."""
    na, nb = _normalize_for_prefix(a), _normalize_for_prefix(b)
    if not na or not nb:
        return ""
    n = min(len(na), len(nb))
    i = 0
    while i < n and na[i] == nb[i]:
        i += 1
    prefix = na[:i].rstrip()
    # 마지막 토큰이 잘렸다면 앞 단어 경계까지만 (예: "ros progr" → "ros")
    if i < len(na) and na[i].strip() and i > 0 and not na[i - 1].isspace():
        last_space = prefix.rfind(" ")
        if last_space >= 0:
            prefix = prefix[:last_space].rstrip()
    return prefix


# ─────────────────────────────────────────────────────
# DocLite — repository 의존 회피용 가벼운 dict 래퍼
# ─────────────────────────────────────────────────────


@dataclass
class DocLite:
    """매처 입력 — DB ORM 객체 의존 없는 가벼운 표현. 테스트에서도 그대로 사용."""
    doc_id: str
    title: str
    source: str
    doc_type: str
    series_id: Optional[str] = None
    series_match_status: str = "none"


def _same_folder(a: str, b: str) -> bool:
    """source 경로 두 개가 같은 부모 폴더에 속하는가."""
    if not a or not b:
        return False
    # source가 URL이면 폴더 비교 의미 없음. 파일 경로만 사용.
    da = os.path.dirname(a) if a else ""
    db = os.path.dirname(b) if b else ""
    if not da or not db:
        return False
    return os.path.normpath(da) == os.path.normpath(db)


# ─────────────────────────────────────────────────────
# 핵심 — 후보 산출
# ─────────────────────────────────────────────────────


PREFIX_MIN_LEN = 8


def find_candidates(
    target: DocLite,
    population: Iterable[DocLite],
) -> Optional[SeriesCandidate]:
    """target 문서에 대해 population에서 시리즈 후보를 찾는다.

    population: 인덱스 전체 또는 같은 doc_type 사전 필터링된 부분집합.
    target.series_match_status == 'rejected' 이면 None (재바인딩 차단).
    target 자신은 자동 제외.
    """
    if target.series_match_status == "rejected":
        return None

    # 같은 doc_type 후보 + 자기 제외 + rejected 제외
    pool = [
        d for d in population
        if d.doc_id != target.doc_id
        and d.doc_type == target.doc_type
        and d.series_match_status != "rejected"
    ]
    if not pool:
        return None

    target_vol = extract_volume_number(target.title) or extract_volume_number(target.source)

    # ── 1차: 이미 묶인 series_id 후보군 우선 (기존 시리즈에 합치기)
    by_series: dict[str, list[DocLite]] = {}
    for d in pool:
        if d.series_id:
            by_series.setdefault(d.series_id, []).append(d)

    for sid, members in by_series.items():
        sample = members[0]
        prefix = common_prefix(target.title, sample.title)
        if len(prefix) < PREFIX_MIN_LEN:
            continue
        same_folder = _same_folder(target.source, sample.source)
        sample_vol = extract_volume_number(sample.title) or extract_volume_number(sample.source)
        has_seq = target_vol is not None and sample_vol is not None
        # high: 같은 폴더 + 권 번호 시퀀스 모두 만족
        if same_folder and has_seq:
            return SeriesCandidate(
                series_id=sid,
                members=[target.doc_id] + [m.doc_id for m in members],
                series_title=prefix,
                volume_number=target_vol,
                confidence=Confidence.HIGH,
            )
        # medium: 폴더 또는 권 번호 중 하나라도 결여
        return SeriesCandidate(
            series_id=sid,
            members=[target.doc_id] + [m.doc_id for m in members],
            series_title=prefix,
            volume_number=target_vol,
            confidence=Confidence.MEDIUM,
        )

    # ── 2차: 신규 시리즈 후보 — 묶이지 않은 문서 사이에서 best match
    best: Optional[tuple[DocLite, str, bool, bool]] = None  # (peer, prefix, same_folder, has_seq)
    for d in pool:
        if d.series_id:
            continue
        prefix = common_prefix(target.title, d.title)
        if len(prefix) < PREFIX_MIN_LEN:
            continue
        same_folder = _same_folder(target.source, d.source)
        peer_vol = extract_volume_number(d.title) or extract_volume_number(d.source)
        has_seq = target_vol is not None and peer_vol is not None
        score = len(prefix) + (10 if same_folder else 0) + (10 if has_seq else 0)
        if best is None or score > _score(best):
            best = (d, prefix, same_folder, has_seq)

    if best is None:
        return None
    peer, prefix, same_folder, has_seq = best
    if same_folder and has_seq:
        confidence = Confidence.HIGH
    elif same_folder or has_seq:
        confidence = Confidence.MEDIUM
    else:
        confidence = Confidence.LOW

    return SeriesCandidate(
        series_id=None,  # 신규 시리즈 → 호출자가 series_id 발급
        members=[target.doc_id, peer.doc_id],
        series_title=prefix,
        volume_number=target_vol,
        confidence=confidence,
    )


def _score(t: tuple[DocLite, str, bool, bool]) -> int:
    _peer, prefix, same_folder, has_seq = t
    return len(prefix) + (10 if same_folder else 0) + (10 if has_seq else 0)
