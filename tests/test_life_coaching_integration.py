"""Life-coaching integration tests (rule-based; no ML / no external API / no LLM).

POST /api/v1/coaching/life — emotion classification connected to today's
schedule/todo, free time, preference, place & reservation hints. Isolated temp
SQLite. Base date 2026-07-01.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.database.init_db import apply_schema_to_sqlite_file
from backend.database.session import create_sqlite_engine, get_db
from backend.main import app

COACH = "/api/v1/coaching/life"
CONFIRM = "/api/v1/ai/schedule/confirm"
PREF = "/api/v1/memory/local-user/preferences/effective"
DATE = "2026-07-01"
USER = "local-user"

_DIAGNOSIS_TERMS = ("우울증", "불안장애", "정신질환", "치료가 필요", "장애입니다", "정신과", "약을 드세요")


def _coaching_text(data):
    """Coaching-facing text only (excludes safety.note, which legitimately
    says '의료 진단이 아니라...')."""
    parts = []
    for c in data["coaching_cards"]:
        parts += [c["title"], c["message"], c["reason"]]
    if data["safety"].get("support_message"):
        parts.append(data["safety"]["support_message"])
    return " ".join(parts)


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "coach.db"
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


def _coach(client, text, date=DATE, **extra):
    body = {"user_id": USER, "text": text, "date": date, "timezone": "Asia/Seoul"}
    body.update(extra)
    r = client.post(COACH, json=body)
    assert r.status_code == 200, r.text
    body = r.json()
    assert {"success", "message", "data"}.issubset(body.keys())
    assert body["success"] is True
    return body["data"]


def _save_pref(client, **fields):
    return client.put(PREF, json=fields)


def _mk_event(client, title, start, end, category="work"):
    client.post(CONFIRM, json={"user_id": USER, "parsed": {
        "title": title, "date": DATE, "start_time": start, "end_time": end,
        "category": category, "item_type": "EVENT"}})


def _mk_todo(client, title, category="study"):
    client.post(CONFIRM, json={"user_id": USER, "parsed": {
        "title": title, "date": DATE, "category": category, "item_type": "TODO"}})


def _card_types(data):
    return [c["action_type"] for c in data["coaching_cards"]]


# --------------------------------------------------------------------------- #
# 1. tired classification
# --------------------------------------------------------------------------- #
def test_tired_classification(client):
    data = _coach(client, "오늘 너무 피곤하고 지쳐")
    assert data["primary_emotion"] == "tired"
    assert 0.0 <= data["emotion_score"] <= 1.0


# --------------------------------------------------------------------------- #
# 2. stress -> break_down_task card
# --------------------------------------------------------------------------- #
def test_stress_generates_break_down_task(client):
    data = _coach(client, "마감 때문에 스트레스 받고 부담돼")
    assert data["primary_emotion"] == "stress"
    assert "break_down_task" in _card_types(data)


# --------------------------------------------------------------------------- #
# 3. overwhelmed -> free_time_slots (schedules leave gaps)
# --------------------------------------------------------------------------- #
def test_overwhelmed_generates_free_time(client):
    _mk_event(client, "회의", "14:00", "15:00")
    data = _coach(client, "할 게 너무 많아서 머리가 복잡해")
    assert data["primary_emotion"] == "overwhelmed"
    assert data["free_time_slots"]


# --------------------------------------------------------------------------- #
# 4-6. context summary reflects schedules / todos / next_schedule
# --------------------------------------------------------------------------- #
def test_context_reflects_schedules_and_todos(client):
    _mk_event(client, "회의", "14:00", "15:00")
    _mk_event(client, "저녁 약속", "18:00", "19:00", category="personal")
    _mk_todo(client, "과제 제출")
    data = _coach(client, "그냥 그래")
    ctx = data["context_summary"]
    assert ctx["schedule_count"] == 2
    assert ctx["todo_count"] == 1
    assert ctx["next_schedule"]["title"] == "회의"          # earliest of the day
    assert ctx["next_schedule"]["start_time"] == "14:00"


# --------------------------------------------------------------------------- #
# 7-8. free time present / fallback when the day is full
# --------------------------------------------------------------------------- #
def test_free_time_between_schedules(client):
    _mk_event(client, "오전", "09:00", "12:00")
    _mk_event(client, "오후", "13:00", "18:00")
    data = _coach(client, "피곤해")
    assert data["free_time_slots"]                          # 12:00~13:00 gap etc.


def test_full_day_fallback_card(client):
    _mk_event(client, "종일", "09:00", "21:00")              # fills the window
    data = _coach(client, "너무 피곤하고 지쳐")
    assert data["free_time_slots"] == []
    assert data["coaching_cards"]                            # fallback card exists
    assert "rest" in _card_types(data)                       # short-rest fallback


# --------------------------------------------------------------------------- #
# 9. place recommendations for tired/stress
# --------------------------------------------------------------------------- #
def test_place_recommendations_for_tired(client):
    data = _coach(client, "너무 피곤해")
    assert data["place_recommendations"]
    assert all(p["place_type"] and p["name"] and p["reason"] for p in data["place_recommendations"])


# --------------------------------------------------------------------------- #
# 10. reservation suggestions for a relevant state
# --------------------------------------------------------------------------- #
def test_reservation_suggestions_generated(client):
    data = _coach(client, "너무 피곤해")
    assert data["reservation_suggestions"]
    sug = data["reservation_suggestions"][0]
    assert sug["category"] and sug["next_api"].endswith("/reservations/business-candidates")


def test_beauty_utterance_suggests_hair_or_nail(client):
    data = _coach(client, "머리도 하고 싶고 네일도 받고 싶어")
    cats = {s["category"] for s in data["reservation_suggestions"]}
    assert cats & {"hair", "nail"}


# --------------------------------------------------------------------------- #
# 11. preferred_tone / coaching_style reflected
# --------------------------------------------------------------------------- #
def test_tone_and_style_reflected(client):
    _save_pref(client, preferred_tone="gentle", coaching_style="supportive")
    data = _coach(client, "너무 피곤해")
    joined = " ".join(c["message"] for c in data["coaching_cards"])
    assert "괜찮아요" in joined                               # gentle prefix
    assert "preferred_tone" in data["personalization"]["used_preferences"]


# --------------------------------------------------------------------------- #
# 12. rest_recommendation_enabled=false -> rest replaced
# --------------------------------------------------------------------------- #
def test_rest_disabled_replaces_rest(client):
    _mk_event(client, "회의", "14:00", "15:00")
    _save_pref(client, rest_recommendation_enabled=False)
    data = _coach(client, "너무 피곤하고 지쳐")
    assert "rest" not in _card_types(data)                   # rest excluded/substituted
    assert data["coaching_cards"]


# --------------------------------------------------------------------------- #
# 13. stress_triggers boost
# --------------------------------------------------------------------------- #
def test_stress_triggers_boost(client):
    _save_pref(client, stress_triggers=["과제"])
    data = _coach(client, "과제 때문에 힘들어")
    assert data["primary_emotion"] == "stress"
    assert "stress_triggers" in data["personalization"]["used_preferences"]


# --------------------------------------------------------------------------- #
# 14. no diagnostic language anywhere
# --------------------------------------------------------------------------- #
def test_no_diagnostic_language(client):
    data = _coach(client, "너무 우울하고 슬퍼")
    assert not any(term in _coaching_text(data) for term in _DIAGNOSIS_TERMS)
    assert data["safety"]["diagnosis"] is False


# --------------------------------------------------------------------------- #
# 15. crisis keyword -> safety high + support message
# --------------------------------------------------------------------------- #
def test_crisis_keyword_safety_high(client):
    data = _coach(client, "다 끝내고 싶고 사라지고 싶어")
    assert data["safety"]["risk_level"] == "high"
    assert data["safety"]["support_message"]
    assert not any(term in _coaching_text(data) for term in _DIAGNOSIS_TERMS)


# --------------------------------------------------------------------------- #
# 16. error handling — never 500
# --------------------------------------------------------------------------- #
def test_empty_text_is_422(client):
    r = client.post(COACH, json={"user_id": USER, "text": "", "date": DATE})
    assert r.status_code == 422


def test_no_date_is_safe(client):
    r = client.post(COACH, json={"user_id": USER, "text": "피곤해"})
    assert r.status_code == 200
    assert r.json()["data"]["context_summary"]["date"]


def test_invalid_date_is_safe(client):
    data = _coach(client, "피곤해", date="not-a-date")
    assert data["context_summary"]["date"]                   # fell back to today
    assert data["warnings"]


def test_unmatched_emotion_is_neutral(client):
    data = _coach(client, "음 그냥 평범한 하루야 특별할 것 없어")
    assert data["primary_emotion"] == "neutral"
    assert data["coaching_cards"]                            # still a fallback card


def test_no_schedules_no_todos_safe(client):
    data = _coach(client, "피곤해")
    assert data["context_summary"]["schedule_count"] == 0
    assert data["context_summary"]["todo_count"] == 0
    assert data["coaching_cards"]
