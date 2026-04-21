from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator


_engine = None
_SessionLocal = None


def init_db(postgres_url: str) -> None:
    global _engine, _SessionLocal
    _engine = create_engine(postgres_url, pool_pre_ping=True)
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


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
