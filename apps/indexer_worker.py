"""TASK-018 (ADR-028): 색인 워커 프로세스.

실행:
  python -m apps.indexer_worker

- Postgres `ingest_jobs` 큐를 폴링 (`SELECT … FOR UPDATE SKIP LOCKED`)
- claim → pipeline.ingest → create_document → summary 생성 + 자동 분류 → mark_done
- 실패 시 mark_failed (3회 retry 후 영구 failed)
- SIGTERM 수신 시 현재 잡 끝까지 처리 후 종료 (graceful)
"""
from __future__ import annotations

import signal
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from apps.config import get_settings  # noqa: E402
from apps.dependencies import get_pipeline  # noqa: E402
from apps.routers.documents import _classify_doc, _generate_summary_inner  # noqa: E402
from packages.classifier import CategoryClassifier  # noqa: E402
from packages.code.logger import get_logger  # noqa: E402
from packages.db.connection import get_session, init_db  # noqa: E402
from packages.db.repository import (  # noqa: E402
    create_document,
    get_document_by_hash,
    update_document_classification,
)
from packages.jobs.queue import claim_next_job, mark_done, mark_failed  # noqa: E402
from packages.vectorstore.qdrant_store import QdrantDocumentStore  # noqa: E402

logger = get_logger(__name__)

POLL_INTERVAL_SEC = 3.0          # pending 잡이 없을 때 sleep
EMPTY_BACKOFF_MAX = 15.0         # 빈 큐 sleep 상한
MAX_RETRIES = 3                  # 영구 실패 전 재시도 횟수

_shutdown_requested = False


def _install_signal_handlers() -> None:
    def _handler(signum, _frame):
        global _shutdown_requested
        logger.info(f"signal {signum} 수신 — graceful shutdown 진입")
        _shutdown_requested = True
    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)


def _process_job(job, settings, pipeline) -> None:
    """단일 잡 처리. 호출자가 db 세션·예외 격리·status 갱신을 맡는다."""
    db_gen = get_session()
    db = next(db_gen)
    try:
        # 1) L1 중복 감지 — 큐에 들어온 뒤 다른 잡이 동일 hash로 먼저 인덱싱했을 가능성
        if job.content_hash:
            existing = get_document_by_hash(db, job.content_hash)
            if existing is not None and existing.doc_id != job.doc_id:
                logger.info(
                    f"job {job.id}: 중복 발견(content_hash={job.content_hash[:8]}…) — "
                    f"기존 doc_id={existing.doc_id}로 done 처리"
                )
                mark_done(db, job.id, doc_id=existing.doc_id)
                return

        # 2) 인덱싱
        record = pipeline.ingest(
            file_path=job.file_path,
            title=job.title,
            source=job.source or job.file_path,
            doc_id=job.doc_id,
            content_hash=job.content_hash,
        )
        create_document(db, record)

        # 3) 사용자 명시 분류값이 있으면 우선 적용 (자동 분류 skip)
        user_specified = bool(job.user_doc_type or job.user_category or job.user_tags)
        if user_specified:
            update_document_classification(
                db,
                doc_id=job.doc_id,
                doc_type=job.user_doc_type,
                category=job.user_category,
                category_confidence=1.0 if job.user_category else None,
                tags=list(job.user_tags) if job.user_tags else None,
            )
            pipeline._store.set_classification_payload(
                doc_id=job.doc_id,
                doc_type=job.user_doc_type,
                category=job.user_category if job.user_category is not None else "",
                tags=list(job.user_tags) if job.user_tags else None,
            )

        # 4) summary 생성 (TASK-014)
        if settings.summary_enabled:
            _generate_summary_inner(db, pipeline, settings, job.doc_id)
            db.expire_all()

        # 5) 자동 분류 (사용자 미지정 시) — TASK-015
        if not user_specified:
            db.expire_all()
            from packages.db.repository import get_document
            doc_rec = get_document(db, job.doc_id)
            if doc_rec is not None:
                _classify_doc(db, pipeline, settings, doc_rec)

        # 6) 시리즈 자동 묶기 (TASK-020) — 휴리스틱 high면 auto_attached, medium은 suggested.
        # 실패는 격리(인덱싱 자체는 성공). pipeline._store.set_series_payload를 setter로 주입.
        try:
            from packages.series import series_match_for_doc
            db.expire_all()
            result = series_match_for_doc(
                db,
                job.doc_id,
                qdrant_payload_setter=pipeline._store.set_series_payload,
            )
            if result.get("status") in ("auto_attached", "suggested"):
                logger.info(f"job {job.id} series_match: {result}")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"job {job.id} series_match 실패(격리됨): {exc}")

        # 7) /index/overview 캐시 무효화
        from apps.routers.documents import invalidate_index_overview_cache
        invalidate_index_overview_cache()

        mark_done(db, job.id, doc_id=job.doc_id)
        logger.info(f"job {job.id} 완료 doc_id={job.doc_id}")
    finally:
        db.close()


def _handle_failure(job_id: int, error: str, retry_count: int) -> None:
    """예외를 mark_failed로 기록. retry < MAX_RETRIES 면 pending으로 되돌림."""
    db_gen = get_session()
    db = next(db_gen)
    try:
        retry = retry_count < MAX_RETRIES
        mark_failed(db, job_id, error, retry=retry)
        if retry:
            logger.warning(f"job {job_id} 재시도 예정 (retry {retry_count + 1}/{MAX_RETRIES})")
        else:
            logger.error(f"job {job_id} 영구 실패")
    finally:
        db.close()


def main() -> int:
    settings = get_settings()
    init_db(settings.postgres_url)

    # SQLAlchemy `Base.metadata.create_all`은 새 컬럼은 못 만들지만 새 테이블은 생성.
    # 명시적으로 한 번 호출해 ingest_jobs 등 신규 테이블을 보강(이미 있으면 무해).
    from packages.db.connection import get_engine
    from packages.db.models import Base
    Base.metadata.create_all(bind=get_engine())

    _install_signal_handlers()

    logger.info(
        f"indexer 워커 시작 — postgres={settings.postgres_url.split('@')[-1]}, "
        f"qdrant={settings.qdrant_url}, search_mode={settings.search_mode}"
    )

    pipeline = get_pipeline()
    logger.info("RAG pipeline 초기화 완료. 폴링 시작.")

    empty_streak_sec = 0.0
    while not _shutdown_requested:
        db_gen = get_session()
        db = next(db_gen)
        try:
            job = claim_next_job(db)
        finally:
            db.close()

        if job is None:
            sleep_for = min(POLL_INTERVAL_SEC + empty_streak_sec * 0.5, EMPTY_BACKOFF_MAX)
            time.sleep(sleep_for)
            empty_streak_sec = min(empty_streak_sec + sleep_for, EMPTY_BACKOFF_MAX)
            continue

        empty_streak_sec = 0.0
        logger.info(
            f"job {job.id} claim 됨 — title={job.title!r} doc_id={job.doc_id} "
            f"retry={job.retry_count}"
        )
        try:
            _process_job(job, settings, pipeline)
        except Exception:
            tb = traceback.format_exc()
            logger.error(f"job {job.id} 예외:\n{tb}")
            _handle_failure(job.id, tb, job.retry_count)
        # 잡 1건 처리 후 즉시 다음 잡 시도(폴링 sleep 없이)

    logger.info("indexer 워커 종료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
