"""Planner repository + Schedule/To-do service tests (Stage 3).

Isolated temp SQLite DB initialized from local_schema.sql. Verifies the
lowercase<->UPPERCASE casing mapping, date/time <-> ISO conversion, To-do
`completed` derivation, soft-delete exclusion, and safe missing-id handling.
Does not import conftest.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import sessionmaker

from backend.database.init_db import apply_schema_to_sqlite_file
from backend.database.models import Calendar, PlannerItem, User
from backend.database.schema.local_schedule_schema import ScheduleCreate, ScheduleUpdate
from backend.database.schema.todo_schema import TodoCreate, TodoUpdate
from backend.database.session import create_sqlite_engine
from backend.database import repository as repo
from backend.services import local_schedule_service as sched
from backend.services import todo_service as todo

NOW = "2026-06-30T09:00:00"
USER = "u1"
CAL = "cal1"


@pytest.fixture()
def db(tmp_path):
    db_file = tmp_path / "planner.db"
    apply_schema_to_sqlite_file(db_file)
    engine = create_sqlite_engine(f"sqlite:///{db_file.as_posix()}")
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = Session()
    session.add(User(user_id=USER, created_at=NOW, updated_at=NOW))
    session.commit()
    session.add(Calendar(calendar_id=CAL, user_id=USER, name="기본",
                         is_primary=1, created_at=NOW, updated_at=NOW))
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _new_schedule(**over):
    base = dict(title="병원 예약", date="2026-06-30", start_time="14:00",
                end_time="15:00", category="hospital", priority="high",
                location="서울OO병원", memo="진료", source="ai",
                travel_time_minutes=30)
    base.update(over)
    return ScheduleCreate(**base)


# --------------------------------------------------------------------------- #
# Repository primitives
# --------------------------------------------------------------------------- #
def test_repository_create_planner_event_and_todo_details(db):
    repo.create_planner_item(db, item_id="e1", user_id=USER, item_type="EVENT",
                             title="회의", status="SCHEDULED", priority="MEDIUM",
                             source_type="MANUAL")
    repo.create_event_detail(db, item_id="e1", calendar_id=CAL,
                             start_at="2026-06-30T10:00:00")
    repo.create_planner_item(db, item_id="t1", user_id=USER, item_type="TODO",
                             title="과제", status="SCHEDULED", priority="HIGH",
                             source_type="MANUAL")
    repo.create_todo_detail(db, item_id="t1", planned_date="2026-06-30")
    db.commit()
    assert db.get(PlannerItem, "e1").event_detail.start_at == "2026-06-30T10:00:00"
    assert db.get(PlannerItem, "t1").todo_detail.planned_date == "2026-06-30"


# --------------------------------------------------------------------------- #
# Schedule: casing + datetime round-trip
# --------------------------------------------------------------------------- #
def test_schedule_casing_and_datetime_mapping(db):
    read = sched.create_schedule(db, _new_schedule(), user_id=USER, calendar_id=CAL)
    # API response is lowercase / split date+time
    assert read.priority == "high"
    assert read.source == "ai"
    assert read.status == "scheduled"
    assert read.date == "2026-06-30"
    assert read.start_time == "14:00"
    assert read.end_time == "15:00"
    assert read.travel_time_minutes == 30

    # DB stores UPPERCASE + single ISO datetime
    row = db.get(PlannerItem, read.id)
    assert row.priority == "HIGH"
    assert row.source_type == "AI"          # "ai" -> "AI"
    assert row.status == "SCHEDULED"
    assert row.item_type == "EVENT"
    assert row.event_detail.start_at == "2026-06-30T14:00:00"
    assert row.event_detail.end_at == "2026-06-30T15:00:00"


def test_schedule_source_user_maps_to_manual(db):
    read = sched.create_schedule(db, _new_schedule(source="user"),
                                 user_id=USER, calendar_id=CAL)
    assert read.source == "user"
    assert db.get(PlannerItem, read.id).source_type == "MANUAL"   # not "USER"


def test_get_and_list_and_update_schedule(db):
    a = sched.create_schedule(db, _new_schedule(title="A"), user_id=USER, calendar_id=CAL)
    sched.create_schedule(db, _new_schedule(title="B"), user_id=USER, calendar_id=CAL)
    assert sched.get_schedule(db, a.id).title == "A"
    assert len(sched.list_schedules(db, user_id=USER)) == 2

    upd = sched.update_schedule(db, a.id, ScheduleUpdate(
        title="A2", priority="low", start_time="13:00", status="completed"))
    assert upd.title == "A2" and upd.priority == "low"
    assert upd.start_time == "13:00" and upd.status == "completed"
    assert db.get(PlannerItem, a.id).priority == "LOW"
    assert db.get(PlannerItem, a.id).event_detail.start_at == "2026-06-30T13:00:00"


# --------------------------------------------------------------------------- #
# To-do: completed conversion
# --------------------------------------------------------------------------- #
def test_todo_completed_conversion(db):
    open_todo = todo.create_todo(db, TodoCreate(title="청소", due_date="2026-07-01"),
                                 user_id=USER)
    assert open_todo.completed is False
    assert open_todo.status == "scheduled"
    assert open_todo.due_date == "2026-07-01"
    assert db.get(PlannerItem, open_todo.id).status == "SCHEDULED"

    done = todo.create_todo(db, TodoCreate(title="끝난일", completed=True), user_id=USER)
    assert done.completed is True
    assert done.status == "completed"
    assert db.get(PlannerItem, done.id).status == "COMPLETED"
    assert db.get(PlannerItem, done.id).todo_detail.completed_at is not None


def test_todo_update_toggles_completed(db):
    t = todo.create_todo(db, TodoCreate(title="t"), user_id=USER)
    done = todo.update_todo(db, t.id, TodoUpdate(completed=True))
    assert done.completed is True and done.status == "completed"
    reopened = todo.update_todo(db, t.id, TodoUpdate(completed=False))
    assert reopened.completed is False
    assert db.get(PlannerItem, t.id).todo_detail.completed_at is None


# --------------------------------------------------------------------------- #
# Soft delete + listing
# --------------------------------------------------------------------------- #
def test_soft_delete_sets_timestamp_and_excludes_from_list(db):
    a = sched.create_schedule(db, _new_schedule(title="A"), user_id=USER, calendar_id=CAL)
    b = sched.create_schedule(db, _new_schedule(title="B"), user_id=USER, calendar_id=CAL)
    assert sched.delete_schedule(db, a.id) is True

    # deleted_at recorded in DB
    assert repo.get_planner_item(db, a.id, include_deleted=True).deleted_at is not None
    # excluded from get + list
    assert sched.get_schedule(db, a.id) is None
    remaining = [s.id for s in sched.list_schedules(db, user_id=USER)]
    assert a.id not in remaining and b.id in remaining


# --------------------------------------------------------------------------- #
# Missing-id safety
# --------------------------------------------------------------------------- #
def test_missing_id_is_safe(db):
    assert sched.get_schedule(db, "nope") is None
    assert todo.get_todo(db, "nope") is None
    assert sched.update_schedule(db, "nope", ScheduleUpdate(title="x")) is None
    assert todo.update_todo(db, "nope", TodoUpdate(title="x")) is None
    assert sched.delete_schedule(db, "nope") is False
    assert todo.delete_todo(db, "nope") is False


# --------------------------------------------------------------------------- #
# repository date filters
# --------------------------------------------------------------------------- #
def test_list_events_and_todos_by_date(db):
    sched.create_schedule(db, _new_schedule(date="2026-06-30"), user_id=USER, calendar_id=CAL)
    sched.create_schedule(db, _new_schedule(date="2026-07-01"), user_id=USER, calendar_id=CAL)
    todo.create_todo(db, TodoCreate(title="td", due_date="2026-06-30"), user_id=USER)

    assert len(repo.list_events_by_date(db, user_id=USER, date="2026-06-30")) == 1
    assert len(repo.list_todos_by_due_date(db, user_id=USER, due_date="2026-06-30")) == 1


def test_update_schedule_date_only_shifts_both_start_and_end(db):
    """Changing only the date must move end_at to the new date too (CHECK end>start)."""
    r = sched.create_schedule(db, _new_schedule(date="2026-06-30",
                              start_time="14:00", end_time="15:00"),
                              user_id=USER, calendar_id=CAL)
    u = sched.update_schedule(db, r.id, ScheduleUpdate(date="2026-07-05"))
    assert u.date == "2026-07-05"
    assert u.start_time == "14:00" and u.end_time == "15:00"
    row = db.get(PlannerItem, r.id)
    assert row.event_detail.start_at == "2026-07-05T14:00:00"
    assert row.event_detail.end_at == "2026-07-05T15:00:00"
