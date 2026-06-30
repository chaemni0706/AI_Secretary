"""Backend-A end-to-end integration flows (Stage 10).

Exercises the real API surface via TestClient against an isolated temp SQLite
DB, simulating the pre-Flutter usage flows. Each test gets a fresh DB (function
scope) so data is isolated. Does not import conftest; no external calls.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.database.init_db import apply_schema_to_sqlite_file
from backend.database.session import create_sqlite_engine, get_db
from backend.main import app

# fixed clock so relative date parsing / next_schedule are deterministic
NOW = "2026-06-29T10:00:00+09:00"   # Monday -> '내일' = 2026-06-30
DAY = "2026-06-30"


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "integration.db"
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


def _envelope(r, *, status=200):
    """Assert no 500, status, and the common {success, message, data} envelope."""
    assert r.status_code == status, (r.status_code, r.text)
    assert r.status_code < 500
    body = r.json()
    assert "success" in body and "message" in body and "data" in body, body
    assert isinstance(body["message"], str) and body["message"]
    return body


# --------------------------------------------------------------------------- #
# Scenario 1: NL parse -> save (from-draft) -> list
# --------------------------------------------------------------------------- #
def test_scenario1_parse_save_list(client):
    parsed = _envelope(client.post("/api/v1/ai/schedule/parse",
                       json={"input": "내일 오후 2시에 병원 예약 잡아줘", "current_datetime": NOW}))["data"]
    draft = parsed["schedule_draft"]
    assert draft["title"] and draft["date"] == DAY and draft["start_time"] == "14:00"

    saved = _envelope(client.post("/api/v1/local/schedules/from-draft",
                      json={"schedule_draft": draft, "intent": parsed["intent"]}))["data"]
    sid = saved["id"]
    assert saved["date"] == DAY and saved["start_time"] == "14:00" and saved["source"] == "ai"

    listed = _envelope(client.get("/api/v1/local/schedules"))["data"]
    assert any(s["id"] == sid for s in listed)


# --------------------------------------------------------------------------- #
# Scenario 2: save schedule + todo -> dashboard summary
# --------------------------------------------------------------------------- #
def test_scenario2_dashboard_summary(client):
    _envelope(client.post("/api/v1/local/schedules",
              json={"title": "회의", "date": DAY, "start_time": "10:00", "priority": "medium"}))
    _envelope(client.post("/api/v1/local/todos",
              json={"title": "리포트", "due_date": DAY, "priority": "high", "completed": False}))
    _envelope(client.post("/api/v1/local/todos",
              json={"title": "메일", "due_date": DAY, "priority": "low", "completed": True}))

    data = _envelope(client.get("/api/v1/dashboard/summary",
                     params={"date": DAY, "current_datetime": f"{DAY}T09:00:00+09:00"}))["data"]
    assert data["total_schedule_count"] == 1
    assert data["total_todo_count"] == 2
    assert data["completed_todo_count"] == 1
    assert data["todo_completion_rate"] == 0.5
    assert data["next_schedule"]["title"] == "회의"


# --------------------------------------------------------------------------- #
# Scenario 3: personal memory -> notification plan reflects it
# --------------------------------------------------------------------------- #
def test_scenario3_memory_into_notification_plan(client):
    _envelope(client.put("/api/v1/memory/u1",
              json={"notification_preference": "late_prone",
                    "default_travel_minutes": 40, "default_buffer_minutes": 5}))
    sid = _envelope(client.post("/api/v1/local/schedules",
                    json={"title": "병원", "date": DAY, "start_time": "14:00",
                          "category": "hospital"}))["data"]["id"]

    plan = _envelope(client.post("/api/v1/notifications/plan",
                     json={"schedule_id": sid, "user_id": "u1", "weather": "rain"}))["data"]
    assert plan["applied_preference"] == "late_prone"
    assert plan["applied_travel_minutes"] == 40
    assert plan["applied_buffer_minutes"] == 5
    assert plan["leave_time"] == "13:15"            # 14:00 - 40 - 5
    times = [n["time"] for n in plan["notifications"]]
    assert times == sorted(times) and len(times) >= 1
    assert any(c["item"] == "우산" for c in plan["checklist"])   # weather=rain


# --------------------------------------------------------------------------- #
# Scenario 4: stored schedules -> from-store reservation candidates
# --------------------------------------------------------------------------- #
def test_scenario4_reservation_from_store(client):
    for title, st, en in [("팀플", "18:00", "19:00"), ("저녁", "20:00", "21:00")]:
        _envelope(client.post("/api/v1/local/schedules",
                  json={"title": title, "date": DAY, "start_time": st, "end_time": en}))

    data = _envelope(client.post("/api/v1/reservations/candidates/from-store",
                     json={"target_date": DAY, "duration_minutes": 60,
                           "preferred_start_time": "18:00", "preferred_end_time": "21:00"}))["data"]
    cands = data["recommended_candidates"]
    assert cands
    # no candidate overlaps either busy block
    def overlaps(c, bs, be):
        s = int(c["start_time"][:2]) * 60 + int(c["start_time"][3:])
        e = int(c["end_time"][:2]) * 60 + int(c["end_time"][3:])
        return s < be and bs < e
    for c in cands:
        assert not overlaps(c, 18 * 60, 19 * 60)
        assert not overlaps(c, 20 * 60, 21 * 60)
    # the 19:00-20:00 gap should be recommended
    assert any(c["start_time"] == "19:00" for c in cands)


# --------------------------------------------------------------------------- #
# Cross-scenario: stable responses for not-found / invalid (no 500)
# --------------------------------------------------------------------------- #
def test_stability_no_500_on_edge_inputs(client):
    # unknown schedule -> 404 envelope (not 500)
    _envelope(client.get("/api/v1/local/schedules/nope"), status=404)
    _envelope(client.post("/api/v1/notifications/plan", json={"schedule_id": "nope"}), status=404)
    # empty dashboard -> stable 200
    empty = _envelope(client.get("/api/v1/dashboard/today",
                      params={"date": DAY, "current_datetime": f"{DAY}T09:00:00+09:00"}))["data"]
    assert empty["total_schedule_count"] == 0 and empty["next_schedule"] is None
    # from-store with no stored schedules -> stable 200
    rs = _envelope(client.post("/api/v1/reservations/candidates/from-store",
                   json={"target_date": DAY, "duration_minutes": 60,
                         "preferred_start_time": "14:00", "preferred_end_time": "15:00"}))["data"]
    assert rs["target_date"] == DAY
