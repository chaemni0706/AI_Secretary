"""Integration tests for POST /api/v1/voice/route — the unified voice entry
point. Verifies that the router dispatches to the EXISTING feature services
(place recommendation / chat orchestrator / briefing generator / schedule
parser / notification plan builder) without ever routing a place-recommend
utterance into schedule_create, and that reminder_setting only activates
right after a schedule was just created in the same conversation (context
echoed back by the client on the next turn).

Isolated temp SQLite per test (same pattern as test_notification_plan_integration.py).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.core.config import settings
from backend.database.init_db import apply_schema_to_sqlite_file
from backend.database.session import create_sqlite_engine, get_db
from backend.main import app
from backend.services import naver_place_client as naver

ROUTE = "/api/v1/voice/route"
NOW = "2026-07-06T09:00:00+09:00"


@pytest.fixture()
def client(tmp_path):
    db_file = tmp_path / "voice_route.db"
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


class _FakeResp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


@pytest.fixture
def mock_naver_ok(monkeypatch):
    def _fake_get(url, headers=None, params=None, timeout=None):
        payload = {
            "items": [{
                "title": "<b>홍대</b> 카페 예시", "link": "https://map.naver.com/example",
                "category": "카페,디저트", "telephone": "02-000-0000",
                "address": "서울 마포구 서교동 1-1", "roadAddress": "서울 마포구 양화로 100",
            }]
        }
        return _FakeResp(200, payload)

    monkeypatch.setattr(settings, "NAVER_CLIENT_ID", "test-id")
    monkeypatch.setattr(settings, "NAVER_CLIENT_SECRET", "test-secret")
    monkeypatch.setattr(naver.httpx, "get", _fake_get)


def _route(client, text, **kwargs):
    body = {"text": text, "current_datetime": NOW, **kwargs}
    r = client.post(ROUTE, json=body)
    assert r.status_code == 200, r.text
    payload = r.json()
    assert {"success", "message", "data"}.issubset(payload.keys())
    assert payload["success"] is True
    return payload["data"]


# --------------------------------------------------------------------------- #
# 1. "가게 추천해줘" / "근처 카페 추천해줘" — never schedule_create
# --------------------------------------------------------------------------- #
def test_store_recommendation_never_becomes_schedule_create(client, mock_naver_ok):
    data = _route(client, "가게 추천해줘")
    assert data["intent"] == "reservation_recommendation"
    # 챗 안 카드로 표시(show_card). 이전 navigate → 인-챗 캐러셀로 변경.
    assert data["screen_action"]["type"] == "show_card"
    assert data["screen_action"]["target"] == "reservation_recommendation"
    assert "recommended_places" in data["data"]
    assert data["data"]["recommended_places"], "mocked Naver result should produce a candidate"


def test_nearby_cafe_recommendation(client, mock_naver_ok):
    data = _route(client, "근처 카페 추천해줘")
    assert data["intent"] == "reservation_recommendation"


def test_recommendation_degrades_gracefully_without_naver_keys(client):
    """No mock_naver_ok fixture here -> settings.naver_configured is False.
    네이버 키가 없으면 Mock 업체 목록으로 대체(빈 목록 대신). 절대 crash/schedule_create
    로 새지 않는다."""
    data = _route(client, "가게 추천해줘")
    assert data["intent"] == "reservation_recommendation"
    places = data["data"]["recommended_places"]
    assert places, "키 없을 때 Mock 업체 목록을 반환해야 함"
    assert all(p["source"] == "mock" for p in places)


# --------------------------------------------------------------------------- #
# 2. emotion_schedule_coaching
# --------------------------------------------------------------------------- #
def test_tired_plus_today_schedule_is_coaching(client):
    data = _route(client, "오늘 진짜 피곤하다 오늘 일정 뭐야")
    assert data["intent"] == "emotion_schedule_coaching"
    assert data["screen_action"]["type"] == "show_card"
    assert data["tts_text"]


def test_hard_plus_what_to_do_is_coaching(client):
    data = _route(client, "너무 힘들어 오늘 뭐 해야 돼")
    assert data["intent"] == "emotion_schedule_coaching"


def test_emotion_coaching_combines_empathy_schedule_and_suggestion(client):
    """스펙 요구: 감정 공감 + 오늘 일정 요약 + 휴식/일정 조정 제안이 하나의
    응답에 함께 나와야 한다 — 공감 문장만 있는 짧은 응답이면 안 된다."""
    created = client.post("/api/v1/local/schedules", json={
        "title": "팀 회의", "date": "2026-07-06", "start_time": "10:00",
        "end_time": "11:00", "category": "meeting", "priority": "high",
    })
    assert created.status_code == 200, created.text

    data = _route(client, "오늘 진짜 피곤하다 오늘 일정 뭐야")
    assert data["intent"] == "emotion_schedule_coaching"
    # 오늘 일정 요약(제목)이 응답 문장에 포함돼야 한다.
    assert "팀 회의" in data["tts_text"], data["tts_text"]
    # 공감 문장만 담긴 짧은 템플릿으로 되돌아가면 안 된다.
    assert data["tts_text"] != "많이 피곤해 보여요. 잠깐 쉬어가는 건 어때요?"
    assert len(data["tts_text"]) > len("많이 피곤해 보여요. 잠깐 쉬어가는 건 어때요?")
    assert len(data["data"]["today_schedule"]) == 1
    assert data["data"]["solutions"], "휴식/일정 조정 제안(solutions)이 함께 내려와야 한다"


# --------------------------------------------------------------------------- #
# 3. daily_briefing
# --------------------------------------------------------------------------- #
def test_daily_briefing(client):
    data = _route(client, "오늘 브리핑 해줘")
    assert data["intent"] == "daily_briefing"
    assert data["screen_action"]["type"] == "show_card"
    assert "summary" in data["data"]


def test_daily_briefing_variant(client):
    data = _route(client, "오늘의 브리핑 들려줘")
    assert data["intent"] == "daily_briefing"


# --------------------------------------------------------------------------- #
# 4. schedule_create -> reminder_setting two-turn flow
# --------------------------------------------------------------------------- #
def test_schedule_create_then_reminder_confirmation_flow(client):
    created = _route(client, "내일 오후 3시에 병원 일정 추가해줘")
    assert created["intent"] == "schedule_create"
    assert "알림을 받을까요" in created["tts_text"]
    assert created["context"]["type"] == "schedule_created"
    assert created["data"]["item"]["title"]

    # next turn: client echoes back the context it just received
    reminder = _route(client, "응 알림 받을래", context=created["context"])
    assert reminder["intent"] == "reminder_setting"
    assert reminder["data"]["reminder_enabled"] is True
    assert reminder["data"]["reminder_minutes_before"] == 30
    assert "reminder_plan" in reminder["data"]


def test_schedule_create_then_explicit_minutes(client):
    created = _route(client, "내일 오후 3시에 병원 일정 추가해줘")
    reminder = _route(client, "1시간 전에 알려줘", context=created["context"])
    assert reminder["intent"] == "reminder_setting"
    assert reminder["data"]["reminder_minutes_before"] == 60
    minutes_before = {r["type"]: r["minutes_before"] for r in reminder["data"]["reminder_plan"]["reminders"]}
    assert minutes_before["default"] == 60


def test_reminder_setting_without_pending_context_does_not_fire(client):
    """Anti-regression: a bare reminder phrase with no prior schedule_create in
    this conversation must not be treated as a reminder confirmation."""
    data = _route(client, "응 알림 받을래")
    assert data["intent"] != "reminder_setting"


# --------------------------------------------------------------------------- #
# 5. schedule_query
# --------------------------------------------------------------------------- #
def test_schedule_query_after_registering(client):
    _route(client, "내일 오후 3시에 병원 일정 추가해줘")
    data = _route(client, "내일 일정 알려줘")
    assert data["intent"] == "schedule_query"
