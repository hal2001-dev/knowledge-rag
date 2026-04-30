"""TASK-022 (ADR-035): heading prefix 동반 검색 단위 테스트.

retriever.retrieve()의 expand 옵션이 reranker 통과한 hit 청크의 heading_path
prefix를 공유하는 인접 청크를 companion으로 동반시키는지 검증한다. Qdrant
호출은 mock으로 대체하고 retriever의 동반·중복·exclude·heading_path 비어있는
경우 분기를 격리해서 본다.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from packages.code.models import ScoredChunk
from packages.rag.retriever import retrieve


def _hit(doc_id: str, chunk_index: int, heading_path: list[str], score: float = 0.9) -> ScoredChunk:
    return ScoredChunk(
        content=f"hit content {doc_id}/{chunk_index}",
        metadata={
            "doc_id": doc_id,
            "chunk_index": chunk_index,
            "heading_path": heading_path,
            "title": "T",
            "page": chunk_index,
        },
        score=score,
    )


def _companion(doc_id: str, chunk_index: int, heading_path: list[str]) -> ScoredChunk:
    return ScoredChunk(
        content=f"companion {doc_id}/{chunk_index}",
        metadata={
            "doc_id": doc_id,
            "chunk_index": chunk_index,
            "heading_path": heading_path,
            "title": "T",
            "page": chunk_index,
        },
        score=0.0,
    )


def _stub_store(scroll_returns: list[list[ScoredChunk]]) -> MagicMock:
    """similarity_search_with_score는 단일 hit를 통과시키고, scroll_by_heading_prefix는
    hit별로 미리 준비된 list를 차례로 반환하도록 stub.
    """
    store = MagicMock()
    # similarity_search_with_score는 reranker가 그대로 통과시킬 후보들을 반환
    store.similarity_search_with_score.return_value = ["candidate"]
    store.scroll_by_heading_prefix.side_effect = scroll_returns
    return store


def _stub_reranker(hits: list[ScoredChunk]) -> MagicMock:
    rer = MagicMock()
    rer.rerank.return_value = hits
    return rer


def test_expand_disabled_returns_only_hits():
    """expand_enabled=False면 companion 0건, scroll 호출 없음 (회귀 보호)."""
    hit = _hit("doc-A", 5, ["31장", "31.10 vi 키맵"])
    store = _stub_store([])
    rer = _stub_reranker([hit])

    out = retrieve(store=store, query="q", reranker=rer, expand_enabled=False)

    assert out == [hit]
    store.scroll_by_heading_prefix.assert_not_called()


def test_expand_attaches_companions_with_marking():
    """depth=1로 hit의 첫 토큰("31장")을 공유하는 인접 청크 2개 동반.

    companion에 metadata.companion=True 마킹, score=0.0 유지, hit는 list 앞쪽에 보존.
    """
    hit = _hit("doc-A", 5, ["31장", "31.10 vi 키맵"])
    neighbors = [
        _companion("doc-A", 4, ["31장", "31.9 매크로"]),
        _companion("doc-A", 6, ["31장", "31.11 매핑"]),
    ]
    store = _stub_store([neighbors])
    rer = _stub_reranker([hit])

    out = retrieve(
        store=store, query="q", reranker=rer,
        expand_enabled=True, expand_prefix_depth=1, expand_neighbors=2,
    )

    assert out[0] is hit
    assert len(out) == 3
    for c in out[1:]:
        assert c.metadata["companion"] is True
        assert c.score == 0.0
    # scroll 호출 인자 확인 — prefix_tokens=heading_path[:1], exclude에 hit 자기 자신 포함
    store.scroll_by_heading_prefix.assert_called_once()
    call = store.scroll_by_heading_prefix.call_args
    assert call.kwargs["doc_id"] == "doc-A"
    assert call.kwargs["prefix_tokens"] == ["31장"]
    assert 5 in call.kwargs["exclude_chunk_indices"]
    assert call.kwargs["limit"] == 2


def test_expand_depth_zero_is_noop():
    """depth=0이면 expand 의미 없음 — scroll 호출 없이 hit만 반환."""
    hit = _hit("doc-A", 5, ["31장", "31.10"])
    store = _stub_store([])
    rer = _stub_reranker([hit])

    out = retrieve(
        store=store, query="q", reranker=rer,
        expand_enabled=True, expand_prefix_depth=0, expand_neighbors=2,
    )

    assert out == [hit]
    store.scroll_by_heading_prefix.assert_not_called()


def test_empty_heading_path_skips_expand_for_that_hit():
    """heading_path가 비어 있는 hit는 동반 회수 대상에서 자연 제외."""
    hit_no_heading = _hit("doc-A", 5, [])
    hit_with_heading = _hit("doc-B", 1, ["1장"])
    neighbors_b = [_companion("doc-B", 2, ["1장", "1.1"])]
    # hit_no_heading은 prefix_tokens가 비어 scroll 호출 자체가 없음 → side_effect는 1번만 소비
    store = _stub_store([neighbors_b])
    rer = _stub_reranker([hit_no_heading, hit_with_heading])

    out = retrieve(
        store=store, query="q", reranker=rer,
        expand_enabled=True, expand_prefix_depth=1, expand_neighbors=2,
    )

    assert out[0] is hit_no_heading
    assert out[1] is hit_with_heading
    # companion은 hit_with_heading 쪽에서 1개만 추가
    assert len(out) == 3
    assert out[2].metadata["companion"] is True
    assert out[2].metadata["doc_id"] == "doc-B"
    # scroll 호출은 정확히 1번 (heading 있는 hit만)
    assert store.scroll_by_heading_prefix.call_count == 1


def test_dedup_across_hits_and_companions():
    """두 hit가 같은 prefix를 공유해 같은 인접 청크가 중복 회수돼도 1번만 append.

    또한 hit 자기 자신이 다른 hit의 companion 후보로 잡히는 경우도 차단.
    """
    hit1 = _hit("doc-A", 5, ["31장", "31.10"])
    hit2 = _hit("doc-A", 7, ["31장", "31.12"])
    # hit1의 scroll은 hit2(중복) + 신규 1개 → hit2는 이미 hits 안에 있어 제외돼야 함
    scroll_for_hit1 = [
        _companion("doc-A", 7, ["31장", "31.12"]),  # hit2 중복 — 제외돼야 함
        _companion("doc-A", 4, ["31장", "31.9"]),   # 신규 — 추가
    ]
    # hit2의 scroll은 hit1(이미 hits) + 방금 추가된 4(이미 companion) + 신규 9
    scroll_for_hit2 = [
        _companion("doc-A", 5, ["31장", "31.10"]),  # hit1 — 제외
        _companion("doc-A", 4, ["31장", "31.9"]),   # 방금 추가된 companion — 제외
        _companion("doc-A", 9, ["31장", "31.13"]),  # 신규 — 추가
    ]
    store = _stub_store([scroll_for_hit1, scroll_for_hit2])
    rer = _stub_reranker([hit1, hit2])

    out = retrieve(
        store=store, query="q", reranker=rer,
        expand_enabled=True, expand_prefix_depth=1, expand_neighbors=3,
    )

    # 기대: [hit1, hit2, companion(4), companion(9)] — 중복 0
    assert out[0] is hit1
    assert out[1] is hit2
    companion_indices = sorted(c.metadata["chunk_index"] for c in out[2:])
    assert companion_indices == [4, 9]
    assert all(c.metadata.get("companion") for c in out[2:])
