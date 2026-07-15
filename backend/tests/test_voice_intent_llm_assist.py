"""voice_intent_router — 규칙 분류 + LLM 보조 하이브리드 테스트.

- 각 intent 별 규칙 분류 예문 3개 이상(결정적, LLM 미사용)
- 하이브리드: 규칙이 명확하면 LLM 미호출 / fallback 일 때만 LLM 승격 /
  플래그 OFF·저신뢰·실패 시 규칙 유지
LLM 은 monkeypatch 로 대체해 실제 OpenAI 를 호출하지 않는다.
"""

import pytest

from backend.services import voice_intent_router as R

SCHED_CTX = {"type": "schedule_created", "schedule_id": "1"}


# --------------------------------------------------------------------------- #
# 1) 규칙 분류 — intent 별 3개 이상
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text", [
    "근처 카페 추천해줘",
    "저녁 먹을 곳 추천",
    "맛집 추천해 줘",
])
def test_reservation_recommendation(text):
    assert R.select_voice_intent(text)["intent"] == "reservation_recommendation"


@pytest.mark.parametrize("text", [
    "너무 피곤한데 오늘 일정 뭐야",
    "스트레스 받는데 할 일 너무 많아",
    "우울한데 오늘 뭐 해야 하지",
])
def test_emotion_schedule_coaching(text):
    assert R.select_voice_intent(text)["intent"] == "emotion_schedule_coaching"


@pytest.mark.parametrize("text", [
    "오늘 브리핑 해줘",
    "하루 브리핑",
    "브리핑 들려줘",
])
def test_daily_briefing(text):
    assert R.select_voice_intent(text)["intent"] == "daily_briefing"


@pytest.mark.parametrize("text", [
    "오늘 일정 뭐야",
    "내 일정 알려줘",
    "일정 보여줘",
])
def test_schedule_query(text):
    assert R.select_voice_intent(text)["intent"] == "schedule_query"


@pytest.mark.parametrize("text", [
    "미리 알려줘",
    "응 알림",
    "알림 설정",
])
def test_reminder_setting_with_context(text):
    # 문맥 게이팅: 직전 일정 컨텍스트가 있어야 발화됨
    assert R.select_voice_intent(text, context=SCHED_CTX)["intent"] == "reminder_setting"


@pytest.mark.parametrize("text", [
    "회의 일정 추가해줘",
    "병원 일정 등록",
    "내일 오후 2시 치과",  # 날짜/시간 신호만으로도 schedule_create
])
def test_schedule_create(text):
    assert R.select_voice_intent(text)["intent"] == "schedule_create"


@pytest.mark.parametrize("text", [
    "안녕",
    "고마워",
    "네 생각은 어때",
])
def test_fallback_chat(text):
    assert R.select_voice_intent(text)["intent"] == "fallback_chat"


# --------------------------------------------------------------------------- #
# 2) 하이브리드 (규칙 우선 + LLM 보조)
# --------------------------------------------------------------------------- #
def test_hybrid_rule_clear_skips_llm(monkeypatch):
    """규칙이 명확하면 LLM 을 호출하지 않는다."""
    called = {"n": 0}
    monkeypatch.setattr(R, "_llm_classify", lambda t: called.__setitem__("n", 1))
    out = R.select_voice_intent_hybrid("오늘 브리핑 해줘")
    assert out["intent"] == "daily_briefing"
    assert called["n"] == 0


def test_hybrid_flag_off_no_llm(monkeypatch):
    monkeypatch.setattr(R.settings, "ENABLE_LLM_INTENT", False)
    called = {"n": 0}
    monkeypatch.setattr(R, "_llm_classify", lambda t: called.__setitem__("n", 1))
    out = R.select_voice_intent_hybrid("네 생각은 어때")
    assert out["intent"] == "fallback_chat"
    assert called["n"] == 0


def test_hybrid_promotes_on_high_confidence(monkeypatch):
    monkeypatch.setattr(R.settings, "ENABLE_LLM_INTENT", True)
    monkeypatch.setattr(R.llm_service, "is_enabled", lambda: True)
    monkeypatch.setattr(R, "_llm_classify",
                        lambda t: {"intent": "schedule_create", "confidence": 0.9})
    out = R.select_voice_intent_hybrid("그거 하나 넣어둬")
    assert out["intent"] == "schedule_create"
    assert out.get("intent_source") == "llm"


def test_hybrid_low_confidence_keeps_fallback(monkeypatch):
    monkeypatch.setattr(R.settings, "ENABLE_LLM_INTENT", True)
    monkeypatch.setattr(R.llm_service, "is_enabled", lambda: True)
    monkeypatch.setattr(R, "_llm_classify",
                        lambda t: {"intent": "schedule_create", "confidence": 0.3})
    out = R.select_voice_intent_hybrid("네 생각은 어때")
    assert out["intent"] == "fallback_chat"


def test_hybrid_llm_says_fallback_keeps_fallback(monkeypatch):
    monkeypatch.setattr(R.settings, "ENABLE_LLM_INTENT", True)
    monkeypatch.setattr(R.llm_service, "is_enabled", lambda: True)
    monkeypatch.setattr(R, "_llm_classify",
                        lambda t: {"intent": "fallback_chat", "confidence": 0.95})
    out = R.select_voice_intent_hybrid("네 생각은 어때")
    assert out["intent"] == "fallback_chat"


def test_hybrid_llm_failure_keeps_fallback(monkeypatch):
    monkeypatch.setattr(R.settings, "ENABLE_LLM_INTENT", True)
    monkeypatch.setattr(R.llm_service, "is_enabled", lambda: True)

    def boom(_t):
        raise RuntimeError("network")

    monkeypatch.setattr(R, "_llm_classify", boom)
    out = R.select_voice_intent_hybrid("네 생각은 어때")
    assert out["intent"] == "fallback_chat"
