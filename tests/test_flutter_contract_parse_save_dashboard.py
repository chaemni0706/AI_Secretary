"""Flutter integration CONTRACT lock-down tests.

Goal: not new behaviour, but freezing the field names / response wrappers /
status codes the Flutter app depends on across:

    POST /api/v1/ai/schedule/parse/enhanced   (flat data)
    POST /api/v1/ai/schedule/confirm          (data.schedule | data.todo)
    GET  /api/v1/dashboard/today              (schedules[] / todos[])

No real LLM (use_llm=false). Isolated temp SQLite. Base date fixed to
2026-07-01 (Wednesday).
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
DASH_TODAY = "/api/v1/dashboard/today"
DASH_BARE = "/api/v1/dashboard"           # must NOT exist (contract keeps /today)
TODAY = "2026-07-01"
USER = "local-user"

# The flat data contract the Flutter client maps against.
ENHANCED_FIELDS = {
    "original_text", "title", "date", "start_time", "end_time", "category",
    "item_type", "location", "memo", "is_all_day", "confidence", "parse_source",
    "timezone", "base_date", "warnings",
    "needs_clarification", "missing_fields", "clarification_questions",
}


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "contract.db"
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


def _envelope(r, *, success=True):
    body = r.json()
    assert {"success", "message", "data"}.issubset(body.keys()), body
    assert body["success"] is success
    return body


def _parse(client, text):
    r = client.post(PARSE, json={"text": text, "today": TODAY,
                                 "timezone": "Asia/Seoul", "use_llm": False})
    assert r.status_code == 200, r.text
    return _envelope(r)["data"]


def _parsed_payload(data):
    keys = ("original_text", "title", "date", "start_time", "end_time",
            "category", "location", "memo", "is_all_day", "item_type")
    return {k: data.get(k) for k in keys}


def _confirm(client, parsed, *, item_type=None, user_id=USER):
    body = {"user_id": user_id, "parsed": parsed}
    if item_type is not None:
        body["item_type"] = item_type
    return client.post(CONFIRM, json=body)


# --------------------------------------------------------------------------- #
# 1-2. enhanced parse: flat structure + required fields always present
# --------------------------------------------------------------------------- #
def test_enhanced_parse_is_flat_with_all_fields(client):
    data = _parse(client, "오늘 오후 3시에 병원 예약 있어")
    # flat: no nested slots / schedule_draft wrappers
    assert "slots" not in data and "schedule_draft" not in data
    assert set(data.keys()) == ENHANCED_FIELDS


def test_enhanced_parse_required_fields_and_types(client):
    data = _parse(client, "오늘 오후 3시에 병원 예약 있어")
    assert data["title"] == "병원 예약"
    assert data["date"] == TODAY
    assert data["start_time"] == "15:00"
    assert data["category"] == "health"
    assert data["item_type"] in ("EVENT", "TODO")
    # nullable / list fields keep their type even when empty
    assert isinstance(data["warnings"], list)
    assert isinstance(data["missing_fields"], list)
    assert isinstance(data["clarification_questions"], list)
    assert isinstance(data["needs_clarification"], bool)


def test_enhanced_parse_nullable_fields_are_null_not_missing(client):
    data = _parse(client, "오늘까지 과제 제출해야 해")   # todo: no time/location
    assert data["start_time"] is None       # present and null, not dropped
    assert data["location"] is None
    assert "end_time" in data and "memo" in data


# --------------------------------------------------------------------------- #
# 3. EVENT: parse -> confirm -> data.schedule
# --------------------------------------------------------------------------- #
def test_event_confirm_returns_data_schedule(client):
    data = _parse(client, "오늘 오후 3시에 병원 예약 있어")
    assert data["item_type"] == "EVENT"
    body = _envelope(_confirm(client, _parsed_payload(data)))
    assert body["message"] == "일정을 저장했습니다."
    assert "schedule" in body["data"] and "todo" not in body["data"]
    sch = body["data"]["schedule"]
    for f in ("id", "title", "date", "start_time", "end_time", "category"):
        assert f in sch
    assert sch["title"] == "병원 예약" and sch["date"] == TODAY


# --------------------------------------------------------------------------- #
# 4. TODO: parse -> confirm -> data.todo
# --------------------------------------------------------------------------- #
def test_todo_confirm_returns_data_todo(client):
    data = _parse(client, "오늘까지 과제 제출해야 해")
    assert data["item_type"] == "TODO"
    body = _envelope(_confirm(client, _parsed_payload(data)))
    assert body["message"] == "할 일을 저장했습니다."
    assert "todo" in body["data"] and "schedule" not in body["data"]
    todo = body["data"]["todo"]
    for f in ("id", "title", "due_date", "category", "completed"):
        assert f in todo
    assert todo["title"] == "과제 제출" and todo["due_date"] == TODAY
    assert todo["completed"] is False


# --------------------------------------------------------------------------- #
# 5. confirm validation failures -> 422 (never 500)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("parsed, item_type", [
    ({"title": "회의", "date": None, "start_time": "15:00"}, "EVENT"),        # no date
    ({"title": "회의", "date": TODAY, "is_all_day": False}, "EVENT"),          # no start_time
    ({"title": None, "date": TODAY, "start_time": "15:00"}, "EVENT"),          # no title
    ({"title": "회의", "date": "2026/07/01", "start_time": "15:00"}, "EVENT"), # bad date
    ({"title": "회의", "date": TODAY, "start_time": "25:99"}, "EVENT"),        # bad time
    ({"title": "과제", "date": None}, "TODO"),                                 # todo no due_date
    ({"title": None, "date": TODAY}, "TODO"),                                  # todo no title
    ({"title": "회의", "date": TODAY, "start_time": "15:00"}, "MEETING"),      # invalid item_type
])
def test_confirm_validation_failures_return_422(client, parsed, item_type):
    r = _confirm(client, parsed, item_type=item_type)
    assert r.status_code == 422, r.text
    assert r.json()["success"] is False
    assert r.json()["message"]        # a message explaining the problem


# --------------------------------------------------------------------------- #
# 6. confirming a needs_clarification parse is rejected with 422
# --------------------------------------------------------------------------- #
def test_confirm_needs_clarification_result_is_422(client):
    data = _parse(client, "미용실 예약해야 돼")     # no date/time -> needs_clarification
    assert data["needs_clarification"] is True
    assert "date" in data["missing_fields"]
    r = _confirm(client, _parsed_payload(data))
    assert r.status_code == 422
    assert r.json()["success"] is False


# --------------------------------------------------------------------------- #
# 7-8. dashboard path contract: /dashboard/today works, bare /dashboard doesn't
# --------------------------------------------------------------------------- #
def test_dashboard_today_path_works(client):
    r = client.get(DASH_TODAY, params={"date": TODAY, "user_id": USER})
    assert r.status_code == 200
    data = _envelope(r)["data"]
    assert data["date"] == TODAY
    assert "schedules" in data and "todos" in data


def test_bare_dashboard_path_not_introduced(client):
    # contract keeps /dashboard/today; a bare GET /dashboard must not be a route
    r = client.get(DASH_BARE, params={"date": TODAY})
    assert r.status_code == 404


# --------------------------------------------------------------------------- #
# 9-10. dashboard item field contracts
# --------------------------------------------------------------------------- #
def test_dashboard_schedule_fields(client):
    _envelope(_confirm(client, _parsed_payload(_parse(client, "오늘 오후 3시에 병원 예약 있어"))))
    data = _envelope(client.get(DASH_TODAY, params={"date": TODAY, "user_id": USER}))["data"]
    assert data["schedules"], "expected one schedule"
    s = data["schedules"][0]
    for f in ("id", "title", "date", "start_time", "end_time", "category"):
        assert f in s
    assert s["date"] == TODAY and s["start_time"] == "15:00"


def test_dashboard_todo_fields(client):
    _envelope(_confirm(client, _parsed_payload(_parse(client, "오늘까지 과제 제출해야 해"))))
    data = _envelope(client.get(DASH_TODAY, params={"date": TODAY, "user_id": USER}))["data"]
    assert data["todos"], "expected one todo"
    t = data["todos"][0]
    for f in ("id", "title", "due_date", "category", "completed"):
        assert f in t
    assert t["due_date"] == TODAY and t["completed"] is False


# --------------------------------------------------------------------------- #
# 11-12. item_type detection contract
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text", [
    "오늘까지 과제 제출해야 해",
    "보고서 완료해야 함",
    "장 볼 목록 정리",
])
def test_todo_keywords_detected_as_todo(client, text):
    assert _parse(client, text)["item_type"] == "TODO"


@pytest.mark.parametrize("text", [
    "내일 산책",          # ambiguous -> EVENT default
    "오늘 병원 예약",     # explicit EVENT signal
    "친구랑 미팅",
])
def test_ambiguous_or_event_detected_as_event(client, text):
    assert _parse(client, text)["item_type"] == "EVENT"


# --------------------------------------------------------------------------- #
# 13. empty dashboard -> empty arrays, no 500
# --------------------------------------------------------------------------- #
def test_empty_dashboard_returns_empty_arrays(client):
    data = _envelope(client.get(DASH_TODAY, params={"date": TODAY, "user_id": USER}))["data"]
    assert data["schedules"] == [] and data["todos"] == []


# --------------------------------------------------------------------------- #
# needs_clarification / missing_fields correspondence contract
# --------------------------------------------------------------------------- #
def test_clarification_corresponds_to_missing_fields(client):
    data = _parse(client, "미용실 예약해야 돼")
    assert data["needs_clarification"] == bool(data["missing_fields"])
    assert len(data["clarification_questions"]) == len(data["missing_fields"])


def test_no_missing_fields_means_no_clarification(client):
    data = _parse(client, "오늘 오후 3시에 병원 예약 있어")
    assert data["missing_fields"] == []
    assert data["needs_clarification"] is False
