#!/usr/bin/env python3
"""
Phase 1 평가: Retrieval 정량 지표 측정.

사용법:
  python scripts/bench_retrieval.py                    # 현재 .env backend로 실행
  python scripts/bench_retrieval.py --backend flashrank bge-m3  # A/B 비교

지표:
  Hit@K         : top-K 안에 정답 doc가 하나라도 들어있으면 1
  Precision@K   : top-K 중 정답 doc_id 비율
  Recall@K      : 정답 doc_id 중 top-K에 들어온 비율
  MRR           : 1 / (첫 정답의 rank). 없으면 0
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

from apps.config import get_settings
from packages.llm.embeddings import build_embeddings
from packages.rag.reranker import get_reranker
from packages.rag.retriever import retrieve
from packages.vectorstore.qdrant_store import QdrantDocumentStore


def load_dataset(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def score_one(retrieved_doc_ids: list[str], expected_doc_ids: set[str], k: int) -> dict:
    """
    청크 기반 retrieval을 document 기준으로 환산해 지표 계산.
    같은 doc의 청크가 top-K에 여러 개 들어올 수 있으므로 unique 처리.
    """
    topk = retrieved_doc_ids[:k]
    hits = [d in expected_doc_ids for d in topk]  # MRR용 순서 보존
    unique_topk = list(dict.fromkeys(topk))       # 순서 유지 dedupe
    unique_hits = [d in expected_doc_ids for d in unique_topk]

    hit_at_k = 1.0 if any(hits) else 0.0
    precision = sum(unique_hits) / len(unique_topk) if unique_topk else 0.0
    recall = (
        len(set(unique_topk) & expected_doc_ids) / len(expected_doc_ids)
        if expected_doc_ids else 0.0
    )
    mrr = 0.0
    for rank, h in enumerate(hits, 1):
        if h:
            mrr = 1.0 / rank
            break
    return {"hit@k": hit_at_k, "precision": precision, "recall": recall, "mrr": mrr}


def run_backend(backend: str, dataset: list[dict], k: int, initial_k: int, settings) -> dict:
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
    reranker = get_reranker(backend=backend)
    # warm-up
    from packages.code.models import ScoredChunk
    reranker.rerank("warmup", [ScoredChunk(content="warmup", metadata={}, score=0.0)], top_n=1)

    per_query = []
    aggregate = {"hit@k": 0.0, "precision": 0.0, "recall": 0.0, "mrr": 0.0, "latency_ms": 0.0}
    for row in dataset:
        start = time.monotonic()
        chunks = retrieve(
            store=store,
            query=row["question"],
            reranker=reranker,
            initial_k=initial_k,
            top_n=k,
            score_threshold=0.0,
        )
        latency_ms = int((time.monotonic() - start) * 1000)
        doc_ids = [c.metadata.get("doc_id") for c in chunks]
        metrics = score_one(doc_ids, set(row["expected_doc_ids"]), k)
        metrics["latency_ms"] = latency_ms

        per_query.append({
            "id": row["id"],
            "question": row["question"],
            "language": row.get("language"),
            "expected_doc_ids": row["expected_doc_ids"],
            "retrieved_doc_ids": doc_ids,
            **metrics,
        })
        for key in aggregate:
            aggregate[key] += metrics[key]

    n = len(dataset) or 1
    for key in aggregate:
        aggregate[key] = round(aggregate[key] / n, 4)

    return {"backend": backend, "aggregate": aggregate, "per_query": per_query}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(ROOT / "tests/eval/dataset.jsonl"))
    parser.add_argument("--backend", nargs="+", default=None,
                        help="재순위 backend 한두 개 지정. 미지정시 .env의 RERANKER_BACKEND만")
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--initial-k", type=int, default=20)
    parser.add_argument("--out-dir", default=str(ROOT / "data/eval_runs"))
    args = parser.parse_args()

    settings = get_settings()
    dataset = load_dataset(Path(args.dataset))
    backends = args.backend or [settings.reranker_backend]

    print(f"dataset: {args.dataset} ({len(dataset)}개 질의), k={args.k}, initial_k={args.initial_k}")
    print(f"backends: {backends}\n")

    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"retrieval_{run_id}.json"

    runs = []
    for backend in backends:
        print(f"=== {backend} ===")
        result = run_backend(backend, dataset, args.k, args.initial_k, settings)
        runs.append(result)
        agg = result["aggregate"]
        print(f"  Hit@{args.k}     : {agg['hit@k']:.3f}")
        print(f"  Precision@{args.k}: {agg['precision']:.3f}")
        print(f"  Recall@{args.k}   : {agg['recall']:.3f}")
        print(f"  MRR          : {agg['mrr']:.3f}")
        print(f"  avg latency  : {agg['latency_ms']:.0f}ms")
        print()

    # 질의별 비교 표 (backend가 2개 이상일 때)
    if len(runs) >= 2:
        print("=== 질의별 Hit@K 비교 ===")
        header = "id   " + " ".join(f"{r['backend']:>12}" for r in runs) + "  lang  question"
        print(header)
        for i, row in enumerate(runs[0]["per_query"]):
            vals = " ".join(f"{r['per_query'][i]['hit@k']:>12.1f}" for r in runs)
            lang = row.get("language", "")[:5]
            q = row["question"][:50]
            print(f"{row['id']}  {vals}  {lang:>5}  {q}")

    out_path.write_text(json.dumps({"run_id": run_id, "k": args.k, "runs": runs},
                                   indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n저장: {out_path}")


if __name__ == "__main__":
    main()
