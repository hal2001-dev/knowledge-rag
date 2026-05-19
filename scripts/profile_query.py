#!/usr/bin/env python3
"""
단발 진단: 하나의 질의에 대해 embed/sparse/qdrant/rerank/LLM 각 구간 ms 측정.

같은 질의를 2회 돌리고 2회차(warm)를 보고한다 — 1회차는 cold start 비용 포함.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

from apps.config import get_settings
from packages.llm.embeddings import build_embeddings
from packages.llm.chat import build_chat
from packages.rag.generator import generate
from packages.rag.reranker import get_reranker
from packages.rag.sparse import SparseEmbedder
from packages.vectorstore.qdrant_store import QdrantDocumentStore
from qdrant_client.models import SparseVector


def profile_once(*, store, embeddings, sparse, reranker, llm, query, initial_k, top_n, score_threshold):
    timings = {}

    t = time.monotonic()
    dense_q = embeddings.embed_query(query)
    timings["embed_dense_ms"] = int((time.monotonic() - t) * 1000)

    t = time.monotonic()
    sparse_q = sparse.embed_query(query)
    timings["embed_sparse_ms"] = int((time.monotonic() - t) * 1000)

    # qdrant hybrid search — store.similarity_search_with_score 내부와 동일한 호출 흉내내기
    # 하지만 단순화를 위해 store API를 그대로 호출(임베딩 중복은 무시 가능 — 캐시 없음이라 동일 비용 2배)
    # 더 정확한 측정 위해 raw client 사용 가능하지만 일단 store API로 충분 비교
    t = time.monotonic()
    candidates = store.similarity_search_with_score(
        query=query,
        k=initial_k,
        score_threshold=score_threshold,
    )
    timings["retrieve_total_ms"] = int((time.monotonic() - t) * 1000)
    timings["candidates"] = len(candidates)

    t = time.monotonic()
    hits = reranker.rerank(query=query, candidates=candidates, top_n=top_n)
    timings["rerank_ms"] = int((time.monotonic() - t) * 1000)
    timings["hits"] = len(hits)

    t = time.monotonic()
    gen_result = generate(
        llm=llm,
        question=query,
        chunks=hits,
        history=None,
    )
    timings["generate_ms"] = int((time.monotonic() - t) * 1000)
    timings["answer_chars"] = len(gen_result["answer"])

    timings["total_observed_ms"] = (
        timings["retrieve_total_ms"] + timings["rerank_ms"] + timings["generate_ms"]
    )
    return timings, gen_result["answer"]


def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "ROS의 주요 구성요소는?"

    settings = get_settings()
    print(f"query: {query!r}")
    print(f"llm_backend={settings.llm_backend} model={settings.llm_model or settings.openai_chat_model}")
    print(f"reranker={settings.reranker_backend} search_mode={settings.search_mode}\n")

    emb = build_embeddings(settings)
    sparse = SparseEmbedder(model_name=settings.sparse_model_name) if settings.search_mode == "hybrid" else None
    store = QdrantDocumentStore(
        url=settings.qdrant_url,
        collection=settings.qdrant_collection,
        embeddings=emb,
        search_mode=settings.search_mode,
        sparse_embedder=sparse,
    )
    llm = build_chat(settings)
    reranker = get_reranker(backend=settings.reranker_backend)

    common = dict(
        store=store, embeddings=emb, sparse=sparse, reranker=reranker, llm=llm,
        query=query,
        initial_k=settings.default_initial_k,
        top_n=settings.default_top_k,
        score_threshold=settings.default_score_threshold,
    )

    print("[run 1 / cold] ...")
    t1, _ = profile_once(**common)
    for k, v in t1.items():
        print(f"  {k:>22}: {v}")

    print("\n[run 2 / warm] ...")
    t2, ans2 = profile_once(**common)
    for k, v in t2.items():
        print(f"  {k:>22}: {v}")

    print(f"\n--- answer preview (warm) ---\n{ans2[:400]}")


if __name__ == "__main__":
    main()
