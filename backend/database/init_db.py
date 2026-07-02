"""Schema initialization helpers.

``database/local_schema.sql`` is the single source of truth. These helpers
apply that raw SQL (preserving triggers and CHECK constraints) instead of
``Base.metadata.create_all``. Used by the runtime initializer and by tests to
build an isolated database.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Union

from sqlalchemy.engine import Engine

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCAL_SCHEMA_PATH = _PROJECT_ROOT / "database" / "local_schema.sql"


def read_schema_sql() -> str:
    if not LOCAL_SCHEMA_PATH.exists():
        raise FileNotFoundError(f"SQL schema not found: {LOCAL_SCHEMA_PATH}")
    return LOCAL_SCHEMA_PATH.read_text(encoding="utf-8")


def apply_schema_to_sqlite_file(db_path: Union[str, Path]) -> None:
    """Initialize a standalone SQLite file from local_schema.sql (raw sqlite3)."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    sql = read_schema_sql()
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(sql)
        conn.commit()


def init_db_from_engine(engine: Engine) -> None:
    """Apply local_schema.sql through an existing SQLAlchemy engine's raw
    DBAPI connection (works for file-based and shared in-memory SQLite)."""
    sql = read_schema_sql()
    raw = engine.raw_connection()
    try:
        cursor = raw.cursor()
        cursor.executescript(sql)
        raw.commit()
    finally:
        raw.close()
