"""voice_route_orchestrator._augment_schedule_with_llm 단위 테스트.

일정 생성 음성 흐름의 'LLM 갭필(enhanced) 보정' 로직을 검증한다.
- 규칙 파서 결과가 항상 우선
- ENABLE_LLM_SCHEDULE_PARSE 꺼짐/규칙 완전/LLM 실패 시 원본 유지
- 규칙이 비운 필드만 enhanced 값으로 채움
- 충돌(규칙 vs LLM) 시 규칙 유지
실제 OpenAI를 호출하지 않도록 parse_enhanced 를 monkeypatch 한다.
"""

import pytest

from backend.services import voice_route_orchestrator as O
from backend.database.schema.schedule_schema import (
    ScheduleDraft,
    ScheduleParseData,
    ScheduleSlots,
)
from backend.database.schema.schedule_parse_schema import EnhancedParseData
from backend.database.schema.voice_route_schema import VoiceRouteRequest


def _parsed(intent="create_schedule", *, title="치과", date="2026-07-02",
            start_time=None, missing=None):
    draft = ScheduleDraft(title=title, date=date, start_time=start_time)
    return ScheduleParseData(
        intent=intent,
        confidence=0.7,
        slots=ScheduleSlots(),
        schedule_draft=draft,
        missing_fields=missing if missing is not None else [],
        tts_text=None,
    )


def _req():
    return VoiceRouteRequest(text="내일 치과 예약", current_datetime="2026-07-01T10:00:00+09:00")


def _stub_enhanced(monkeypatch, **fields):
    def fake(_req):
        return EnhancedParseData(original_text="", **fields), "msg"
    monkeypatch.setattr(O, "parse_enhanced", fake)


def test_flag_off_returns_original(monkeypatch):
    monkeypatch.setattr(O.settings, "ENABLE_LLM_SCHEDULE_PARSE", False)
    called = {"n": 0}
    monkeypatch.setattr(O, "parse_enhanced", lambda r: called.__setitem__("n", 1))
    p = _parsed(start_time=None, missing=["time"])
    out = O._augment_schedule_with_llm(p, _req())
    assert out.schedule_draft.start_time is None
    assert out.missing_fields == ["time"]
    assert called["n"] == 0  # LLM 미호출


def test_rule_complete_skips_llm(monkeypatch):
    monkeypatch.setattr(O.settings, "ENABLE_LLM_SCHEDULE_PARSE", True)
    called = {"n": 0}
    monkeypatch.setattr(O, "parse_enhanced", lambda r: called.__setitem__("n", 1))
    p = _parsed(date="2026-07-02", start_time="14:00", missing=[])
    out = O._augment_schedule_with_llm(p, _req())
    assert out.schedule_draft.start_time == "14:00"
    assert called["n"] == 0  # 규칙이 다 채워 LLM 미호출


def test_fills_missing_time(monkeypatch):
    monkeypatch.setattr(O.settings, "ENABLE_LLM_SCHEDULE_PARSE", True)
    _stub_enhanced(monkeypatch, start_time="14:00", end_time="15:00")
    p = _parsed(date="2026-07-02", start_time=None, missing=["time"])
    out = O._augment_schedule_with_llm(p, _req())
    assert out.schedule_draft.start_time == "14:00"
    assert "time" not in out.missing_fields


def test_conflict_keeps_rule(monkeypatch):
    monkeypatch.setattr(O.settings, "ENABLE_LLM_SCHEDULE_PARSE", True)
    _stub_enhanced(monkeypatch, date="2026-12-31", start_time="14:00")
    p = _parsed(date="2026-07-02", start_time=None, missing=["time"])
    out = O._augment_schedule_with_llm(p, _req())
    assert out.schedule_draft.date == "2026-07-02"  # 규칙 우선(충돌 시 규칙)
    assert out.schedule_draft.start_time == "14:00"  # 비었던 필드는 채움


def test_promotes_unknown_intent(monkeypatch):
    monkeypatch.setattr(O.settings, "ENABLE_LLM_SCHEDULE_PARSE", True)
    _stub_enhanced(monkeypatch, title="치과", date="2026-07-02",
                   start_time="14:00", item_type="EVENT")
    p = _parsed(intent="unknown", title="", date=None,
                missing=["title", "date", "time"])
    out = O._augment_schedule_with_llm(p, _req())
    assert out.intent == "create_schedule"
    assert out.missing_fields == []


def test_llm_failure_keeps_rule(monkeypatch):
    monkeypatch.setattr(O.settings, "ENABLE_LLM_SCHEDULE_PARSE", True)

    def boom(_req):
        raise RuntimeError("network")

    monkeypatch.setattr(O, "parse_enhanced", boom)
    p = _parsed(date="2026-07-02", start_time=None, missing=["time"])
    out = O._augment_schedule_with_llm(p, _req())
    assert out.schedule_draft.start_time is None
    assert out.missing_fields == ["time"]
