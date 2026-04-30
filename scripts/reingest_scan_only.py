"""ISSUE-010: extraction_quality='scan_only' 문서를 macOS Vision OCR로 재색인.

각 문서당 처리 순서:
  1. 신 chunks 생성 (force_full_page_ocr 모드, 기존 markdown 덮어쓰기)
  2. Qdrant에서 doc_id 청크 삭제 (성공 후에만)
  3. 신 chunks를 Qdrant에 add_documents
  4. 신 chunks에 category/series payload 재적용 (있던 경우)
  5. DB의 chunk_count/has_tables/has_images/extraction_quality 갱신
  6. summary는 무효화(NULL) — 사용자 검수 후 generate_summaries.py 재실행 권장

처리 중 실패하면 해당 doc만 skip 후 다음 문서로 진행. 마지막에 보고.

사용법:
  .venv/bin/python scripts/reingest_scan_only.py            # 모든 scan_only 처리
  .venv/bin/python scripts/reingest_scan_only.py --doc-id <uuid>
  .venv/bin/python scripts/reingest_scan_only.py --dry-run  # 대상만 출력
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from sqlalchemy import text  # noqa: E402

from apps.config import get_settings  # noqa: E402
from packages.code.logger import get_logger  # noqa: E402
from packages.db.connection import get_engine, get_session, init_db  # noqa: E402
from packages.db.repository import get_document  # noqa: E402
from packages.llm.embeddings import build_embeddings  # noqa: E402
from packages.loaders.docling_loader import DoclingDocumentLoader  # noqa: E402
from packages.rag.chunker import chunk_documents  # noqa: E402
from packages.rag.sparse import SparseEmbedder  # noqa: E402
from packages.vectorstore.qdrant_store import QdrantDocumentStore  # noqa: E402

logger = get_logger(__name__)

UPLOADS_DIR = ROOT / "data" / "uploads"


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


def _list_targets(engine, doc_id: str | None):
    with engine.connect() as c:
        if doc_id:
            rows = c.execute(text(
                "SELECT doc_id, title, category, series_id, category_confidence, tags "
                "FROM documents WHERE doc_id = :d"
            ), {"d": doc_id}).fetchall()
        else:
            rows = c.execute(text(
                "SELECT doc_id, title, category, series_id, category_confidence, tags "
                "FROM documents WHERE extraction_quality = 'scan_only' ORDER BY title"
            )).fetchall()
    return rows


def _process_one(row, store, settings) -> tuple[bool, str]:
    """단일 문서 처리. (성공 여부, 메시지)"""
    doc_id, title = row.doc_id, row.title
    src_pdf = UPLOADS_DIR / f"{doc_id}.pdf"
    if not src_pdf.exists():
        return False, f"원본 PDF 없음: {src_pdf}"

    src_kb = src_pdf.stat().st_size / 1024
    logger.info(f"[{doc_id[:8]}] OCR 시작 — {title} ({src_kb:.0f} KB)")
    t0 = time.monotonic()

    try:
        loader = DoclingDocumentLoader(
            markdown_save_dir=settings.markdown_dir,
            force_full_page_ocr=True,
        )
        documents = loader.load(file_path=str(src_pdf), doc_id=doc_id, title=title)
        chunks = chunk_documents(documents)
        if not chunks:
            return False, "OCR 후 chunks=0 (변환 실패 추정)"

        has_tables = any(d.metadata.get("content_type") == "table" for d in chunks)
        has_images = any(d.metadata.get("content_type") == "image" for d in chunks)

        # 기존 청크 삭제 — load 성공 후에만 destruct
        store.delete_by_doc_id(doc_id)
        store.add_documents(chunks)

        # category/series payload 재적용 (category_confidence는 DB-only이라 Qdrant 측 인자 없음)
        if row.category:
            store.set_classification_payload(
                doc_id=doc_id,
                category=row.category,
                tags=list(row.tags or []),
            )
        if row.series_id:
            store.set_series_payload(doc_ids=[doc_id], series_id=row.series_id)

        # DB 갱신 — chunk_count, flags, extraction_quality. summary는 무효화.
        engine = get_engine()
        with engine.begin() as c:
            c.execute(text(
                "UPDATE documents SET "
                " chunk_count = :cc, has_tables = :ht, has_images = :hi,"
                " indexed_at = :ts, extraction_quality = 'ok',"
                " summary = NULL, summary_model = NULL, summary_generated_at = NULL "
                "WHERE doc_id = :d"
            ), {
                "cc": len(chunks),
                "ht": has_tables, "hi": has_images,
                "ts": datetime.now(timezone.utc),
                "d": doc_id,
            })

        dt = time.monotonic() - t0
        return True, f"chunks={len(chunks)} time={dt:.0f}s"
    except Exception as e:
        return False, f"예외: {e!r}"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--doc-id", help="단일 문서 처리 (extraction_quality 무관)")
    p.add_argument("--dry-run", action="store_true", help="대상만 출력")
    args = p.parse_args()

    settings = get_settings()
    init_db(os.environ["POSTGRES_URL"])
    engine = get_engine()
    targets = _list_targets(engine, args.doc_id)
    if not targets:
        print("처리 대상 없음")
        return 0

    print(f"대상 {len(targets)}건:")
    for r in targets:
        print(f"  - {r.doc_id}  {r.title}")
    if args.dry_run:
        return 0

    print("\n시작…\n")
    store = _build_store(settings)

    ok = 0
    fail = []
    t_total0 = time.monotonic()
    for i, row in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] {row.title}")
        success, msg = _process_one(row, store, settings)
        if success:
            ok += 1
            print(f"  ✓ {msg}")
        else:
            fail.append((row.doc_id, row.title, msg))
            print(f"  ❌ {msg}")
    dt_total = time.monotonic() - t_total0

    print(f"\n=== 완료 ===")
    print(f"성공: {ok}/{len(targets)}  | 총 {dt_total/60:.1f}분")
    if fail:
        print(f"실패 {len(fail)}건:")
        for did, title, msg in fail:
            print(f"  - {did}  {title}  | {msg}")
    print()
    print("다음 단계:")
    print("  .venv/bin/python scripts/generate_summaries.py")
    print("    (이번에 재색인된 문서는 summary=NULL이라 자동으로 대상)")
    return 0 if not fail else 1


if __name__ == "__main__":
    sys.exit(main())
