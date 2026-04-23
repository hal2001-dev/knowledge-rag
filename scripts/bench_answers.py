#!/usr/bin/env python3
"""
Phase 2 평가: Ragas 답변 품질 측정.

사용법:
  python scripts/bench_answers.py
  python scripts/bench_answers.py --limit 5     # 빠른 스모크

지표 (Ragas):
  faithfulness         : 답변이 retrieved context에 근거하는 정도
  answer_relevancy     : 답변이 질문에 관련된 정도
  context_precision    : 가져온 context 중 정답에 기여한 비율
  context_recall       : 정답 대비 context가 얼마나 커버하는가

비용: 질의 N개 × 지표 4개 × 평균 2~3회 LLM 호출. N=12이면 약 100~150 API call.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
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
from packages.rag.retriever import retrieve
from packages.vectorstore.qdrant_store import QdrantDocumentStore


def load_dataset(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _build_stack(settings):
    """retrieve를 직접 호출할 수 있도록 store·llm·reranker만 반환 (pipeline 우회)."""
    emb = build_embeddings(settings)
    sparse = None
    if settings.search_mode == "hybrid":
        from packages.rag.sparse import SparseEmbedder
        sparse = SparseEmbedder(model_name=settings.sparse_model_name)
    store = QdrantDocumentStore(
        url=settings.qdrant_url,
        collection=settings.qdrant_collection,
        embeddings=emb,
        search_mode=settings.search_mode,
        sparse_embedder=sparse,
    )
    llm = build_chat(settings)
    reranker = get_reranker(backend=settings.reranker_backend)
    return store, llm, reranker


def _collect_samples(store, llm, reranker, dataset: list[dict], settings) -> list[dict]:
    """각 질의에 대해 (question, answer, full-context chunks, reference) 수집.

    pipeline.query를 쓰면 sources에 200자 excerpt만 남아 Ragas faithfulness가
    context 부족으로 낮게 평가된다. 여기서는 retrieve/generate를 직접 호출해
    전체 청크 content를 Ragas에 전달한다.
    """
    import time
    samples = []
    for row in dataset:
        t0 = time.monotonic()
        chunks = retrieve(
            store=store,
            query=row["question"],
            reranker=reranker,
            initial_k=settings.default_initial_k,
            top_n=settings.default_top_k,
            score_threshold=settings.default_score_threshold,
        )
        if not chunks:
            answer = "관련 문서를 찾지 못했습니다."
            full_contexts = []
        else:
            answer = generate(llm=llm, question=row["question"], chunks=chunks, history=None)
            full_contexts = [c.content for c in chunks]
        latency_ms = int((time.monotonic() - t0) * 1000)

        samples.append({
            "id": row["id"],
            "user_input": row["question"],
            "response": answer,
            "retrieved_contexts": full_contexts,
            "retrieved_doc_ids": [c.metadata.get("doc_id") for c in chunks],
            "reference": row.get("reference", ""),
            "expected_doc_ids": row["expected_doc_ids"],
            "language": row.get("language"),
            "latency_ms": latency_ms,
        })
    return samples


def _ragas_evaluate(samples: list[dict], judge_model: str) -> dict:
    """
    Ragas 0.4 API로 평가.
    reference가 없는 샘플은 context_recall이 NaN이 될 수 있음 — 전체 dataset을 돌리되 평균에서 제외.
    """
    from ragas import EvaluationDataset, evaluate
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.metrics import (
        Faithfulness,
        ResponseRelevancy,
        LLMContextPrecisionWithoutReference,
        LLMContextRecall,
    )
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings

    ragas_samples = []
    for s in samples:
        ragas_samples.append({
            "user_input": s["user_input"],
            "response": s["response"],
            "retrieved_contexts": s["retrieved_contexts"] or ["(empty)"],
            "reference": s["reference"] or s["response"],  # 없으면 self-reference (context_recall 무의미 → 해석 주의)
        })
    ds = EvaluationDataset.from_list(ragas_samples)

    judge_llm = LangchainLLMWrapper(
        ChatOpenAI(model=judge_model, temperature=0.0)
    )
    judge_emb = LangchainEmbeddingsWrapper(OpenAIEmbeddings(model="text-embedding-3-small"))

    metrics = [
        Faithfulness(llm=judge_llm),
        ResponseRelevancy(llm=judge_llm, embeddings=judge_emb),
        LLMContextPrecisionWithoutReference(llm=judge_llm),
        LLMContextRecall(llm=judge_llm),
    ]

    return evaluate(dataset=ds, metrics=metrics).to_pandas().to_dict(orient="list")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(ROOT / "tests/eval/dataset.jsonl"))
    parser.add_argument("--limit", type=int, default=None, help="처음 N개만 평가 (스모크용)")
    parser.add_argument("--judge-model", default="gpt-4o-mini")
    parser.add_argument("--out-dir", default=str(ROOT / "data/eval_runs"))
    args = parser.parse_args()

    # Ragas가 LangSmith 트레이스를 자동 집계하도록 env 확인
    if not os.environ.get("LANGCHAIN_API_KEY"):
        settings = get_settings()
        if settings.langchain_tracing_v2 and settings.langchain_api_key:
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
            os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project

    settings = get_settings()
    dataset = load_dataset(Path(args.dataset))
    if args.limit:
        dataset = dataset[: args.limit]

    print(f"dataset: {args.dataset} ({len(dataset)}개)")
    print(f"LLM backend: {settings.llm_backend}, reranker: {settings.reranker_backend}")
    print(f"judge: {args.judge_model}\n")

    store, llm, reranker = _build_stack(settings)

    print("샘플 수집 중...")
    samples = _collect_samples(store, llm, reranker, dataset, settings)

    print(f"Ragas 평가 실행 중 (LLM call ≈ {len(samples) * 10}회)...")
    scores = _ragas_evaluate(samples, judge_model=args.judge_model)

    # 평균 집계 (NaN 제외)
    import math
    def _mean(xs):
        vals = [x for x in xs if isinstance(x, (int, float)) and not math.isnan(x)]
        return round(sum(vals) / len(vals), 4) if vals else None

    aggregate = {}
    for col, vals in scores.items():
        if col in ("user_input", "response", "retrieved_contexts", "reference"):
            continue
        aggregate[col] = _mean(vals)

    print("\n=== 집계 ===")
    for k, v in aggregate.items():
        print(f"  {k}: {v}")

    # 저장
    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"answers_{run_id}.json"
    out_path.write_text(
        json.dumps({
            "run_id": run_id,
            "settings": {
                "llm_backend": settings.llm_backend,
                "llm_model": settings.llm_model or settings.openai_chat_model,
                "reranker_backend": settings.reranker_backend,
                "judge_model": args.judge_model,
            },
            "aggregate": aggregate,
            "samples": samples,
            "per_query_scores": scores,
        }, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(f"\n저장: {out_path}")
    print("(LangSmith 트레이스가 활성화되어 있으면 대시보드에서 'knowledge-rag' 프로젝트에 실행 이력이 남습니다)")


if __name__ == "__main__":
    main()
