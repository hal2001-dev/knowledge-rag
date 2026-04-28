"""TASK-020 (ADR-029): 시리즈 휴리스틱 매처 단위 테스트.

DB 의존 없이 DocLite 입력만으로 검증.
"""
from __future__ import annotations

import pytest

from packages.series.matcher import (
    Confidence,
    DocLite,
    common_prefix,
    extract_volume_number,
    find_candidates,
)


# ─────────────────────────────────────────────────────
# extract_volume_number
# ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Chapter 12: Intro", 12),
        ("Ch.7 — Networking", 7),
        ("Vol 3", 3),
        ("Volume 21", 21),
        ("심연 위의 불길 1", 1),
        ("심연 위의 불길 2", 2),
        ("제 3권", 3),
        ("3권", 3),
        ("12편", 12),
        ("space-odyssey-vol02.pdf", 2),
        ("/Volumes/shared/series/book_03.pdf", 3),
        ("1st Edition", 1),
        # 4자리 연도는 권 번호가 아니어야 한다
        ("Released in 2024", None),
        # 권 번호 단서 없음
        ("Just a title", None),
        # 제목 중간 버전 번호("2.0.3")는 권 번호로 보지 않음 — 끝의 단어 차단
        ("ROS 2.0.3 Reference", None),
    ],
)
def test_extract_volume_number(text, expected):
    assert extract_volume_number(text) == expected


# ─────────────────────────────────────────────────────
# common_prefix
# ─────────────────────────────────────────────────────


def test_common_prefix_strips_volume_numbers():
    a = "심연 위의 불길 1"
    b = "심연 위의 불길 2"
    p = common_prefix(a, b)
    # 권 번호가 정규화로 제거되어야 prefix가 충분히 길어진다
    assert "심연 위의 불길" in p
    assert len(p) >= 8


def test_common_prefix_short_when_no_overlap():
    a = "ROS Programming"
    b = "Deep Learning"
    p = common_prefix(a, b)
    assert len(p) < 8


# ─────────────────────────────────────────────────────
# find_candidates
# ─────────────────────────────────────────────────────


def _doc(doc_id: str, title: str, source: str, doc_type: str = "book", **kw) -> DocLite:
    return DocLite(
        doc_id=doc_id,
        title=title,
        source=source,
        doc_type=doc_type,
        series_id=kw.get("series_id"),
        series_match_status=kw.get("series_match_status", "none"),
    )


def test_high_confidence_same_folder_and_volume_sequence():
    target = _doc("d1", "심연 위의 불길 1", "/series/danshim/심연_위의_불길_01.pdf")
    pop = [
        _doc("d2", "심연 위의 불길 2", "/series/danshim/심연_위의_불길_02.pdf"),
        _doc("d3", "심연 위의 불길 3", "/series/danshim/심연_위의_불길_03.pdf"),
    ]
    cand = find_candidates(target, pop)
    assert cand is not None
    assert cand.confidence == Confidence.HIGH
    assert cand.series_id is None  # 신규 시리즈
    assert "d2" in cand.members or "d3" in cand.members
    assert cand.volume_number == 1


def test_medium_confidence_same_folder_but_no_volume():
    target = _doc("d1", "ROS Robot Programming Guide", "/folder/a.pdf")
    pop = [_doc("d2", "ROS Robot Programming Reference", "/folder/b.pdf")]
    cand = find_candidates(target, pop)
    assert cand is not None
    # 같은 폴더 + 공통 prefix 충분 + 권 번호 없음 → MEDIUM
    assert cand.confidence == Confidence.MEDIUM


def test_low_confidence_no_folder_no_volume_long_prefix_only():
    target = _doc("d1", "Distributed Systems Concepts", "/folder1/a.pdf")
    pop = [_doc("d2", "Distributed Systems Patterns", "/folder2/b.pdf")]
    cand = find_candidates(target, pop)
    assert cand is not None
    assert cand.confidence == Confidence.LOW


def test_no_candidate_when_prefix_too_short():
    target = _doc("d1", "ROS", "/folder/a.pdf")
    pop = [_doc("d2", "Deep Learning", "/folder/b.pdf")]
    cand = find_candidates(target, pop)
    assert cand is None


def test_skip_rejected_target():
    target = _doc("d1", "심연 위의 불길 1", "/series/a.pdf", series_match_status="rejected")
    pop = [_doc("d2", "심연 위의 불길 2", "/series/b.pdf")]
    cand = find_candidates(target, pop)
    assert cand is None


def test_skip_rejected_peer():
    target = _doc("d1", "심연 위의 불길 1", "/series/a.pdf")
    pop = [_doc("d2", "심연 위의 불길 2", "/series/b.pdf", series_match_status="rejected")]
    cand = find_candidates(target, pop)
    # rejected peer는 풀에서 제외되므로 후보 없음
    assert cand is None


def test_attach_to_existing_series():
    target = _doc("d1", "심연 위의 불길 5", "/series/danshim/05.pdf")
    pop = [
        _doc("d2", "심연 위의 불길 1", "/series/danshim/01.pdf", series_id="ser_abc"),
        _doc("d3", "심연 위의 불길 2", "/series/danshim/02.pdf", series_id="ser_abc"),
    ]
    cand = find_candidates(target, pop)
    assert cand is not None
    assert cand.series_id == "ser_abc"  # 기존 시리즈에 합치기
    assert cand.confidence == Confidence.HIGH
    assert cand.volume_number == 5


def test_doc_type_must_match():
    target = _doc("d1", "심연 위의 불길 1", "/series/a.pdf", doc_type="book")
    pop = [_doc("d2", "심연 위의 불길 2", "/series/b.pdf", doc_type="article")]
    cand = find_candidates(target, pop)
    # doc_type 다르면 풀에서 제외 → 후보 없음
    assert cand is None


def test_self_excluded_from_population():
    target = _doc("d1", "심연 위의 불길 1", "/series/a.pdf")
    pop = [_doc("d1", "심연 위의 불길 1", "/series/a.pdf")]  # 자기 자신
    cand = find_candidates(target, pop)
    assert cand is None
