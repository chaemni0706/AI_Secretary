"""Tests for assistant_style_service + its wiring into schedule clarification,
chat tts_text and reminder strength. Rule-based, no LLM / no DB.
"""

from backend.services import assistant_style_service as style
from backend.services import user_preference_service as prefs_svc
from backend.services.schedule_parser import build_schedule_plan

NOW = "2026-06-29T10:00:00+09:00"
MISSING = ["date", "time", "location"]


# --------------------------------------------------------------------------- #
# build_style_profile — defaults + enum/field mapping
# --------------------------------------------------------------------------- #
def test_default_profile_when_no_preferences():
    p = style.build_style_profile(None)
    assert p == {"tone": "friendly", "length": "medium", "strength": "normal"}


def test_profile_maps_legacy_enums():
    p = style.build_style_profile(
        {"assistant_tone": "polite", "response_length": "detailed", "nudge_strength": "high"}
    )
    assert p == {"tone": "formal", "length": "long", "strength": "strong"}


def test_profile_maps_spec_enums_and_reminder_field():
    p = style.build_style_profile(
        {"assistant_tone": "formal", "response_length": "long", "reminder_strength": "gentle"}
    )
    assert p == {"tone": "formal", "length": "long", "strength": "gentle"}


# --------------------------------------------------------------------------- #
# tone wording in clarification
# --------------------------------------------------------------------------- #
def _clar(tone, length="medium"):
    profile = {"tone": tone, "length": length, "strength": "normal"}
    return style.build_clarification_text("병원 방문", MISSING, profile)


def test_friendly_tone_markers():
    text = _clar("friendly")
    assert "좋아요" in text and "할까요" in text


def test_formal_tone_markers():
    text = _clar("formal")
    assert "등록하겠습니다" in text and "알려주세요" in text


def test_caring_tone_markers():
    text = _clar("caring")
    assert "제가 챙겨드릴게요" in text and "편하신" in text


# --------------------------------------------------------------------------- #
# response length
# --------------------------------------------------------------------------- #
def test_short_is_shorter_than_long():
    short = _clar("caring", "short")
    long = _clar("caring", "long")
    assert len(short) < len(long)


def test_apply_response_style_short_truncates():
    text = "좋아요, 등록해둘게요. 시간은 언제로 할까요? 필요하면 알림도 설정할게요."
    short = style.apply_response_style(text, {"tone": "friendly", "length": "short", "strength": "normal"})
    long = style.apply_response_style(text, {"tone": "friendly", "length": "long", "strength": "normal"})
    assert len(short) < len(long)


# --------------------------------------------------------------------------- #
# reminder strength
# --------------------------------------------------------------------------- #
def test_gentle_reminder_is_few_and_soft():
    profile = {"tone": "friendly", "length": "medium", "strength": "gentle"}
    assert len(style.reminder_offsets(profile)) == 1
    assert "가볍게" in style.build_reminder_text("회의", profile)


def test_strong_reminder_is_many_and_firm():
    profile = {"tone": "friendly", "length": "medium", "strength": "strong"}
    assert len(style.reminder_offsets(profile)) == 3
    msg = style.build_reminder_text("회의", profile)
    assert "중요한" in msg and "꼭" in msg


def test_strong_has_more_reminders_than_gentle():
    g = style.reminder_offsets({"strength": "gentle"})
    s = style.reminder_offsets({"strength": "strong"})
    assert len(s) > len(g)


# --------------------------------------------------------------------------- #
# notification_plan_builder wiring (opt-in reminder_strength; default unchanged)
# --------------------------------------------------------------------------- #
def test_notification_strength_reminders_scale_and_default_unchanged():
    from backend.services import notification_plan_builder as npb

    none = npb._strength_reminders("회의", None, "2026-06-30", "14:00")
    gentle = npb._strength_reminders("회의", "gentle", "2026-06-30", "14:00")
    strong = npb._strength_reminders("회의", "strong", "2026-06-30", "14:00")
    assert none == []                       # default plan unchanged
    assert len(gentle) == 1 and len(strong) == 3
    assert "가볍게" in gentle[0].message
    assert "중요한" in strong[0].message
    assert gentle[0].trigger_time is not None


# --------------------------------------------------------------------------- #
# schedule clarification reflects preference (via build_schedule_plan)
# --------------------------------------------------------------------------- #
def test_schedule_plan_default_unchanged_without_preferences():
    p = build_schedule_plan("나 병원 가려고 일정 잡아줘", NOW)
    # default rule-base wording (category question bank), NOT styled
    assert "어느 병원" in p["clarification_message"]


def test_schedule_plan_friendly_style():
    p = build_schedule_plan(
        "나 병원 가려고 일정 잡아줘", NOW,
        preferences={"assistant_tone": "friendly", "response_length": "short"},
    )
    assert "좋아요" in p["clarification_message"] or "할까요" in p["clarification_message"]


def test_schedule_plan_formal_style():
    p = build_schedule_plan(
        "나 병원 가려고 일정 잡아줘", NOW,
        preferences={"assistant_tone": "formal", "response_length": "medium"},
    )
    assert "등록하겠습니다" in p["clarification_message"]
    assert "알려주세요" in p["clarification_message"]


def test_schedule_plan_by_user_id_lookup():
    prefs_svc.update_user_preferences("style-user", {"assistant_tone": "caring"})
    p = build_schedule_plan("나 병원 가려고 일정 잡아줘", NOW, user_id="style-user")
    assert "제가 챙겨드릴게요" in p["clarification_message"]


# --------------------------------------------------------------------------- #
# chat tts_text reflects preference
# --------------------------------------------------------------------------- #
def test_chat_tts_text_reflects_preference():
    from backend.database.schema.chat_schema import ChatRespondRequest
    from backend.services import chat_orchestrator

    # ChatRespondRequest.user_id is Optional[int]; the pref store keys by str(id).
    prefs_svc.update_user_preferences("101", {"assistant_tone": "friendly"})
    prefs_svc.update_user_preferences("102", {"assistant_tone": "concise"})
    a = chat_orchestrator.respond(ChatRespondRequest(message="오늘 좀 지치네요", user_id=101))
    b = chat_orchestrator.respond(ChatRespondRequest(message="오늘 좀 지치네요", user_id=102))
    # both produce a spoken line, and the two tones differ
    assert a.tts_text and b.tts_text
    assert a.tts_text != b.tts_text
