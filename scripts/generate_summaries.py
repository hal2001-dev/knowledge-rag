#!/usr/bin/env python3
"""문서 요약 일괄 생성 CLI (TASK-014, ADR-024).

미요약 문서(`documents.summary IS NULL`)를 순회해 LLM 호출로 요약을 만들어 DB에 저장한다.
실패는 격리하고 최종 리포트(JSON)에 누적한다. 재실행 안전(이미 요약된 문서는 자동 skip,
`--regenerate`로 강제 재생성).

사용 예시:
  python scripts/generate_summaries.py
  python scripts/generate_summaries.py --doc-id <uuid>
  python scripts/generate_summaries.py --regenerate
  python scripts/generate_summaries.py --dry-run
  python scripts/generate_summaries.py --limit 5

결과 JSON: data/eval_runs/summaries_<timestamp>.json
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
from packages.code.logger import get_logger  # noqa: E402
from packages.db.connection import get_session, init_db  # noqa: E402
from packages.db.repository import (  # noqa: E402
    get_document,
    list_documents,
    list_documents_without_summary,
    update_document_summary,
)
from packages.llm.chat import build_chat  # noqa: E402
from packages.llm.embeddings import build_embeddings  # noqa: E402
from packages.rag.sparse import SparseEmbedder  # noqa: E402
from packages.summarizer.document_summarizer import summarize_document  # noqa: E402
from packages.vectorstore.qdrant_store import QdrantDocumentStore  # noqa: E402

logger = get_logger(__name__)

DEFAULT_REPORT_DIR = ROOT / "data" / "eval_runs"


def _build_store(settings) -> QdrantDocumentStore:
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


def _select_targets(db, args) -> list:
    if args.doc_id:
        rec = get_document(db, args.doc_id)
        if rec is None:
            print(f"문서를 찾을 수 없음: {args.doc_id}", file=sys.stderr)
            sys.exit(2)
        return [rec]
    if args.regenerate:
        return list_documents(db)
    return list_documents_without_summary(db)


def main() -> None:
    parser = argparse.ArgumentParser(description="문서 요약 일괄 생성")
    parser.add_argument("--doc-id", help="단일 문서만 처리")
    parser.add_argument("--regenerate", action="store_true",
                        help="이미 요약된 문서도 강제 재생성")
    parser.add_argument("--dry-run", action="store_true",
                        help="실제 LLM 호출·DB 갱신 없이 대상만 출력")
    parser.add_argument("--limit", type=int, default=0,
                        help="최대 처리 문서 수 (0=무제한)")
    parser.add_argument("--report",
                        help="결과 JSON 저장 경로 (기본: data/eval_runs/summaries_<ts>.json)")
    args = parser.parse_args()

    settings = get_settings()
    init_db(settings.postgres_url)

    started_at = datetime.now(timezone.utc)
    started_mono = time.monotonic()

    # store/llm은 dry-run이면 불필요 — lazy init으로 비용 0 유지
    store = None
    llm = None
    if not args.dry_run:
        store = _build_store(settings)
        llm = build_chat(settings)

    db_gen = get_session()
    db = next(db_gen)
    try:
        targets = _select_targets(db, args)
        if args.limit > 0:
            targets = targets[: args.limit]

        print(
            f"[summaries] 대상 {len(targets)}개 문서 "
            f"(regenerate={args.regenerate}, dry_run={args.dry_run})"
        )

        results: list[dict] = []
        ok = failed = empty = 0

        for i, rec in enumerate(targets, start=1):
            doc_id = rec.doc_id
            title = rec.title or doc_id
            t0 = time.monotonic()
            print(f"  [{i}/{len(targets)}] {title!r} (doc_id={doc_id[:8]}…)", end=" ")

            if args.dry_run:
                print("→ dry-run skip")
                results.append({"doc_id": doc_id, "title": title, "status": "dry_run"})
                continue

            try:
                chunks = store.scroll_by_doc_id(doc_id, limit=10)
            except Exception as e:
                logger.warning(f"scroll 실패 doc_id={doc_id}: {e}")
                results.append({
                    "doc_id": doc_id, "title": title,
                    "status": "failed", "error": f"scroll: {e}",
                })
                failed += 1
                print("→ FAIL (scroll)")
                continue

            if not chunks:
                results.append({
                    "doc_id": doc_id, "title": title,
                    "status": "empty", "error": "no chunks",
                })
                empty += 1
                print("→ skip (empty)")
                continue

            try:
                summary = summarize_document(
                    title=title, chunks=chunks, settings=settings, llm=llm
                )
            except Exception as e:
                logger.warning(f"summarize 실패 doc_id={doc_id}: {e}")
                results.append({
                    "doc_id": doc_id, "title": title,
                    "status": "failed", "error": str(e),
                })
                failed += 1
                print("→ FAIL (llm)")
                continue

            if not summary.one_liner and not summary.abstract:
                # graceful degrade — 빈 결과는 DB에 쓰지 않는다
                results.append({
                    "doc_id": doc_id, "title": title,
                    "status": "failed", "error": "empty summary",
                    "model": summary.model,
                })
                failed += 1
                print("→ FAIL (empty result)")
                continue

            update_document_summary(
                db,
                doc_id=doc_id,
                summary=summary.to_dict(),
                model=summary.model,
            )
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            results.append({
                "doc_id": doc_id, "title": title,
                "status": "ok",
                "model": summary.model,
                "one_liner": summary.one_liner,
                "topics": summary.topics,
                "elapsed_ms": elapsed_ms,
            })
            ok += 1
            print(f"→ ok ({elapsed_ms}ms): {summary.one_liner!r}")

        finished_at = datetime.now(timezone.utc)
        elapsed_sec = round(time.monotonic() - started_mono, 2)

        report = {
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "elapsed_sec": elapsed_sec,
            "total": len(targets),
            "ok": ok,
            "failed": failed,
            "empty": empty,
            "regenerate": args.regenerate,
            "dry_run": args.dry_run,
            "results": results,
        }

        if not args.dry_run:
            DEFAULT_REPORT_DIR.mkdir(parents=True, exist_ok=True)
            ts = started_at.strftime("%Y-%m-%d_%H%M%S")
            report_path = Path(args.report) if args.report else DEFAULT_REPORT_DIR / f"summaries_{ts}.json"
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"\n[summaries] 리포트 저장: {report_path}")

        print(
            f"[summaries] 완료 — total={len(targets)} "
            f"ok={ok} failed={failed} empty={empty} elapsed={elapsed_sec}s"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
