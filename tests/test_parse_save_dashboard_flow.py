"""End-to-end integration flow tests (Flutter-critical path).

    natural language
      -> POST /ai/schedule/parse/enhanced         (use_llm=false; no real LLM)
      -> POST /ai/schedule/confirm                 (EVENT -> schedule, TODO -> todo)
      -> GET  /dashboard/today?date=...            (saved item shows up)

Isolated temp SQLite via get_db override (does NOT import conftest). Base date
is fixed to 2026-07-01 so relative dates resolve deterministically.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.database.init_db import apply_schema_to_sqlite_file
from backend.database.session import create_sqlite_engine, get_db
from backend.main import app

PARSE = "/api/v1/ai/schedule/parse/enhanced"
CONFIRM = "/api/v1/ai/schedule/confirm"
DASH = "/api/v1/dashboard/today"
TODAY = "2026-07-01"
TOMORROW = "2026-07-02"
USER = "local-user"


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "flow.db"
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


# --------------------------------------------------------------------------- #
# helpers — each asserts the common envelope as it goes
# --------------------------------------------------------------------------- #
def _envelope(r):
    assert r.status_code == 200, r.text
    body = r.json()
    assert {"success", "message", "data"}.issubset(body.keys())
    assert body["success"] is True
    assert isinstance(body["message"], str) and body["message"]
    return body["data"]


def _parse(client, text, today=TODAY):
    r = client.post(PARSE, json={"text": text, "today": today,
                                 "timezone": "Asia/Seoul", "use_llm": False})
    return _envelope(r)


def _confirm(client, parsed, *, item_type=None, user_id=USER):
    body = {"user_id": user_id, "parsed": parsed}
    if item_type is not None:
        body["item_type"] = item_type
    return client.post(CONFIRM, json=body)


def _dash(client, date=TODAY, user_id=USER):
    return _envelope(client.get(DASH, params={"date": date, "user_id": user_id}))


def _parsed_payload(data):
    """Trim an enhanced-parse result down to the confirm `parsed` shape."""
    keys = ("original_text", "title", "date", "start_time", "end_time",
            "category", "location", "memo", "is_all_day", "item_type")
    return {k: data.get(k) for k in keys}


# --------------------------------------------------------------------------- #
# 1. schedule: parse -> confirm -> dashboard
# --------------------------------------------------------------------------- #
def test_schedule_flow_parse_confirm_dashboard(client):
    parsed = _parse(client, "오늘 오후 3시에 병원 예약 있어")
    assert parsed["title"] == "병원 예약"
    assert parsed["date"] == TODAY
    assert parsed["start_time"] == "15:00"
    assert parsed["category"] == "health"
    assert parsed["item_type"] == "EVENT"

    saved = _envelope(_confirm(client, _parsed_payload(parsed)))
    sch = saved["schedule"]
    assert sch["id"]
    assert sch["title"] == "병원 예약" and sch["date"] == TODAY and sch["start_time"] == "15:00"

    dash = _dash(client, TODAY)
    assert dash["date"] == TODAY
    titles = [s["title"] for s in dash["schedules"]]
    assert "병원 예약" in titles
    hit = next(s for s in dash["schedules"] if s["title"] == "병원 예약")
    assert hit["id"] == sch["id"] and hit["date"] == TODAY and hit["start_time"] == "15:00"


# --------------------------------------------------------------------------- #
# 2. todo: parse -> confirm -> dashboard
# --------------------------------------------------------------------------- #
def test_todo_flow_parse_confirm_dashboard(client):
    parsed = _parse(client, "오늘까지 과제 제출해야 해")
    assert parsed["item_type"] == "TODO"
    assert parsed["title"] == "과제 제출"       # cleaned of command form / 까지
    assert parsed["date"] == TODAY

    saved = _envelope(_confirm(client, _parsed_payload(parsed)))
    todo = saved["todo"]
    assert todo["id"]
    assert todo["title"] == "과제 제출"
    assert todo["due_date"] == TODAY
    assert todo["completed"] is False

    dash = _dash(client, TODAY)
    titles = [t["title"] for t in dash["todos"]]
    assert "과제 제출" in titles
    hit = next(t for t in dash["todos"] if t["title"] == "과제 제출")
    assert hit["id"] == todo["id"] and hit["due_date"] == TODAY
    assert hit["completed"] is False


# --------------------------------------------------------------------------- #
# 3. schedule + todo together on the same date
# --------------------------------------------------------------------------- #
def test_schedule_and_todo_same_day_dashboard(client):
    _envelope(_confirm(client, _parsed_payload(_parse(client, "오늘 오후 3시에 병원 예약 있어"))))
    _envelope(_confirm(client, _parsed_payload(_parse(client, "오늘까지 과제 제출해야 해"))))

    dash = _dash(client, TODAY)
    assert "병원 예약" in [s["title"] for s in dash["schedules"]]
    assert "과제 제출" in [t["title"] for t in dash["todos"]]
    assert dash["total_schedule_count"] >= 1 and dash["total_todo_count"] >= 1


# --------------------------------------------------------------------------- #
# 4. tomorrow's schedule is NOT on today's dashboard, but IS on tomorrow's
# --------------------------------------------------------------------------- #
def test_tomorrow_schedule_date_consistency(client):
    parsed = _parse(client, "내일 오후 3시 회의")
    assert parsed["date"] == TOMORROW
    _envelope(_confirm(client, _parsed_payload(parsed)))

    today_dash = _dash(client, TODAY)
    assert "회의" not in [s["title"] for s in today_dash["schedules"]]

    tomorrow_dash = _dash(client, TOMORROW)
    assert "회의" in [s["title"] for s in tomorrow_dash["schedules"]]


# --------------------------------------------------------------------------- #
# 5. todo due_date matches the dashboard date filter
# --------------------------------------------------------------------------- #
def test_todo_due_date_matches_dashboard_filter(client):
    parsed = _parse(client, "내일까지 보고서 작성해야 해")
    assert parsed["item_type"] == "TODO"
    assert parsed["date"] == TOMORROW
    _envelope(_confirm(client, _parsed_payload(parsed)))

    assert parsed["title"] not in [t["title"] for t in _dash(client, TODAY)["todos"]]
    assert parsed["title"] in [t["title"] for t in _dash(client, TOMORROW)["todos"]]


# --------------------------------------------------------------------------- #
# 6. confirm rejects a parse with no date (422, not 500)
# --------------------------------------------------------------------------- #
def test_confirm_rejects_missing_date(client):
    r = _confirm(client, {"title": "병원 예약", "start_time": "15:00", "item_type": "EVENT"})
    assert r.status_code == 422
    assert r.json()["success"] is False


def test_confirm_rejects_todo_missing_due_date(client):
    r = _confirm(client, {"title": "과제 제출", "item_type": "TODO"})
    assert r.status_code == 422
    assert r.json()["success"] is False


# --------------------------------------------------------------------------- #
# 7. normal schedule without start_time is rejected (422)
# --------------------------------------------------------------------------- #
def test_confirm_rejects_timed_schedule_without_start_time(client):
    r = _confirm(client, {"title": "회의", "date": TODAY, "is_all_day": False, "item_type": "EVENT"})
    assert r.status_code == 422


# --------------------------------------------------------------------------- #
# 8. all-day schedule saves without start_time and shows on the dashboard
# --------------------------------------------------------------------------- #
def test_allday_schedule_without_start_time_ok(client):
    parsed = {"title": "워크숍", "date": TODAY, "start_time": None,
              "is_all_day": True, "category": "work", "item_type": "EVENT"}
    saved = _envelope(_confirm(client, parsed))
    assert saved["schedule"]["title"] == "워크숍"
    assert "워크숍" in [s["title"] for s in _dash(client, TODAY)["schedules"]]


# --------------------------------------------------------------------------- #
# 9. empty dashboard -> 200 with empty arrays (no 500)
# --------------------------------------------------------------------------- #
def test_empty_dashboard_returns_empty_arrays(client):
    dash = _dash(client, TODAY)
    assert dash["schedules"] == [] and dash["todos"] == []
    assert dash["total_schedule_count"] == 0 and dash["total_todo_count"] == 0


def test_dashboard_invalid_date_is_safe(client):
    # invalid date must not 500 — it simply matches nothing
    data = _envelope(client.get(DASH, params={"date": "not-a-date", "user_id": USER}))
    assert data["schedules"] == [] and data["todos"] == []


def test_dashboard_without_user_id_is_safe(client):
    data = _envelope(client.get(DASH, params={"date": TODAY}))
    assert isinstance(data["schedules"], list) and isinstance(data["todos"], list)


# --------------------------------------------------------------------------- #
# 10. envelope consistency across every step
# --------------------------------------------------------------------------- #
def test_envelope_consistency_all_steps(client):
    # parse
    r = client.post(PARSE, json={"text": "오늘 오후 3시에 병원 예약 있어",
                                 "today": TODAY, "use_llm": False})
    assert {"success", "message", "data"}.issubset(r.json().keys())
    parsed = r.json()["data"]
    # confirm
    r = _confirm(client, _parsed_payload(parsed))
    assert {"success", "message", "data"}.issubset(r.json().keys())
    # dashboard
    r = client.get(DASH, params={"date": TODAY, "user_id": USER})
    assert {"success", "message", "data"}.issubset(r.json().keys())


# --------------------------------------------------------------------------- #
# 11. only-todo / only-schedule DB states don't break the dashboard
# --------------------------------------------------------------------------- #
def test_only_todo_present_dashboard_ok(client):
    _envelope(_confirm(client, _parsed_payload(_parse(client, "오늘까지 과제 제출해야 해"))))
    dash = _dash(client, TODAY)
    assert dash["schedules"] == []
    assert "과제 제출" in [t["title"] for t in dash["todos"]]


def test_only_schedule_present_dashboard_ok(client):
    _envelope(_confirm(client, _parsed_payload(_parse(client, "오늘 오후 3시에 병원 예약 있어"))))
    dash = _dash(client, TODAY)
    assert dash["todos"] == []
    assert "병원 예약" in [s["title"] for s in dash["schedules"]]
