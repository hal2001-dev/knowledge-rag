"""0.23.1 데이터 마이그레이션 — Qdrant 분류 payload flat key → nested.

ADR-025 (TASK-015) 도입 시 `set_classification_payload`가 `payload["metadata.category"]`
형태(flat top-level key)로 저장하던 잠재 버그가 0.23.1에서 fix.
이 스크립트는 PostgreSQL `documents` 테이블의 doc_type/category/tags를 진실 원천으로
잡아 Qdrant payload에 nested 형식(`payload["metadata"]["category"]`)으로 재적용한다.

flat key는 더 이상 검색에 쓰이지 않지만 cruft로 남아 있을 수 있어 별도로 delete_payload로 정리.

사용:
    .venv/bin/python scripts/migrate_classification_payload_to_nested.py [--dry-run] [--cleanup-flat]

옵션:
    --dry-run       실제 변경 안 함, 영향 범위만 출력
    --cleanup-flat  flat key (`metadata.category` 등) 삭제까지 수행 (기본: nested만 추가)
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.http.models import FieldCondition, Filter, MatchValue
from sqlalchemy.orm import Session

# 프로젝트 루트 import 경로 추가
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from apps.config import get_settings
from packages.code.logger import get_logger
from packages.db.connection import get_session, init_db
from packages.db.models import DocumentRecord
from packages.vectorstore.qdrant_store import QdrantDocumentStore

logger = get_logger(__name__)

FLAT_KEYS = ["metadata.doc_type", "metadata.category", "metadata.tags"]


def _scan_flat_keys(client: QdrantClient, collection: str) -> tuple[Counter, set[str]]:
    """전체 청크를 scroll해 flat key 분포 + 영향받은 doc_id 집합 반환."""
    counter: Counter = Counter()
    affected_docs: set[str] = set()
    next_offset = None
    while True:
        result, next_offset = client.scroll(
            collection_name=collection,
            offset=next_offset,
            limit=512,
            with_payload=True,
            with_vectors=False,
        )
        for p in result:
            payload = p.payload or {}
            for k in FLAT_KEYS:
                if k in payload:
                    counter[k] += 1
            md = payload.get("metadata") or {}
            doc_id = md.get("doc_id") if isinstance(md, dict) else None
            if doc_id and any(k in payload for k in FLAT_KEYS):
                affected_docs.add(doc_id)
        if next_offset is None:
            break
    return counter, affected_docs


def _reapply_nested(
    store: QdrantDocumentStore,
    db: Session,
    doc_ids: set[str],
    dry_run: bool,
) -> int:
    """PostgreSQL의 진실값으로 nested set_payload 재적용. 적용 카운트 반환."""
    n = 0
    for doc_id in sorted(doc_ids):
        rec: Optional[DocumentRecord] = (
            db.query(DocumentRecord).filter(DocumentRecord.doc_id == doc_id).first()
        )
        if rec is None:
            logger.warning(f"doc_id={doc_id[:8]} PG에 없음 — 건너뜀")
            continue
        doc_type = rec.doc_type
        category = rec.category
        tags = rec.tags if rec.tags is not None else None
        if not any([doc_type, category, tags]):
            logger.info(f"doc_id={doc_id[:8]} 분류값 비어 있음 — 건너뜀")
            continue
        logger.info(
            f"doc_id={doc_id[:8]} title={rec.title[:30]} "
            f"→ doc_type={doc_type} category={category} tags={tags}"
        )
        if not dry_run:
            ok = store.set_classification_payload(
                doc_id=doc_id,
                doc_type=doc_type,
                category=category,
                tags=tags,
            )
            if ok:
                n += 1
            else:
                logger.error(f"doc_id={doc_id[:8]} set_payload 실패")
    return n


def _delete_flat_keys(
    client: QdrantClient,
    collection: str,
    doc_ids: set[str],
    dry_run: bool,
) -> int:
    """영향받은 doc_id들의 청크에서 flat key 삭제. 실행 카운트 반환."""
    if not doc_ids:
        return 0
    n = 0
    for doc_id in sorted(doc_ids):
        if not dry_run:
            try:
                client.delete_payload(
                    collection_name=collection,
                    keys=FLAT_KEYS,
                    points=Filter(
                        must=[FieldCondition(key="metadata.doc_id", match=MatchValue(value=doc_id))]
                    ),
                )
                n += 1
            except Exception as e:
                logger.warning(f"doc_id={doc_id[:8]} delete_payload 실패: {e}")
    return n


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="실제 변경 없이 영향 범위만 출력")
    parser.add_argument(
        "--cleanup-flat",
        action="store_true",
        help="flat key 삭제까지 수행 (기본: nested 추가만)",
    )
    args = parser.parse_args()

    settings = get_settings()
    init_db(settings.postgres_url)

    sparse = None
    if settings.search_mode == "hybrid":
        from packages.rag.sparse import SparseEmbedder
        sparse = SparseEmbedder(settings.sparse_model_name)

    from packages.llm.embeddings import get_embeddings
    embeddings = get_embeddings(settings)

    store = QdrantDocumentStore(
        url=settings.qdrant_url,
        collection=settings.qdrant_collection,
        embeddings=embeddings,
        search_mode=settings.search_mode,
        sparse_embedder=sparse,
    )
    client = store._client

    print(f"=== flat key scan ({settings.qdrant_collection}) ===")
    counter, affected_docs = _scan_flat_keys(client, settings.qdrant_collection)
    print(f"flat key 청크 분포:")
    for k in FLAT_KEYS:
        print(f"  {k:30s}: {counter.get(k, 0)}")
    print(f"영향받은 doc_id: {len(affected_docs)}건")

    if not affected_docs:
        print("처리할 데이터 없음 — 종료")
        return 0

    print(f"\n=== nested 재적용 (dry_run={args.dry_run}) ===")
    db_gen = get_session()
    db = next(db_gen)
    n_applied = _reapply_nested(store, db, affected_docs, args.dry_run)
    print(f"적용 doc 수: {n_applied}/{len(affected_docs)}")

    n_cleaned = 0
    if args.cleanup_flat:
        print(f"\n=== flat key 삭제 (dry_run={args.dry_run}) ===")
        n_cleaned = _delete_flat_keys(client, settings.qdrant_collection, affected_docs, args.dry_run)
        print(f"flat key 정리 doc 수: {n_cleaned}/{len(affected_docs)}")

    if args.dry_run:
        print("\n*** dry-run — 실제 변경 안 함. --cleanup-flat 없이 한 번 더 실행하면 nested 적용 ***")
    else:
        print(f"\n적용 완료. nested {n_applied}건"
              + (f", flat 정리 {n_cleaned}건" if args.cleanup_flat else " (flat key는 그대로, --cleanup-flat 옵션 시 삭제)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
