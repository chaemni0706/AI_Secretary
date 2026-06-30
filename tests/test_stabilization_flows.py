"""Pre-Flutter integration regression tests.

Covers the end-to-end flows that the Flutter client depends on, all against an
isolated temp SQLite DB (no OpenAI / external APIs). Mirrors the get_db override
pattern used in test_dashboard.py so it never touches the runtime DB.

Flows verified:
  1. schedule CRUD (create/list/get/update/delete)
  2. todo CRUD (create/list/get/update/delete + complete toggle)
  3. parse -> schedule from-draft -> persisted
  4. todo draft -> todo from-draft -> persisted
  5. dashboard/today returns saved schedules + todos + stats block
  6. reservation candidates excludes conflicting times
  7. reservation candidate -> schedule from-draft save
  8. notification plan create + retrieve
  9. notification plan duplicate create does not raise (no UNIQUE crash)
 10. missing schedule/todo id -> 404 envelope, never a 500
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
D = "2026-07-03"


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "flows.db"
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


def _data(r, status=200):
    assert r.status_code == status, (r.status_code, r.text)
    body = r.json()
    assert {"success", "message", "data"}.issubset(body.keys()), body
    return body


# --- 1. schedule CRUD --------------------------------------------------------
def test_schedule_crud_flow(client):
    created = _data(client.post(SB, json={
        "title": "치과 예약", "date": D, "start_time": "14:00",
        "end_time": "15:00", "category": "hospital", "priority": "high",
        "location": "강남역",
    }))["data"]
    sid = created["id"]
    assert created["title"] == "치과 예약" and created["status"] == "scheduled"

    listed = _data(client.get(SB, params={"date": D}))["data"]
    assert any(s["id"] == sid for s in listed)

    one = _data(client.get(f"{SB}/{sid}"))["data"]
    assert one["id"] == sid

    patched = _data(client.patch(f"{SB}/{sid}", json={"title": "치과 재예약"}))["data"]
    assert patched["title"] == "치과 재예약"

    deleted = _data(client.delete(f"{SB}/{sid}"))["data"]
    assert deleted["deleted"] is True
    assert client.get(f"{SB}/{sid}").status_code == 404


def test_schedule_optional_fields_and_validation(client):
    # no end_time / no location is allowed
    ok = _data(client.post(SB, json={"title": "종일", "date": D, "start_time": "09:00"}))["data"]
    assert ok["end_time"] is None and ok["location"] is None and ok["priority"] == "medium"
    # end before start -> 422 (not 500), envelope preserved
    bad = client.post(SB, json={"title": "bad", "date": D, "start_time": "15:00", "end_time": "14:00"})
    assert bad.status_code == 422
    assert bad.json()["success"] is False


# --- 2. todo CRUD ------------------------------------------------------------
def test_todo_crud_flow(client):
    created = _data(client.post(TB, json={"title": "자료 정리", "due_date": D}))["data"]
    tid = created["id"]
    assert created["completed"] is False and created["priority"] == "medium"

    assert any(t["id"] == tid for t in _data(client.get(TB, params={"due_date": D}))["data"])
    assert _data(client.get(f"{TB}/{tid}"))["data"]["id"] == tid

    done = _data(client.patch(f"{TB}/{tid}", json={"completed": True}))["data"]
    assert done["completed"] is True

    assert _data(client.delete(f"{TB}/{tid}"))["data"]["deleted"] is True
    assert client.get(f"{TB}/{tid}").status_code == 404


# --- 3. parse -> from-draft --------------------------------------------------
def test_parse_to_schedule_from_draft(client):
    parsed = _data(client.post("/api/v1/ai/schedule/parse", json={
        "input": "내일 오후 2시에 치과 예약 잡아줘",
        "current_datetime": "2026-07-02T10:00:00+09:00",
    }))["data"]
    draft = parsed["schedule_draft"]
    assert draft["title"] and draft["date"] and draft["start_time"]

    saved = _data(client.post(f"{SB}/from-draft", json={"schedule_draft": draft}))["data"]
    assert saved["id"] and saved["title"] == draft["title"]
    # visible in list
    assert any(s["id"] == saved["id"] for s in _data(client.get(SB, params={"date": draft["date"]}))["data"])


# --- 4. todo draft -> todo ---------------------------------------------------
def test_todo_from_draft(client):
    draft = {"title": "장보기", "date": D, "priority": "medium"}
    saved = _data(client.post(f"{TB}/from-draft", json={"schedule_draft": draft, "intent": "create_todo"}))["data"]
    assert saved["id"] and saved["title"] == "장보기" and saved["due_date"] == D


# --- 5. dashboard/today + stats ---------------------------------------------
def test_dashboard_today_with_stats(client):
    client.post(SB, json={"title": "일정", "date": D, "start_time": "09:00"})
    t = _data(client.post(TB, json={"title": "할일", "due_date": D}))["data"]
    client.patch(f"{TB}/{t['id']}", json={"completed": True})

    data = _data(client.get("/api/v1/dashboard/today", params={"date": D}))["data"]
    assert data["date"] == D
    assert len(data["schedules"]) == 1 and len(data["todos"]) == 1
    stats = data["stats"]
    assert stats["schedule_count"] == 1
    assert stats["todo_count"] == 1
    assert stats["completed_todo_count"] == 1
    assert stats["todo_completion_rate"] == 1.0
    # flat fields kept for backward-compat
    assert data["total_schedule_count"] == 1 and data["total_todo_count"] == 1


# --- 6. reservation excludes conflicts --------------------------------------
def test_reservation_candidates_exclude_conflict(client):
    res = _data(client.post("/api/v1/reservations/candidates", json={
        "constraints": {
            "target_date": D, "preferred_start_time": "13:00",
            "preferred_end_time": "18:00", "duration_minutes": 60,
        },
        "existing_schedules": [
            {"date": D, "start_time": "14:00", "end_time": "15:00"},
        ],
    }))["data"]
    cands = res["recommended_candidates"]
    assert cands, "expected at least one candidate"
    # none of the recommended candidates overlaps 14:00-15:00
    for c in cands:
        assert not (c["start_time"] < "15:00" and c["end_time"] > "14:00"), c
    # the conflicting slot is reported as rejected
    assert any(r["start_time"] == "14:00" for r in res["rejected_slots"])


# --- 7. reservation candidate -> schedule save ------------------------------
def test_reservation_candidate_to_schedule(client):
    res = _data(client.post("/api/v1/reservations/candidates/from-store", json={
        "target_date": D, "duration_minutes": 60,
        "preferred_start_time": "13:00", "preferred_end_time": "18:00",
        "category": "beauty",
    }))["data"]
    chosen = res["recommended_candidates"][0]
    draft = {
        "title": "미용실 예약", "date": D,
        "start_time": chosen["start_time"], "end_time": chosen["end_time"],
        "category": "beauty", "priority": "medium",
    }
    saved = _data(client.post(f"{SB}/from-draft", json={"schedule_draft": draft}))["data"]
    assert saved["start_time"] == chosen["start_time"]
    assert any(s["id"] == saved["id"] for s in _data(client.get(SB, params={"date": D}))["data"])


# --- 8 & 9. notification plan create + retrieve + duplicate ------------------
def test_notification_plan_create_retrieve_and_duplicate(client):
    sid = _data(client.post(SB, json={
        "title": "치과", "date": D, "start_time": "14:00", "category": "hospital",
    }))["data"]["id"]

    first = _data(client.post("/api/v1/notifications/plan", json={
        "schedule_id": sid, "notification_preference": "forgetful", "persist": True,
    }))["data"]
    assert first["schedule_id"] == sid
    assert first["notifications"], "expected notifications"
    assert first["persisted_reminders"] >= 1

    # duplicate create must not raise a UNIQUE/500 error
    dup = client.post("/api/v1/notifications/plan", json={
        "schedule_id": sid, "notification_preference": "forgetful", "persist": True,
    })
    assert dup.status_code == 200, dup.text

    got = _data(client.get(f"/api/v1/notifications/plan/{sid}"))["data"]
    assert got["schedule_id"] == sid and got["notifications"]


# --- 10. missing ids never 500 ----------------------------------------------
def test_missing_ids_return_404_not_500(client):
    for path in (f"{SB}/does-not-exist", f"{TB}/does-not-exist"):
        r = client.get(path)
        assert r.status_code == 404, (path, r.status_code)
        assert r.json()["success"] is False

    # notification plan for a missing schedule -> 404 envelope, not 500
    r = client.post("/api/v1/notifications/plan", json={"schedule_id": "does-not-exist"})
    assert r.status_code == 404, r.text
    assert r.json()["success"] is False
