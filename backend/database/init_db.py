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


# --- Lightweight, idempotent column migrations ------------------------------
# CREATE TABLE IF NOT EXISTS never alters an existing table, so newly-added
# columns must be backfilled for databases created before the column existed.
# Each entry: table -> {column: column_definition}. Applied only when missing.
_COLUMN_MIGRATIONS = {
    "ledger_transactions": {
        "memo": "TEXT",  # user free-form memo (optional)
    },
}


def _apply_column_migrations(cursor) -> None:
    """Add any missing columns listed in ``_COLUMN_MIGRATIONS`` (SQLite has no
    ADD COLUMN IF NOT EXISTS, so existence is checked via PRAGMA table_info)."""
    for table, columns in _COLUMN_MIGRATIONS.items():
        try:
            existing = {row[1] for row in cursor.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()}
        except Exception:
            continue  # table not present yet -> CREATE handled it already
        if not existing:
            continue
        for col, decl in columns.items():
            if col not in existing:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")


def _migrate_todo_planned_date_to_due_at(cursor) -> None:
    """One-time data fix: before start/end-date support was added, todo_details
    .planned_date held what the API exposed as due_date; due_at was unused.
    Move that value to due_at (the real due-date column going forward) and
    clear planned_date so it's free to hold a genuine start date. Idempotent:
    only touches rows where due_at is still empty."""
    try:
        cursor.execute(
            "UPDATE todo_details SET due_at = planned_date, planned_date = NULL "
            "WHERE due_at IS NULL AND planned_date IS NOT NULL"
        )
    except Exception:
        pass  # table not present yet -> nothing to backfill


def apply_schema_to_sqlite_file(db_path: Union[str, Path]) -> None:
    """Initialize a standalone SQLite file from local_schema.sql (raw sqlite3)."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    sql = read_schema_sql()
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(sql)
        _apply_column_migrations(conn.cursor())
        _migrate_todo_planned_date_to_due_at(conn.cursor())
        conn.commit()


def init_db_from_engine(engine: Engine) -> None:
    """Apply local_schema.sql through an existing SQLAlchemy engine's raw
    DBAPI connection (works for file-based and shared in-memory SQLite)."""
    sql = read_schema_sql()
    raw = engine.raw_connection()
    try:
        cursor = raw.cursor()
        cursor.executescript(sql)
        _apply_column_migrations(cursor)
        _migrate_todo_planned_date_to_due_at(cursor)
        raw.commit()
    finally:
        raw.close()
