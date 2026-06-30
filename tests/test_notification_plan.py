"""Stored-schedule notification plan tests (Stage 8).

Seeds schedules/memory via the real APIs, then checks /notifications/plan.
Reuses departure_alert logic; does not touch /alerts/departure-plan.
Isolated temp DB via get_db override; does not import conftest.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.database.init_db import apply_schema_to_sqlite_file
from backend.database.models import Calendar, EventDetail, PlannerItem, Reminder, User
from backend.database.session import create_sqlite_engine, get_db
from backend.main import app

SB = "/api/v1/local/schedules"
PLAN = "/api/v1/notifications/plan"
NOW = "2026-06-30T09:00:00"


@pytest.fixture()
def ctx(tmp_path):
    db_file = tmp_path / "notif.db"
    apply_schema_to_sqlite_file(db_file)
    engine = create_sqlite_engine(f"sqlite:///{db_file.as_posix()}")
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def _override():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c, TestingSession
    app.dependency_overrides.clear()
    engine.dispose()


def _new_schedule(client, **over):
    body = {"title": "병원 예약", "date": "2026-06-30", "start_time": "14:00",
            "category": "hospital", "priority": "high"}
    body.update(over)
    r = client.post(SB, json=body)
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"]


def _plan(client, **body):
    r = client.post(PLAN, json=body)
    return r


# --------------------------------------------------------------------------- #
# Basic plan from a stored schedule
# --------------------------------------------------------------------------- #
def test_plan_from_stored_schedule(ctx):
    client, _ = ctx
    sid = _new_schedule(client, start_time="14:00")
    r = _plan(client, schedule_id=sid, travel_minutes=30, buffer_minutes=10)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["schedule_id"] == sid
    assert data["leave_time"] == "13:20"          # 14:00 - 30 - 10
    assert data["applied_travel_minutes"] == 30
    assert data["applied_buffer_minutes"] == 10
    assert data["source"] == "stored_schedule"
    assert any(c["item"] == "신분증" for c in data["checklist"])  # hospital base


# --------------------------------------------------------------------------- #
# memory defaults applied when request omits them
# --------------------------------------------------------------------------- #
def test_memory_defaults_applied(ctx):
    client, _ = ctx
    client.patch("/api/v1/memory/u1/preferences",
                 json={"default_travel_minutes": 45, "default_buffer_minutes": 15})
    sid = _new_schedule(client, start_time="14:00")
    data = _plan(client, schedule_id=sid, user_id="u1").json()["data"]
    assert data["applied_travel_minutes"] == 45
    assert data["applied_buffer_minutes"] == 15
    assert data["leave_time"] == "13:00"          # 14:00 - 45 - 15


def test_late_prone_preference_from_memory(ctx):
    client, _ = ctx
    client.patch("/api/v1/memory/u1/preferences", json={"notification_preference": "late_prone"})
    sid = _new_schedule(client, start_time="14:00")
    late = _plan(client, schedule_id=sid, user_id="u1",
                 travel_minutes=30, buffer_minutes=10).json()["data"]
    normal = _plan(client, schedule_id=sid, travel_minutes=30, buffer_minutes=10).json()["data"]
    assert late["applied_preference"] == "late_prone"
    # late_prone adds earlier/extra departure reminders
    assert len(late["notifications"]) > len(normal["notifications"])
    times = [n["time"] for n in late["notifications"]]
    assert times == sorted(times)                 # ascending


# --------------------------------------------------------------------------- #
# request value beats memory
# --------------------------------------------------------------------------- #
def test_request_overrides_memory(ctx):
    client, _ = ctx
    client.patch("/api/v1/memory/u1/preferences", json={"default_travel_minutes": 60})
    sid = _new_schedule(client, start_time="14:00")
    data = _plan(client, schedule_id=sid, user_id="u1", travel_minutes=20).json()["data"]
    assert data["applied_travel_minutes"] == 20    # request wins over memory's 60


# --------------------------------------------------------------------------- #
# notifications sorted ascending
# --------------------------------------------------------------------------- #
def test_notifications_time_sorted(ctx):
    client, _ = ctx
    sid = _new_schedule(client, start_time="14:00")
    data = _plan(client, schedule_id=sid, travel_minutes=35, buffer_minutes=10,
                 notification_preference="strong").json()["data"]
    times = [n["time"] for n in data["notifications"]]
    assert times == sorted(times)
    assert len(times) >= 1


# --------------------------------------------------------------------------- #
# missing schedule -> 404 stable
# --------------------------------------------------------------------------- #
def test_missing_schedule_returns_404(ctx):
    client, _ = ctx
    r = _plan(client, schedule_id="nope")
    assert r.status_code == 404
    assert r.json()["success"] is False


# --------------------------------------------------------------------------- #
# malformed start_time -> stable (leave_time None, no 500)
# --------------------------------------------------------------------------- #
def test_malformed_start_time_is_stable(ctx):
    client, Session = ctx
    # inject a planner EVENT with an unparseable start_at directly
    db = Session()
    try:
        db.add(User(user_id="local-user", created_at=NOW, updated_at=NOW)); db.commit()
        db.add(Calendar(calendar_id="cal-x", user_id="local-user", name="c",
                        is_primary=1, created_at=NOW, updated_at=NOW)); db.commit()
        db.add(PlannerItem(item_id="bad1", user_id="local-user", item_type="EVENT",
                           title="깨진일정", status="SCHEDULED", priority="MEDIUM",
                           source_type="MANUAL", created_at=NOW, updated_at=NOW)); db.commit()
        db.add(EventDetail(item_id="bad1", calendar_id="cal-x", start_at="invalid")); db.commit()
    finally:
        db.close()
    r = _plan(client, schedule_id="bad1")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["leave_time"] is None
    assert data["notifications"] == []


# --------------------------------------------------------------------------- #
# optional persistence to reminders table
# --------------------------------------------------------------------------- #
def test_persist_writes_reminders(ctx):
    client, Session = ctx
    sid = _new_schedule(client, start_time="14:00")
    data = _plan(client, schedule_id=sid, travel_minutes=30, buffer_minutes=10,
                 persist=True).json()["data"]
    assert data["persisted_reminders"] >= 1
    db = Session()
    try:
        rows = db.query(Reminder).filter(Reminder.item_id == sid).all()
    finally:
        db.close()
    assert len(rows) == data["persisted_reminders"]
    assert any(r.reminder_type == "DEPARTURE" for r in rows)


# --------------------------------------------------------------------------- #
# Stage 8.1 — notification_preference validation (422 on invalid)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("pref", ["normal", "strong", "forgetful", "late_prone"])
def test_valid_notification_preference_accepted(ctx, pref):
    client, _ = ctx
    sid = _new_schedule(client, start_time="14:00")
    r = _plan(client, schedule_id=sid, travel_minutes=30, buffer_minutes=10,
              notification_preference=pref)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["applied_preference"] == pref


def test_invalid_notification_preference_returns_422(ctx):
    client, _ = ctx
    sid = _new_schedule(client, start_time="14:00")
    r = _plan(client, schedule_id=sid, notification_preference="panic")
    assert r.status_code == 422
    assert r.json()["success"] is False


def test_invalid_notification_preference_422_on_get_variant(ctx):
    client, _ = ctx
    sid = _new_schedule(client, start_time="14:00")
    r = client.get(f"{PLAN}/{sid}", params={"notification_preference": "panic"})
    assert r.status_code == 422
