"""Unit tests for the voice-input intent router (POST /api/v1/voice/route
classification layer). Independent from ``intent_classifier`` (chat) — see
module docstring in voice_intent_router.py for why the taxonomies differ.

Covers the exact 9 spec test sentences plus the context-gating guarantees for
reminder_setting (must never fire without a pending schedule_created context).
"""

from backend.services.voice_intent_router import select_voice_intent

_SCHEDULE_CREATED_CTX = {"type": "schedule_created", "schedule_id": "abc123", "item_type": "EVENT"}


def _intent(text, context=None):
    return select_voice_intent(text, context=context)["intent"]


# --------------------------------------------------------------------------- #
# 1. reservation_recommendation must win over schedule_create
# --------------------------------------------------------------------------- #
def test_store_recommendation_not_schedule_create():
    assert _intent("가게 추천해줘") == "reservation_recommendation"


def test_nearby_cafe_recommendation():
    assert _intent("근처 카페 추천해줘") == "reservation_recommendation"


def test_reservation_recommendation_outranks_schedule_create_keywords():
    # contains "가게 추천" (reco) but 문장 어디에도 "일정 추가"류 키워드가 없어도
    # 마찬가지로 reservation_recommendation 이어야 한다.
    assert _intent("저녁 먹을 곳 추천해줘") == "reservation_recommendation"
    assert _intent("예약할 만한 곳 추천해줘") == "reservation_recommendation"


# --------------------------------------------------------------------------- #
# 2. emotion_schedule_coaching requires BOTH emotion + schedule reference
# --------------------------------------------------------------------------- #
def test_tired_plus_today_schedule_is_coaching_not_query():
    assert _intent("오늘 진짜 피곤하다 오늘 일정 뭐야") == "emotion_schedule_coaching"


def test_hard_plus_what_to_do_is_coaching():
    assert _intent("너무 힘들어 오늘 뭐 해야 돼") == "emotion_schedule_coaching"


def test_bare_schedule_query_without_emotion_stays_schedule_query():
    assert _intent("오늘 일정 뭐야") == "schedule_query"


def test_bare_emotion_without_schedule_reference_is_not_coaching():
    # 일정 언급이 전혀 없으면 emotion_schedule_coaching 로 분류하지 않는다
    # (감정만으로는 어떤 강한 intent 키워드도 없어 fallback_chat).
    assert _intent("너무 힘들어") == "fallback_chat"


# --------------------------------------------------------------------------- #
# 3. daily_briefing
# --------------------------------------------------------------------------- #
def test_daily_briefing_request():
    assert _intent("오늘 브리핑 해줘") == "daily_briefing"


def test_daily_briefing_request_variant():
    assert _intent("오늘의 브리핑 들려줘") == "daily_briefing"


# --------------------------------------------------------------------------- #
# 4. schedule_create — must not be stolen by a bare '일정' weak-match elsewhere
# --------------------------------------------------------------------------- #
def test_schedule_create_with_date_and_time():
    assert _intent("내일 오후 3시에 병원 일정 추가해줘") == "schedule_create"


def test_schedule_create_via_date_time_signal_without_create_verb():
    # 명시적 '추가해줘' 없이도 날짜+시간이 있으면 schedule_create 로 판단한다
    # (schedule_parser 재사용).
    assert _intent("내일 오후 2시에 치과 예약") == "schedule_create"


# --------------------------------------------------------------------------- #
# 5. reminder_setting — context-gated (spec requirement 7)
# --------------------------------------------------------------------------- #
def test_reminder_confirmation_with_pending_context():
    assert _intent("응 알림 받을래", context=_SCHEDULE_CREATED_CTX) == "reminder_setting"


def test_reminder_minutes_with_pending_context():
    result = select_voice_intent("1시간 전에 알려줘", context=_SCHEDULE_CREATED_CTX)
    assert result["intent"] == "reminder_setting"
    assert result["reminder_minutes"] == 60


def test_reminder_phrase_without_pending_context_is_not_misclassified():
    """The core anti-regression case: a bare '알려줘'/'응 알림 받을래' with NO
    prior schedule_create context must NEVER become reminder_setting."""
    assert _intent("응 알림 받을래") != "reminder_setting"
    assert _intent("1시간 전에 알려줘") != "reminder_setting"


def test_reminder_decline_detected():
    result = select_voice_intent("아니 괜찮아", context=_SCHEDULE_CREATED_CTX)
    assert result["intent"] == "reminder_setting"
    assert result["reminder_decline"] is True


def test_reminder_minutes_parses_30_and_10():
    assert select_voice_intent("30분 전에 알려줘", context=_SCHEDULE_CREATED_CTX)["reminder_minutes"] == 30
    assert select_voice_intent("10분 전에 알려줘", context=_SCHEDULE_CREATED_CTX)["reminder_minutes"] == 10


# --------------------------------------------------------------------------- #
# misc robustness
# --------------------------------------------------------------------------- #
def test_empty_text_is_fallback():
    assert _intent("") == "fallback_chat"


def test_never_raises_on_none_context():
    assert select_voice_intent("아무 말이나", context=None)["intent"] in (
        "reservation_recommendation", "emotion_schedule_coaching", "daily_briefing",
        "schedule_query", "reminder_setting", "schedule_create", "fallback_chat",
    )
