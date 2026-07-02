"""Shared client fixture for ledger API tests.

Isolated temp SQLite DB via get_db override + apply_schema_to_sqlite_file, so
the ledger_transactions table (and all others) exist. Does NOT import conftest.
Mirrors the pattern used by test_todo.py / test_local_schedule.py.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.database.init_db import apply_schema_to_sqlite_file
from backend.database.session import create_sqlite_engine, get_db
from backend.main import app


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "ledger_test.db"
    apply_schema_to_sqlite_file(db_file)
    engine = create_sqlite_engine(f"sqlite:///{db_file.as_posix()}")
    TestingSession = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, future=True
    )

    def _override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()
