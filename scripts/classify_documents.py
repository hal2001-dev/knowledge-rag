#!/usr/bin/env python3
"""문서 자동 분류 일괄 실행 (TASK-015, ADR-025).

미분류 문서(`documents.category IS NULL`)를 순회해
- summary.topics + 제목으로 categories.yaml 키워드 매칭
- 매칭 0이면 LLM fallback (gpt-4o-mini, JSON mode)
- doc_type은 file_type/source 휴리스틱
- Postgres + Qdrant payload 동시 업데이트

사용 예시:
  python scripts/classify_documents.py
  python scripts/classify_documents.py --regenerate
  python scripts/classify_documents.py --dry-run
  python scripts/classify_documents.py --doc-id <uuid>
  python scripts/classify_documents.py --limit 5

결과 JSON: data/eval_runs/classification_<timestamp>.json
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

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from apps.config import get_settings  # noqa: E402
from packages.classifier import CategoryClassifier  # noqa: E402
from packages.code.logger import get_logger  # noqa: E402
from packages.db.connection import get_session, init_db  # noqa: E402
from packages.db.repository import (  # noqa: E402
    get_document,
    list_documents,
    list_documents_without_category,
    update_document_classification,
)
from packages.llm.chat import build_chat  # noqa: E402
from packages.llm.embeddings import build_embeddings  # noqa: E402
from packages.rag.sparse import SparseEmbedder  # noqa: E402
from packages.vectorstore.qdrant_store import QdrantDocumentStore  # noqa: E402

logger = get_logger(__name__)
DEFAULT_REPORT_DIR = ROOT / "data" / "eval_runs"


def _build_store(settings):
    embeddings = build_embeddings(settings)
    sparse = (
        SparseEmbedder(model_name=settings.sparse_model_name)
        if settings.search_mode == "hybrid"
        else None
    )
    return QdrantDocumentStore(
        url=settings.qdrant_url,
        collection=settings.qdrant_collection,
        embeddings=embeddings,
        search_mode=settings.search_mode,
        sparse_embedder=sparse,
    )


def _select_targets(db, args):
    if args.doc_id:
        rec = get_document(db, args.doc_id)
        if rec is None:
            print(f"문서를 찾을 수 없음: {args.doc_id}", file=sys.stderr)
            sys.exit(2)
        return [rec]
    if args.regenerate:
        return list_documents(db)
    return list_documents_without_category(db)


def main() -> None:
    parser = argparse.ArgumentParser(description="문서 자동 분류 일괄 실행")
    parser.add_argument("--doc-id", help="단일 문서만 처리")
    parser.add_argument("--regenerate", action="store_true",
                        help="이미 분류된 문서도 강제 재분류")
    parser.add_argument("--dry-run", action="store_true",
                        help="실제 DB·Qdrant 갱신 없이 결과만 출력")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--report")
    args = parser.parse_args()

    settings = get_settings()
    init_db(settings.postgres_url)

    started_at = datetime.now(timezone.utc)
    started_mono = time.monotonic()

    # store/llm은 dry-run에서도 categories.yaml 매칭이 LLM 미사용일 수 있어
    # 가능한 lazy로 초기화 — 일단 classifier 인스턴스만 만들어 둠
    classifier = CategoryClassifier.from_settings(settings)
    classifier.llm = None  # LLM은 fallback 시점에 lazy init

    store = None  # dry-run이면 끝까지 None
    if not args.dry_run:
        store = _build_store(settings)
        # llm은 fallback 시 build_chat이 호출됨 (classifier 내부) — 단 한 번만 빌드되도록 미리
        classifier.llm = build_chat(settings)

    db_gen = get_session()
    db = next(db_gen)
    try:
        targets = _select_targets(db, args)
        if args.limit > 0:
            targets = targets[: args.limit]

        print(
            f"[classify] 대상 {len(targets)}개 문서 "
            f"(regenerate={args.regenerate}, dry_run={args.dry_run})"
        )

        results: list[dict] = []
        ok = failed = 0
        method_counter = {"rule": 0, "llm": 0, "fallback_unknown": 0}

        for i, rec in enumerate(targets, start=1):
            t0 = time.monotonic()
            doc_id = rec.doc_id
            title = rec.title or doc_id
            print(f"  [{i}/{len(targets)}] {title!r} (doc_id={doc_id[:8]}…)", end=" ")

            try:
                result = classifier.classify(
                    title=title,
                    file_type=rec.file_type or "pdf",
                    source=rec.source or "",
                    summary=rec.summary,
                )
            except Exception as e:
                logger.warning(f"classify 예외 doc_id={doc_id}: {e}")
                results.append({"doc_id": doc_id, "title": title, "status": "failed", "error": str(e)})
                failed += 1
                print("→ FAIL")
                continue

            method_counter[result.method] = method_counter.get(result.method, 0) + 1

            if not args.dry_run:
                update_document_classification(
                    db, doc_id=doc_id,
                    doc_type=result.doc_type,
                    category=result.category,
                    category_confidence=result.confidence,
                    tags=result.tags,
                )
                if store is not None:
                    store.set_classification_payload(
                        doc_id=doc_id,
                        doc_type=result.doc_type,
                        category=result.category if result.category is not None else "",
                        tags=result.tags,
                    )

            elapsed_ms = int((time.monotonic() - t0) * 1000)
            results.append({
                "doc_id": doc_id, "title": title, "status": "ok",
                "doc_type": result.doc_type,
                "category": result.category,
                "confidence": result.confidence,
                "method": result.method,
                "tags": result.tags,
                "elapsed_ms": elapsed_ms,
            })
            ok += 1
            print(
                f"→ {result.method:>4} cat={result.category!s:<28} "
                f"conf={result.confidence!s:<5} doc_type={result.doc_type}"
            )

        finished_at = datetime.now(timezone.utc)
        elapsed_sec = round(time.monotonic() - started_mono, 2)

        report = {
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "elapsed_sec": elapsed_sec,
            "total": len(targets),
            "ok": ok,
            "failed": failed,
            "method_counts": method_counter,
            "regenerate": args.regenerate,
            "dry_run": args.dry_run,
            "results": results,
        }

        if not args.dry_run:
            DEFAULT_REPORT_DIR.mkdir(parents=True, exist_ok=True)
            ts = started_at.strftime("%Y-%m-%d_%H%M%S")
            report_path = Path(args.report) if args.report else DEFAULT_REPORT_DIR / f"classification_{ts}.json"
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"\n[classify] 리포트 저장: {report_path}")

        print(
            f"[classify] 완료 — total={len(targets)} ok={ok} failed={failed} "
            f"methods={method_counter} elapsed={elapsed_sec}s"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
