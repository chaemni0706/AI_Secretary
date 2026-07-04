"""Enhanced natural-language parse + confirm tests.

  POST /api/v1/ai/schedule/parse/enhanced
  POST /api/v1/ai/schedule/confirm

The real model is NEVER called: tests either leave the LLM disabled (no API key
-> llm_service.generate returns None -> pure rule fallback) or monkeypatch
llm_service.generate to return a canned reply. Base date is injected via `today`
so relative dates are deterministic (2026-07-01 is a Wednesday).
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.database.init_db import apply_schema_to_sqlite_file
from backend.database.schema.schedule_parse_schema import EnhancedParseData
from backend.database.session import create_sqlite_engine, get_db
from backend.main import app
from backend.services import llm_service, schedule_llm_parser
from backend.services.schedule_parse_service import to_schedule_create_request

PATH = "/api/v1/ai/schedule/parse/enhanced"
CONFIRM = "/api/v1/ai/schedule/confirm"
OLD_PATH = "/api/v1/ai/schedule/parse"
LOCAL = "/api/v1/local/schedules"
TODAY = "2026-07-01"

FULL_KEYS = {
    "original_text", "title", "date", "start_time", "end_time", "category",
    "location", "memo", "is_all_day", "confidence", "parse_source", "item_type",
    "timezone", "base_date", "warnings",
    "needs_clarification", "clarification_questions", "missing_fields",
}


def _parse(client, text, **extra):
    body = {"text": text, "today": TODAY}
    body.update(extra)
    r = client.post(PATH, json=body)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    return body


def _mock_llm(monkeypatch, reply):
    monkeypatch.setattr(llm_service, "generate", lambda *a, **k: reply)


# --------------------------------------------------------------------------- #
# DB-backed client (isolated temp SQLite) for confirm tests
# --------------------------------------------------------------------------- #
@pytest.fixture()
def db_client(tmp_path):
    db_file = tmp_path / "parse_confirm.db"
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
# Response contract (now includes tz/base_date/clarification fields)
# --------------------------------------------------------------------------- #
def test_response_shape(client):
    data = _parse(client, "내일 오후 3시에 병원 예약 있어")["data"]
    assert set(data.keys()) == FULL_KEYS
    assert data["original_text"] == "내일 오후 3시에 병원 예약 있어"
    assert data["parse_source"] in {"llm", "rule_fallback", "hybrid"}
    assert 0.0 <= data["confidence"] <= 1.0
    assert data["timezone"] == "Asia/Seoul"
    assert data["base_date"] == TODAY


# --------------------------------------------------------------------------- #
# rule extraction (no LLM key -> pure rule fallback)
# --------------------------------------------------------------------------- #
def test_case1_tomorrow_afternoon_hospital(client):
    data = _parse(client, "내일 오후 3시에 병원 예약 있어")["data"]
    assert data["date"] == "2026-07-02"
    assert data["start_time"] == "15:00"
    assert data["category"] == "health"


def test_case2_day_after_tomorrow_evening_beauty(client):
    data = _parse(client, "모레 저녁 7시에 미용실 예약")["data"]
    assert data["date"] == "2026-07-03"
    assert data["start_time"] == "19:00"
    assert data["category"] == "beauty"


def test_case3_this_friday_meeting(client):
    data = _parse(client, "이번 주 금요일 오후 2시 회의")["data"]
    assert data["date"] == "2026-07-03"
    assert data["start_time"] == "14:00"
    assert data["category"] == "work"


def test_case4_next_monday_study(client):
    data = _parse(client, "다음 주 월요일 오전 10시 스터디")["data"]
    assert data["date"] == "2026-07-06"
    assert data["start_time"] == "10:00"
    assert data["category"] == "study"


def test_case5_numeric_date_and_time(client):
    data = _parse(client, "7/3 15:30 치과")["data"]
    assert data["date"] == "2026-07-03"
    assert data["start_time"] == "15:30"
    assert data["category"] == "health"


def test_case6_half_past_nail(client):
    data = _parse(client, "오후 3시 반 네일 예약")["data"]
    assert data["start_time"] == "15:30"
    assert data["category"] == "beauty"
    assert data["date"] is None
    assert "날짜 정보가 필요합니다." in data["warnings"]


def test_case7_llm_non_json_falls_back(client, monkeypatch):
    _mock_llm(monkeypatch, "죄송해요, JSON을 만들지 못했습니다.")
    data = _parse(client, "내일 오후 3시에 병원 예약")["data"]
    assert data["parse_source"] == "rule_fallback"
    assert data["date"] == "2026-07-02"
    assert data["start_time"] == "15:00"


def test_case8_llm_bad_date_uses_rule(client, monkeypatch):
    _mock_llm(monkeypatch, json.dumps({
        "title": "병원 진료", "date": "07-02-2026", "start_time": None,
        "end_time": None, "category": "health", "location": None,
        "memo": None, "is_all_day": False, "confidence": 0.8,
    }))
    data = _parse(client, "내일 오후 2시 병원")["data"]
    assert data["date"] == "2026-07-02"
    assert data["start_time"] == "14:00"
    assert data["parse_source"] == "hybrid"
    assert data["title"] == "병원 진료"
    assert any("형식" in w for w in data["warnings"])


def test_case9_missing_datetime_returns_warnings(client):
    body = _parse(client, "미용실 예약해야 돼")
    data = body["data"]
    assert data["date"] is None and data["start_time"] is None
    assert "날짜 정보가 필요합니다." in data["warnings"]
    assert "시간 정보가 필요합니다." in data["warnings"]
    assert body["message"] == "일부 정보가 부족하지만 일정 정보를 생성했습니다."
    assert data["category"] == "beauty"


def test_case10_empty_text_is_422(client):
    r = client.post(PATH, json={"text": "", "today": TODAY})
    assert r.status_code == 422
    assert r.json()["success"] is False


def test_whitespace_text_is_safe_200(client):
    body = _parse(client, "   ")
    assert body["success"] is True
    assert body["data"]["date"] is None


def test_case11_llm_past_date_is_dropped(client, monkeypatch):
    _mock_llm(monkeypatch, json.dumps({
        "title": "병원 예약", "date": "2020-01-01", "start_time": None,
        "end_time": None, "category": "health", "location": None,
        "memo": None, "is_all_day": False, "confidence": 0.7,
    }))
    data = _parse(client, "병원 예약")["data"]
    assert data["date"] is None
    assert any("과거" in w for w in data["warnings"])


def test_legacy_endpoint_contract_unchanged(client):
    r = client.post(OLD_PATH, json={
        "input": "내일 오후 2시에 병원 예약 잡아줘",
        "current_datetime": "2026-06-29T10:00:00+09:00",
    })
    assert r.status_code == 200
    data = r.json()["data"]
    assert set(data.keys()) == {
        "intent", "confidence", "slots", "schedule_draft", "missing_fields"
    }


# --------------------------------------------------------------------------- #
# Timezone
# --------------------------------------------------------------------------- #
def test_today_wins_over_timezone(client):
    data = _parse(client, "내일 병원", timezone="Asia/Seoul")["data"]
    assert data["base_date"] == TODAY
    assert data["timezone"] == "Asia/Seoul"


def test_no_today_uses_timezone_base_date(client):
    r = client.post(PATH, json={"text": "내일 병원", "timezone": "Asia/Seoul"})
    data = r.json()["data"]
    assert data["timezone"] == "Asia/Seoul"
    # base_date computed from the tz clock -> a valid ISO date, and 내일 = base+1
    assert len(data["base_date"]) == 10 and data["base_date"][4] == "-"
    assert data["date"] is not None and data["date"] > data["base_date"]


def test_invalid_timezone_falls_back(client):
    data = _parse(client, "내일 병원", timezone="Mars/Phobos")["data"]
    assert data["timezone"] == "Asia/Seoul"
    assert any("시간대" in w for w in data["warnings"])


# --------------------------------------------------------------------------- #
# Prompt / JSON mode
# --------------------------------------------------------------------------- #
def test_prompt_has_json_rule_and_fewshot():
    prompt = schedule_llm_parser.build_prompt("테스트", today="2026-08-01")
    assert "Return ONLY a valid JSON object" in prompt
    assert "내일 오후 3시에 병원 예약" in prompt          # few-shot example present
    assert "Base date is 2026-08-01" in prompt            # real base overrides example


def test_llm_json_mode_graceful_when_kwarg_unsupported(client, monkeypatch):
    # generate() signature WITHOUT response_format -> parser must retry gracefully
    def gen(prompt, system=None, model=None, temperature=None):
        return json.dumps({"title": "병원 진료", "category": "health", "confidence": 0.8})
    monkeypatch.setattr(llm_service, "generate", gen)
    data = _parse(client, "내일 오후 2시 병원")["data"]
    assert data["title"] == "병원 진료"
    assert data["date"] == "2026-07-02"


def test_llm_code_fence_and_trailing_comma(client, monkeypatch):
    _mock_llm(monkeypatch, "```json\n{\n  \"title\": \"팀 회의\",\n  \"category\": \"work\",\n  \"confidence\": 0.9,\n}\n```")
    data = _parse(client, "회의 잡아줘")["data"]
    assert data["title"] == "팀 회의"
    assert data["category"] == "work"


def test_llm_raises_is_swallowed(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("network down")
    monkeypatch.setattr(llm_service, "generate", boom)
    data = _parse(client, "내일 오후 2시 병원")["data"]
    assert data["date"] == "2026-07-02"
    assert data["parse_source"] == "rule_fallback"


def test_use_llm_false_skips_llm(client, monkeypatch):
    _mock_llm(monkeypatch, json.dumps({"title": "X", "category": "work", "confidence": 0.99}))
    data = _parse(client, "내일 오후 2시 병원", use_llm=False)["data"]
    assert data["parse_source"] == "rule_fallback"
    assert data["title"] != "X"


# --------------------------------------------------------------------------- #
# Hybrid confidence
# --------------------------------------------------------------------------- #
def test_confidence_increases_with_completeness(client):
    low = _parse(client, "미용실 예약해야 돼")["data"]["confidence"]           # no date/time
    high = _parse(client, "내일 오후 3시에 미용실 예약")["data"]["confidence"]  # date+time
    assert high > low


def test_confidence_high_requires_date_and_time(client):
    data = _parse(client, "미용실 예약해야 돼")["data"]      # no date/time
    assert data["confidence"] < 0.6


def test_confidence_drops_on_llm_rule_conflict(client, monkeypatch):
    # agreeing LLM
    _mock_llm(monkeypatch, json.dumps({
        "title": "병원", "date": "2026-07-02", "start_time": "14:00",
        "category": "health", "confidence": 0.9,
    }))
    agree = _parse(client, "내일 오후 2시 병원")["data"]
    # conflicting LLM (different date + time than the rule parser)
    _mock_llm(monkeypatch, json.dumps({
        "title": "병원", "date": "2026-07-20", "start_time": "18:00",
        "category": "health", "confidence": 0.9,
    }))
    conflict = _parse(client, "내일 오후 2시 병원")["data"]
    assert conflict["confidence"] < agree["confidence"]
    assert any("달라" in w for w in conflict["warnings"])
    assert conflict["date"] == "2026-07-02"        # rule still wins


# --------------------------------------------------------------------------- #
# Location grounding
# --------------------------------------------------------------------------- #
def test_location_grounded_allowed(client, monkeypatch):
    _mock_llm(monkeypatch, json.dumps({
        "title": "친구와 식사", "date": "2026-07-03", "start_time": "19:00",
        "category": "meal", "location": "강남역", "confidence": 0.82,
    }))
    data = _parse(client, "이번 주 금요일 저녁 7시에 강남역에서 친구랑 밥")["data"]
    assert data["location"] == "강남역"


def test_location_hallucinated_blocked(client, monkeypatch):
    _mock_llm(monkeypatch, json.dumps({
        "title": "병원 예약", "date": None, "start_time": None,
        "category": "health", "location": "서울아산병원", "confidence": 0.8,
    }))
    data = _parse(client, "내일 오후 3시에 병원 예약 있어")["data"]
    assert data["location"] is None
    assert any("장소" in w for w in data["warnings"])


# --------------------------------------------------------------------------- #
# Clarification UX
# --------------------------------------------------------------------------- #
def test_clarification_when_incomplete(client):
    data = _parse(client, "미용실 예약해야 돼", use_llm=False)["data"]
    assert data["needs_clarification"] is True
    assert "date" in data["missing_fields"]
    assert "start_time" in data["missing_fields"]
    assert "언제 일정으로 등록할까요?" in data["clarification_questions"]
    assert "몇 시에 시작하는 일정인가요?" in data["clarification_questions"]


def test_no_clarification_when_complete(client):
    data = _parse(client, "내일 오후 3시에 병원 예약")["data"]
    assert data["needs_clarification"] is False
    assert data["missing_fields"] == []


# --------------------------------------------------------------------------- #
# Confirm endpoint (DB-backed)
# --------------------------------------------------------------------------- #
def _confirm(client, parsed, user_id="local-user"):
    return client.post(CONFIRM, json={"user_id": user_id, "parsed": parsed})


def test_confirm_saves_local_schedule(db_client):
    parsed = {
        "original_text": "내일 오후 3시에 병원 예약 있어", "title": "병원 예약",
        "date": "2026-07-02", "start_time": "15:00", "end_time": None,
        "category": "health", "location": None, "memo": None, "is_all_day": False,
    }
    r = _confirm(db_client, parsed)
    assert r.status_code == 200, r.text
    saved = r.json()["data"]["schedule"]
    assert saved["id"]
    assert saved["title"] == "병원 예약"
    assert saved["date"] == "2026-07-02" and saved["start_time"] == "15:00"
    assert saved["category"] == "health"
    listed = db_client.get(f"{LOCAL}?date=2026-07-02").json()["data"]
    assert any(s["id"] == saved["id"] for s in listed)


def test_confirm_rejects_missing_date(db_client):
    r = _confirm(db_client, {"title": "병원 예약", "start_time": "15:00"})
    assert r.status_code == 422
    assert r.json()["success"] is False


def test_confirm_rejects_missing_start_time_non_allday(db_client):
    r = _confirm(db_client, {"title": "병원 예약", "date": "2026-07-02", "is_all_day": False})
    assert r.status_code == 422


def test_confirm_allday_without_time_ok(db_client):
    parsed = {"title": "워크숍", "date": "2026-07-05", "start_time": None, "is_all_day": True, "category": "work"}
    r = _confirm(db_client, parsed)
    assert r.status_code == 200, r.text
    saved = r.json()["data"]["schedule"]
    assert saved["title"] == "워크숍" and saved["date"] == "2026-07-05"
    assert saved["start_time"] in (None, "00:00")


def test_confirm_rejects_missing_title(db_client):
    r = _confirm(db_client, {"date": "2026-07-02", "start_time": "15:00"})
    assert r.status_code == 422


def test_confirm_rejects_bad_time_format(db_client):
    r = _confirm(db_client, {"title": "x", "date": "2026-07-02", "start_time": "25:99"})
    assert r.status_code == 422


# --------------------------------------------------------------------------- #
# helper: to_schedule_create_request
# --------------------------------------------------------------------------- #
def test_to_schedule_create_request_ok():
    parsed = EnhancedParseData(
        original_text="x", title="병원 예약", date="2026-07-02", start_time="15:00",
        end_time="16:00", category="health", confidence=0.8, parse_source="hybrid",
    )
    sc = to_schedule_create_request(parsed)
    assert sc.title == "병원 예약" and sc.date == "2026-07-02"
    assert sc.start_time == "15:00" and sc.source == "ai"


def test_to_schedule_create_request_requires_date_time():
    parsed = EnhancedParseData(
        original_text="x", title="미용실 예약", category="beauty",
        confidence=0.4, parse_source="rule_fallback",
    )
    with pytest.raises(ValueError):
        to_schedule_create_request(parsed)
