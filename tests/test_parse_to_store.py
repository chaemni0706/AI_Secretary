"""parse -> confirm -> store flow tests (Stage 5).

The existing /ai/schedule/parse endpoint is unchanged (parse-only). The new
from-draft endpoints persist a confirmed schedule_draft into planner_items.
Isolated temp DB via get_db override; does not import conftest.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.database.init_db import apply_schema_to_sqlite_file
from backend.database.session import create_sqlite_engine, get_db
from backend.main import app

PARSE = "/api/v1/ai/schedule/parse"
SB = "/api/v1/local/schedules"
TB = "/api/v1/local/todos"
NOW = "2026-06-29T10:00:00+09:00"  # Monday -> '내일' = 2026-06-30


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "p2s.db"
    apply_schema_to_sqlite_file(db_file)
    engine = create_sqlite_engine(f"sqlite:///{db_file.as_posix()}")
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

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


# --------------------------------------------------------------------------- #
# parse API must stay parse-only and structurally stable
# --------------------------------------------------------------------------- #
def test_parse_response_structure_unchanged(client):
    r = client.post(PARSE, json={"input": "내일 오후 2시에 병원 예약 잡아줘", "current_datetime": NOW})
    assert r.status_code == 200
    data = r.json()["data"]
    assert set(data.keys()) == {
        "intent", "confidence", "slots", "schedule_draft", "missing_fields"
    }
    # parse alone must NOT have stored anything
    assert client.get(SB).json()["data"] == []


# --------------------------------------------------------------------------- #
# parse -> store schedule -> appears in list
# --------------------------------------------------------------------------- #
def test_parse_then_store_schedule(client):
    parsed = client.post(PARSE, json={"input": "내일 오후 2시에 병원 예약 잡아줘",
                                       "current_datetime": NOW}).json()["data"]
    draft = parsed["schedule_draft"]
    assert draft["title"] and draft["date"] and draft["start_time"]

    saved = client.post(f"{SB}/from-draft", json={"schedule_draft": draft})
    assert saved.status_code == 200, saved.text
    data = saved.json()["data"]
    assert data["title"] == draft["title"]
    assert data["date"] == draft["date"]
    assert data["start_time"] == draft["start_time"]
    assert data["source"] == "ai"

    listed = client.get(SB).json()["data"]
    assert any(s["id"] == data["id"] for s in listed)


# --------------------------------------------------------------------------- #
# store todo from a (create_todo) draft -> appears in list
# --------------------------------------------------------------------------- #
def test_store_todo_from_draft(client):
    draft = {"title": "리포트 제출", "date": "2026-07-01", "category": "study",
             "priority": "high", "memo": "1페이지", "source": "ai"}
    r = client.post(f"{TB}/from-draft", json={"schedule_draft": draft, "intent": "create_todo"})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["title"] == "리포트 제출"
    assert data["due_date"] == "2026-07-01"
    assert data["priority"] == "high"
    assert data["completed"] is False
    assert any(t["id"] == data["id"] for t in client.get(TB).json()["data"])


# --------------------------------------------------------------------------- #
# all-day handling: no start_time -> saved as 00:00 (no 500)
# --------------------------------------------------------------------------- #
def test_schedule_all_day_when_no_start_time(client):
    r = client.post(f"{SB}/from-draft", json={"schedule_draft": {"title": "종일 일정", "date": "2026-06-30"}})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["start_time"] == "00:00"


# --------------------------------------------------------------------------- #
# missing / invalid fields -> stable 422 (never 500)
# --------------------------------------------------------------------------- #
def test_missing_title_returns_422(client):
    r = client.post(f"{SB}/from-draft", json={"schedule_draft": {"date": "2026-06-30", "start_time": "14:00"}})
    assert r.status_code == 422 and r.json()["success"] is False


def test_missing_date_returns_422(client):
    r = client.post(f"{SB}/from-draft", json={"schedule_draft": {"title": "x", "start_time": "14:00"}})
    assert r.status_code == 422


def test_invalid_time_returns_422(client):
    r = client.post(f"{SB}/from-draft", json={"schedule_draft": {"title": "x", "date": "2026-06-30", "start_time": "25:99"}})
    assert r.status_code == 422


def test_todo_missing_title_returns_422(client):
    r = client.post(f"{TB}/from-draft", json={"schedule_draft": {"date": "2026-07-01"}})
    assert r.status_code == 422 and r.json()["success"] is False
