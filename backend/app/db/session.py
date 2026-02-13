from __future__ import annotations

import os
from pathlib import Path
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base

_engine: Engine | None = None
_sessionmaker: sessionmaker[Session] | None = None


def _default_database_url() -> str:
    backend_root = Path(__file__).resolve().parents[2]
    data_dir = backend_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{data_dir / 'dashboard.db'}"


def database_url() -> str:
    return os.getenv("APP_DATABASE_URL", _default_database_url())


def _ensure_engine() -> tuple[Engine, sessionmaker[Session]]:
    global _engine, _sessionmaker
    if _engine is None or _sessionmaker is None:
        url = database_url()
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _engine = create_engine(url, connect_args=connect_args, future=True)
        _sessionmaker = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    return _engine, _sessionmaker


def init_db() -> None:
    engine, _ = _ensure_engine()
    Base.metadata.create_all(bind=engine)


def get_session() -> Iterator[Session]:
    _, session_factory = _ensure_engine()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    _, session_factory = _ensure_engine()
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_database_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _sessionmaker = None
