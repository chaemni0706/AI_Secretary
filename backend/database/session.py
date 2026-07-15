"""Synchronous SQLAlchemy engine + session factory for the local SQLite store.

Design notes
------------
- Local-only SQLite (no external DB server). The default URL is
  ``sqlite:///runtime/ai_secretary_local.db`` (see ``core.config.settings``).
- A *relative* sqlite path is anchored to the project root so the DB lands in
  ``<repo>/runtime/`` regardless of the current working directory, matching
  ``scripts/init_local_db.py``.
- ``PRAGMA foreign_keys=ON`` is enabled per-connection so the schema's foreign
  keys / cascades behave the same way as the raw SQL initializer.
- Schema creation is NOT done here. ``Base.metadata.create_all`` is avoided on
  purpose; ``database/local_schema.sql`` (applied via ``init_db``) stays the
  single source of truth so triggers and CHECK constraints are preserved.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import settings

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SQLITE_PREFIX = "sqlite:///"


def normalize_sqlite_url(url: str) -> str:
    """Anchor a relative sqlite file path to the project root and ensure its
    parent directory exists. Non-sqlite or ``:memory:`` URLs pass through."""
    if not url.startswith(_SQLITE_PREFIX):
        return url
    raw = url[len(_SQLITE_PREFIX):]
    if not raw or raw == ":memory:":
        return url
    path = Path(raw)
    if not path.is_absolute():
        path = _PROJECT_ROOT / path
    return f"{_SQLITE_PREFIX}{path.as_posix()}"


def create_sqlite_engine(url: str, **kwargs) -> Engine:
    """Create an engine configured for SQLite (thread-safe sharing + FK pragma).

    Reused by tests so test engines behave exactly like the production one.
    """
    url = normalize_sqlite_url(url)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args, future=True, **kwargs)

    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _enable_sqlite_fk(dbapi_connection, _connection_record):  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


# --- Production engine / session factory ------------------------------------
DATABASE_URL = normalize_sqlite_url(settings.DATABASE_URL)
engine = create_sqlite_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, future=True
)


def ensure_sqlite_dir(url: str) -> None:
    """Create the parent directory of a sqlite file lazily (only when the DB is
    actually used), so merely importing this module never creates ``runtime/``."""
    if not url.startswith(_SQLITE_PREFIX):
        return
    raw = url[len(_SQLITE_PREFIX):]
    if raw and raw != ":memory:":
        Path(raw).parent.mkdir(parents=True, exist_ok=True)


def get_db():
    """FastAPI dependency yielding a session, always closed afterwards."""
    ensure_sqlite_dir(DATABASE_URL)
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
