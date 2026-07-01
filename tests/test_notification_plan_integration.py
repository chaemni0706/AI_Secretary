"""MVP notification-plan integration tests (plan-only; no OS push / external API).

confirm -> reminder_plan (reminders + checklist + delivery) and
GET /notifications/plans/{item_id}. Isolated temp SQLite; no real LLM.
Base date 2026-07-01.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.database.init_db import apply_schema_to_sqlite_file
from backend.database.session import create_sqlite_engine, get_db
from backend.main import app

CONFIRM = "/api/v1/ai/schedule/confirm"
PREF = "/api/v1/memory/local-user/preferences/effective"
PLANS = "/api/v1/notifications/plans"
LOCAL_TODO = "/api/v1/local/todos"
DASH = "/api/v1/dashboard/today"
USER = "local-user"


@pytest.fixture()
def client(tmp_path):
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
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


def _env(r, *, success=True):
    assert r.status_code == 200, r.text
    body = r.json()
    assert {"success", "message", "data"}.issubset(body.keys())
    assert body["success"] is success
    return body["data"]


def _save_pref(client, **fields):
    return client.put(PREF, json=fields)


def _confirm_event(client, **parsed):
    parsed.setdefault("item_type", "EVENT")
    return client.post(CONFIRM, json={"user_id": USER, "parsed": parsed})


def _confirm_todo(client, **parsed):
    parsed.setdefault("item_type", "TODO")
    return client.post(CONFIRM, json={"user_id": USER, "parsed": parsed})


def _types(plan):
    return [r["type"] for r in plan["reminders"]]


# --------------------------------------------------------------------------- #
# 1. EVENT confirm -> default reminder
# --------------------------------------------------------------------------- #
def test_event_confirm_creates_default_reminder(client):
    data = _env(_confirm_event(client, title="병원 예약", date="2026-07-01",
                               start_time="15:00", category="health"))
    plan = data["reminder_plan"]
    assert "default" in _types(plan)
    default = next(r for r in plan["reminders"] if r["type"] == "default")
    assert default["trigger_time"] == "2026-07-01T14:30:00"
    assert default["message"] and default["reason"]


# --------------------------------------------------------------------------- #
# 2. health checklist contains id / reservation items
# --------------------------------------------------------------------------- #
def test_health_checklist_items(client):
    data = _env(_confirm_event(client, title="병원 예약", date="2026-07-01",
                               start_time="15:00", category="health"))
    items = [c["item"] for c in data["reminder_plan"]["checklist"]]
    assert "신분증" in items
    assert "예약 확인" in items
    for c in data["reminder_plan"]["checklist"]:
        assert c["item"] and c["reason"]


# --------------------------------------------------------------------------- #
# 3. location present -> departure reminder
# --------------------------------------------------------------------------- #
def test_location_creates_departure_reminder(client):
    data = _env(_confirm_event(client, title="병원 예약", date="2026-07-01",
                               start_time="15:00", category="health", location="강남역"))
    assert "departure" in _types(data["reminder_plan"])


# --------------------------------------------------------------------------- #
# 4. no location -> no departure reminder + warning
# --------------------------------------------------------------------------- #
def test_no_location_no_departure(client):
    data = _env(_confirm_event(client, title="병원 예약", date="2026-07-01",
                               start_time="15:00", category="health"))
    plan = data["reminder_plan"]
    assert "departure" not in _types(plan)
    assert any("위치" in w for w in plan["warnings"])


# --------------------------------------------------------------------------- #
# 5. default_reminder_minutes reflected
# --------------------------------------------------------------------------- #
def test_default_reminder_minutes_reflected(client):
    _save_pref(client, default_reminder_minutes=40)
    data = _env(_confirm_event(client, title="회의", date="2026-07-01",
                               start_time="15:00", category="work"))
    default = next(r for r in data["reminder_plan"]["reminders"] if r["type"] == "default")
    assert default["minutes_before"] == 40
    assert default["trigger_time"] == "2026-07-01T14:20:00"


# --------------------------------------------------------------------------- #
# 6. departure_buffer_minutes reflected
# --------------------------------------------------------------------------- #
def test_departure_buffer_minutes_reflected(client):
    _save_pref(client, departure_buffer_minutes=20)     # travel 30 + buffer 20 = 50
    data = _env(_confirm_event(client, title="병원 예약", date="2026-07-01",
                               start_time="15:00", category="health", location="강남역"))
    dep = next(r for r in data["reminder_plan"]["reminders"] if r["type"] == "departure")
    assert dep["minutes_before"] == 50


# --------------------------------------------------------------------------- #
# 7. late_prone -> earlier reminder
# --------------------------------------------------------------------------- #
def test_late_prone_earlier_reminder(client):
    base = _env(_confirm_event(client, title="회의", date="2026-07-01",
                               start_time="15:00", category="work"))
    base_mb = next(r for r in base["reminder_plan"]["reminders"] if r["type"] == "default")["minutes_before"]

    _save_pref(client, late_prone=True)
    late = _env(_confirm_event(client, title="회의", date="2026-07-01",
                               start_time="15:00", category="work"))
    late_mb = next(r for r in late["reminder_plan"]["reminders"] if r["type"] == "default")["minutes_before"]
    assert late_mb > base_mb
    assert "late_prone" in late["reminder_plan"]["personalization"]["used_preferences"]


# --------------------------------------------------------------------------- #
# 8. notification_style soft -> soft tone message
# --------------------------------------------------------------------------- #
def test_soft_notification_style_message(client):
    _save_pref(client, notification_style="soft")
    data = _env(_confirm_event(client, title="병원 예약", date="2026-07-01",
                               start_time="15:00", category="health"))
    default = next(r for r in data["reminder_plan"]["reminders"] if r["type"] == "default")
    assert "천천히" in default["message"]


# --------------------------------------------------------------------------- #
# 9-10. TODO -> deadline reminder, NO departure
# --------------------------------------------------------------------------- #
def test_todo_confirm_creates_deadline_reminder(client):
    data = _env(_confirm_todo(client, title="과제 제출", date="2026-07-01", category="study"))
    plan = data["reminder_plan"]
    assert "deadline" in _types(plan)
    assert "departure" not in _types(plan)
    dl = next(r for r in plan["reminders"] if r["type"] == "deadline")
    assert dl["trigger_time"] == "2026-07-01T09:00:00"


def test_high_priority_todo_gets_day_before(client):
    # create a high-priority todo directly, then look up its plan
    r = client.post(LOCAL_TODO, json={"title": "발표 자료", "due_date": "2026-07-03",
                                       "priority": "high", "category": "work"})
    tid = _env(r)["id"]
    plan = _env(client.get(f"{PLANS}/{tid}"))["reminder_plan"]
    triggers = sorted(r["trigger_time"] for r in plan["reminders"])
    assert len(plan["reminders"]) == 2            # due-day + day-before
    assert triggers[0].startswith("2026-07-02")   # day-before reminder


# --------------------------------------------------------------------------- #
# 11. delivery is plan-only
# --------------------------------------------------------------------------- #
def test_delivery_is_plan_only(client):
    data = _env(_confirm_event(client, title="회의", date="2026-07-01",
                               start_time="15:00", category="work"))
    delivery = data["reminder_plan"]["delivery"]
    assert delivery["os_push_enabled"] is False
    assert delivery["status"] == "planned_only"


# --------------------------------------------------------------------------- #
# 12. plan lookup after save (idempotent)
# --------------------------------------------------------------------------- #
def test_plan_lookup_after_save(client):
    sid = _env(_confirm_event(client, title="병원 예약", date="2026-07-01",
                              start_time="15:00", category="health", location="강남역"))["schedule"]["id"]
    first = _env(client.get(f"{PLANS}/{sid}"))
    assert first["item_id"] == sid and first["item_type"] == "EVENT"
    t1 = [r["trigger_time"] for r in first["reminder_plan"]["reminders"]]
    # idempotent: second lookup identical
    second = _env(client.get(f"{PLANS}/{sid}"))
    t2 = [r["trigger_time"] for r in second["reminder_plan"]["reminders"]]
    assert t1 == t2


def test_plan_lookup_unknown_item_404(client):
    r = client.get(f"{PLANS}/nope_999")
    assert r.status_code == 404


# --------------------------------------------------------------------------- #
# 13. dashboard still works alongside notification plans (no contract break)
# --------------------------------------------------------------------------- #
def test_dashboard_still_works(client):
    _confirm_event(client, title="병원 예약", date="2026-07-01", start_time="15:00", category="health")
    data = _env(client.get(DASH, params={"date": "2026-07-01", "user_id": USER}))
    assert "병원 예약" in [s["title"] for s in data["schedules"]]


# --------------------------------------------------------------------------- #
# 14. normal EVENT without start_time -> 422 (validation, not 500)
# --------------------------------------------------------------------------- #
def test_event_without_start_time_is_422(client):
    r = _confirm_event(client, title="회의", date="2026-07-01", category="work", is_all_day=False)
    assert r.status_code == 422
    assert r.json()["success"] is False


# --------------------------------------------------------------------------- #
# 15. all_day EVENT -> trigger_time uncomputable handled safely
# --------------------------------------------------------------------------- #
def test_all_day_event_safe(client):
    data = _env(_confirm_event(client, title="워크숍", date="2026-07-01",
                               start_time=None, category="work", is_all_day=True))
    plan = data["reminder_plan"]
    default = next((r for r in plan["reminders"] if r["type"] == "default"), None)
    assert default is not None
    assert default["trigger_time"] is None
    assert any("종일" in w for w in plan["warnings"])


# --------------------------------------------------------------------------- #
# error handling: unknown category / no preference -> defaults, no 500
# --------------------------------------------------------------------------- #
def test_unknown_category_and_no_pref_safe(client):
    data = _env(_confirm_event(client, title="뭔가", date="2026-07-01",
                               start_time="15:00", category="unknown_cat"))
    plan = data["reminder_plan"]
    assert "default" in _types(plan)
    assert isinstance(plan["checklist"], list)         # etc fallback, never crash
    assert plan["personalization"]["personalization_applied"] is False
