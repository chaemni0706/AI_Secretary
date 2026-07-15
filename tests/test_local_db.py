"""Local SQLite DB foundation tests (Stage 2).

Verifies that:
- an isolated SQLite DB can be initialized from ``database/local_schema.sql``,
- the SQLAlchemy ORM models can read/write ``planner_items`` and its 1:1
  detail tables (``event_details`` / ``todo_details``),
- foreign keys and the item-type triggers from the SQL are in force,
- NO ``schedules`` / ``todos`` tables exist (planner_items is the SoT),
- the production runtime DB is never touched by the tests.

These tests build their own engine on a temporary file via the shared
``create_sqlite_engine`` helper, so they are fully isolated and never import
``conftest`` directly.
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker

from backend.database.init_db import apply_schema_to_sqlite_file
from backend.database.models import (
    Calendar,
    EventDetail,
    PlannerItem,
    TodoDetail,
    User,
)
from backend.database.session import create_sqlite_engine

NOW = "2026-06-30T09:00:00+09:00"


@pytest.fixture()
def db_session(tmp_path):
    """An isolated, schema-initialized SQLite session on a temp file."""
    db_file = tmp_path / "test_local.db"
    apply_schema_to_sqlite_file(db_file)               # raw SQL -> triggers/CHECKs kept
    engine = create_sqlite_engine(f"sqlite:///{db_file.as_posix()}")
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _seed_user_calendar(session):
    # commit the parent rows in FK order so foreign_keys=ON is satisfied
    session.add(User(user_id="u1", created_at=NOW, updated_at=NOW))
    session.commit()
    session.add(Calendar(calendar_id="cal1", user_id="u1", name="기본",
                         is_primary=1, created_at=NOW, updated_at=NOW))
    session.commit()


# --------------------------------------------------------------------------- #
# Schema shape
# --------------------------------------------------------------------------- #
def test_schema_has_planner_structure_and_no_legacy_tables(db_session):
    names = set(inspect(db_session.get_bind()).get_table_names())
    # planner-centric structure exists
    assert {"planner_items", "event_details", "todo_details"}.issubset(names)
    # optional tables also present in local_schema.sql
    assert {"reminders", "user_settings", "user_memories"}.issubset(names)
    # the forbidden standalone tables must NOT exist
    assert "schedules" not in names
    assert "todos" not in names


# --------------------------------------------------------------------------- #
# ORM round-trip: EVENT
# --------------------------------------------------------------------------- #
def test_orm_can_insert_and_read_event(db_session):
    _seed_user_calendar(db_session)
    db_session.add(PlannerItem(
        item_id="it_event", user_id="u1", item_type="EVENT", title="병원 예약",
        status="SCHEDULED", priority="MEDIUM", source_type="AI",
        created_at=NOW, updated_at=NOW,
    ))
    db_session.commit()
    db_session.add(EventDetail(
        item_id="it_event", calendar_id="cal1",
        start_at="2026-06-30T14:00:00+09:00", end_at="2026-06-30T15:00:00+09:00",
        location_text="서울OO병원", travel_time_minutes=30,
    ))
    db_session.commit()

    item = db_session.get(PlannerItem, "it_event")
    assert item is not None
    assert item.item_type == "EVENT"
    assert item.event_detail is not None
    assert item.event_detail.travel_time_minutes == 30


# --------------------------------------------------------------------------- #
# ORM round-trip: TODO
# --------------------------------------------------------------------------- #
def test_orm_can_insert_and_read_todo(db_session):
    _seed_user_calendar(db_session)
    db_session.add(PlannerItem(
        item_id="it_todo", user_id="u1", item_type="TODO", title="과제 제출",
        status="SCHEDULED", priority="HIGH", source_type="MANUAL",
        created_at=NOW, updated_at=NOW,
    ))
    db_session.commit()
    db_session.add(TodoDetail(item_id="it_todo", due_at="2026-06-30T23:59:00+09:00"))
    db_session.commit()

    item = db_session.get(PlannerItem, "it_todo")
    assert item.item_type == "TODO"
    assert item.todo_detail is not None
    assert item.todo_detail.due_at.endswith("23:59:00+09:00")


# --------------------------------------------------------------------------- #
# Constraints / triggers from local_schema.sql are enforced
# --------------------------------------------------------------------------- #
def test_item_type_trigger_blocks_mismatched_detail(db_session):
    _seed_user_calendar(db_session)
    # planner item is a TODO; attaching event_details must be rejected by trigger
    db_session.add(PlannerItem(
        item_id="it_x", user_id="u1", item_type="TODO", title="x",
        status="DRAFT", priority="LOW", source_type="MANUAL",
        created_at=NOW, updated_at=NOW,
    ))
    db_session.commit()
    db_session.add(EventDetail(item_id="it_x", calendar_id="cal1",
                               start_at="2026-06-30T14:00:00+09:00"))
    with pytest.raises((IntegrityError, OperationalError)):
        db_session.commit()
    db_session.rollback()


def test_foreign_key_enforced(db_session):
    # planner item referencing a non-existent user must fail (PRAGMA foreign_keys=ON)
    db_session.add(PlannerItem(
        item_id="it_orphan", user_id="ghost", item_type="EVENT", title="x",
        status="DRAFT", priority="LOW", source_type="MANUAL",
        created_at=NOW, updated_at=NOW,
    ))
    with pytest.raises((IntegrityError, OperationalError)):
        db_session.commit()
    db_session.rollback()


# --------------------------------------------------------------------------- #
# Test isolation: production runtime DB is never created/used by tests
# --------------------------------------------------------------------------- #
def test_tests_do_not_touch_runtime_db(db_session):
    assert "runtime/ai_secretary_local.db" not in str(db_session.get_bind().url)
    assert ":memory:" not in str(db_session.get_bind().url)
