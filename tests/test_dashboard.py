"""Dashboard aggregation API tests (Stage 6).

Seeds data through the real local Schedule/To-do endpoints, then verifies the
dashboard aggregates/sorting via /dashboard/today and /dashboard/summary.
Isolated temp DB via get_db override; does not import conftest.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.database.init_db import apply_schema_to_sqlite_file
from backend.database.session import create_sqlite_engine, get_db
from backend.main import app

SB = "/api/v1/local/schedules"
TB = "/api/v1/local/todos"
TODAY = "/api/v1/dashboard/today"
SUMMARY = "/api/v1/dashboard/summary"
D = "2026-06-30"
OTHER = "2026-07-01"


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "dash.db"
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
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


def _sched(client, **over):
    body = {"title": "일정", "date": D, "start_time": "10:00", "priority": "medium"}
    body.update(over)
    r = client.post(SB, json=body)
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _todo(client, **over):
    body = {"title": "할일", "due_date": D, "priority": "medium", "completed": False}
    body.update(over)
    r = client.post(TB, json=body)
    assert r.status_code == 200, r.text
    return r.json()["data"]


# --------------------------------------------------------------------------- #
# Empty data -> stable response
# --------------------------------------------------------------------------- #
def test_empty_dashboard_is_stable(client):
    data = client.get(TODAY, params={"date": D, "current_datetime": f"{D}T09:00:00+09:00"}).json()["data"]
    assert data["date"] == D
    assert data["schedules"] == [] and data["todos"] == []
    assert data["total_schedule_count"] == 0 and data["total_todo_count"] == 0
    assert data["todo_completion_rate"] == 0.0
    assert data["next_schedule"] is None
    assert "없습니다" in data["summary_message"]


# --------------------------------------------------------------------------- #
# Date filtering: only items on the requested date
# --------------------------------------------------------------------------- #
def test_date_filters_schedules_and_todos(client):
    _sched(client, title="오늘", date=D, start_time="10:00")
    _sched(client, title="내일", date=OTHER, start_time="10:00")
    _todo(client, title="오늘할일", due_date=D)
    _todo(client, title="내일할일", due_date=OTHER)

    data = client.get(TODAY, params={"date": D, "current_datetime": f"{D}T09:00:00+09:00"}).json()["data"]
    assert data["total_schedule_count"] == 1 and data["schedules"][0]["title"] == "오늘"
    assert data["total_todo_count"] == 1 and data["todos"][0]["title"] == "오늘할일"


# --------------------------------------------------------------------------- #
# next_schedule = earliest schedule at/after current time
# --------------------------------------------------------------------------- #
def test_next_schedule_respects_current_time(client):
    _sched(client, title="오전", date=D, start_time="10:00", end_time="11:00")
    _sched(client, title="오후", date=D, start_time="14:00", end_time="15:00")

    early = client.get(TODAY, params={"date": D, "current_datetime": f"{D}T09:00:00+09:00"}).json()["data"]
    assert early["next_schedule"]["title"] == "오전"

    midday = client.get(TODAY, params={"date": D, "current_datetime": f"{D}T12:00:00+09:00"}).json()["data"]
    assert midday["next_schedule"]["title"] == "오후"

    late = client.get(TODAY, params={"date": D, "current_datetime": f"{D}T20:00:00+09:00"}).json()["data"]
    assert late["next_schedule"] is None


# --------------------------------------------------------------------------- #
# completion rate
# --------------------------------------------------------------------------- #
def test_todo_completion_rate(client):
    _todo(client, title="a", completed=False)
    _todo(client, title="b", completed=False)
    _todo(client, title="c", completed=True)
    data = client.get(SUMMARY, params={"date": D, "current_datetime": f"{D}T09:00:00+09:00"}).json()["data"]
    assert data["total_todo_count"] == 3
    assert data["completed_todo_count"] == 1
    assert data["todo_completion_rate"] == 0.33


# --------------------------------------------------------------------------- #
# high priority extraction (schedules + todos)
# --------------------------------------------------------------------------- #
def test_high_priority_items(client):
    _sched(client, title="중요일정", priority="high", start_time="09:00")
    _sched(client, title="보통일정", priority="medium", start_time="10:00")
    _todo(client, title="중요할일", priority="high")
    data = client.get(TODAY, params={"date": D, "current_datetime": f"{D}T08:00:00+09:00"}).json()["data"]
    hp = data["high_priority_items"]
    titles = {h["title"] for h in hp}
    types = {h["type"] for h in hp}
    assert titles == {"중요일정", "중요할일"}
    assert types == {"schedule", "todo"}


# --------------------------------------------------------------------------- #
# sorting rules
# --------------------------------------------------------------------------- #
def test_schedule_sorted_by_start_time(client):
    _sched(client, title="C", start_time="16:00", end_time=None)
    _sched(client, title="A", start_time="08:00", end_time=None)
    _sched(client, title="B", start_time="12:00", end_time=None)
    data = client.get(TODAY, params={"date": D, "current_datetime": f"{D}T07:00:00+09:00"}).json()["data"]
    assert [s["title"] for s in data["schedules"]] == ["A", "B", "C"]


def test_todo_sorted_incomplete_then_priority(client):
    _todo(client, title="low-open", priority="low", completed=False)
    _todo(client, title="high-open", priority="high", completed=False)
    _todo(client, title="med-done", priority="medium", completed=True)
    data = client.get(TODAY, params={"date": D, "current_datetime": f"{D}T09:00:00+09:00"}).json()["data"]
    order = [t["title"] for t in data["todos"]]
    assert order[0] == "high-open"
    assert order[1] == "low-open"
    assert order[-1] == "med-done"


# --------------------------------------------------------------------------- #
# envelope + summary fields
# --------------------------------------------------------------------------- #
def test_summary_envelope_and_fields(client):
    _sched(client, start_time="10:00")
    r = client.get(SUMMARY, params={"date": D, "current_datetime": f"{D}T09:00:00+09:00"})
    assert r.status_code == 200
    body = r.json()
    assert {"success", "message", "data"}.issubset(body.keys())
    data = body["data"]
    assert {"date", "total_schedule_count", "total_todo_count", "completed_todo_count",
            "todo_completion_rate", "high_priority_items", "next_schedule",
            "summary_message"}.issubset(data.keys())
    # summary is lightweight: no full arrays
    assert "schedules" not in data and "todos" not in data
