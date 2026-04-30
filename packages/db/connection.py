from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from packages.code.logger import get_logger

logger = get_logger(__name__)

_engine = None
_SessionLocal = None

# 마이그레이션 디렉터리: packages/db/migrations/0NNN_*.sql 을 순서대로 실행한다.
# init.sql 은 신규 환경용 1회 적용. 0001+ 는 이미 있는 테이블에 ALTER 등 추가 변경.
_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


# 각 마이그레이션이 "끝났는지" 미리 확인하기 위한 sentinel 컬럼 매핑.
# 컬럼이 이미 있으면 ALTER TABLE 자체를 시도하지 않는다 — AccessExclusiveLock 회피.
# 마이그레이션 sentinel — (file → check_kind, *args)
# kind: "column" → (table, column) 존재 검사
#       "table"  → (table,) 존재 검사
_MIGRATION_SENTINELS: dict[str, tuple] = {
    "0001_add_summary_columns.sql":           ("column", "documents", "summary"),
    "0002_add_classification_columns.sql":    ("column", "documents", "doc_type"),
    "0003_add_ingest_jobs.sql":               ("table", "ingest_jobs"),
    "0004_add_conversations_user_id.sql":     ("column", "conversations", "user_id"),
    "0005_add_series_tables.sql":             ("table", "series"),
    "0006_add_extraction_quality.sql":        ("column", "documents", "extraction_quality"),
}


def _column_exists(conn, table: str, column: str) -> bool:
    row = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c LIMIT 1"
        ),
        {"t": table, "c": column},
    ).first()
    return row is not None


def _table_exists(conn, table: str) -> bool:
    row = conn.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = :t LIMIT 1"
        ),
        {"t": table},
    ).first()
    return row is not None


def _is_migration_applied(conn, sentinel: tuple) -> bool:
    kind = sentinel[0]
    if kind == "column":
        return _column_exists(conn, sentinel[1], sentinel[2])
    if kind == "table":
        return _table_exists(conn, sentinel[1])
    return False


def _apply_alter_migrations(engine) -> None:
    """idempotent 마이그레이션 적용.

    동시 기동(uvicorn + indexer_worker)에서 같은 마이그레이션을 두 프로세스가 실행하면
    pg_type unique 충돌이 발생할 수 있어 `pg_advisory_xact_lock`으로 트랜잭션 단위 직렬화.
    sentinel이 이미 있으면 SQL 시도 자체를 회피.
    """
    files = sorted(p for p in _MIGRATIONS_DIR.glob("[0-9]*.sql"))
    if not files:
        return
    # 빠른 경로 — 모든 마이그레이션이 이미 적용됐으면 lock 자체 불필요
    with engine.connect() as check_conn:
        all_applied = all(
            _is_migration_applied(check_conn, _MIGRATION_SENTINELS[f.name])
            for f in files if f.name in _MIGRATION_SENTINELS
        )
    if all_applied:
        return

    # 직렬화: 임의의 64-bit lock id (프로젝트 고유). 다른 프로세스도 같은 id로 대기.
    # pg_advisory_xact_lock는 bigint(signed 64-bit, 최대 2^63-1) — 9바이트 'knowledge'는 한도 초과(잠재 버그).
    # TASK-018 도입 시 모든 sentinel 충족으로 빠른 경로만 타서 노출 안 됐고, TASK-019 신규 마이그레이션
    # 0004로 표면화. 'knowledg' 8바이트(0x6B6E6F776C656467 ≈ 7.7e18 < 2^63-1)로 축약.
    LOCK_ID = int.from_bytes(b"knowledg", "big")
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(:lid)"), {"lid": LOCK_ID})
        # lock 획득 후 다시 sentinel 확인 — 다른 프로세스가 먼저 적용했을 수 있음
        for f in files:
            sentinel = _MIGRATION_SENTINELS.get(f.name)
            if sentinel and _is_migration_applied(conn, sentinel):
                continue
            sql = f.read_text(encoding="utf-8").strip()
            if not sql:
                continue
            logger.info(f"DB 마이그레이션 적용: {f.name}")
            conn.execute(text(sql))


def init_db(postgres_url: str) -> None:
    global _engine, _SessionLocal
    _engine = create_engine(postgres_url, pool_pre_ping=True)
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    # SQLAlchemy create_all 은 새 컬럼을 추가하지 않으므로 ALTER 마이그레이션을 별도로 적용
    _apply_alter_migrations(_engine)


def get_engine():
    if _engine is None:
        raise RuntimeError("DB가 초기화되지 않았습니다. init_db()를 먼저 호출하세요.")
    return _engine


def get_session() -> Generator[Session, None, None]:
    if _SessionLocal is None:
        raise RuntimeError("DB가 초기화되지 않았습니다. init_db()를 먼저 호출하세요.")
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()
