"""Rule-based reservation message engine — regression tests.

These exercise the engine directly (fast, no TestClient) plus the documented
invariants: generated_message is always a non-empty str and alternatives is
always exactly length 2. The API-level contract is already covered by
tests/test_api.py::test_message_required_fields and tests/test_llm.py.
"""

from backend.database.schema.message_schema import (
    MessageStyle,
    ReservationInfo,
    ReservationMessageRequest,
)
from backend.services import message_generator as mg


def _req(input=None, category="etc", target_date=None, preferred_time=None,
         purpose=None, tone="polite", length="short", channel="sms"):
    return ReservationMessageRequest(
        input=input,
        reservation_info=ReservationInfo(
            category=category, target_date=target_date,
            preferred_time=preferred_time, purpose=purpose),
        style=MessageStyle(tone=tone, length=length, channel=channel),
    )


# --- classification ------------------------------------------------------- #
def test_classify_action_from_utterance():
    rules = mg._load_rules()
    assert mg._classify_action("내일 예약 가능한지 물어봐줘", rules) == "ask_availability"
    assert mg._classify_action("오늘 예약 취소한다고 보내줘", rules) == "cancel_reservation"
    assert mg._classify_action("5시를 7시로 변경 가능한지", rules) == "change_reservation"
    assert mg._classify_action("오후 6시로 예약 확정한다고", rules) == "confirm_reservation"
    assert mg._classify_action("예약되어 있는지 확인 부탁", rules) == "check_reservation"
    # no utterance -> default
    assert mg._classify_action(None, rules) == "ask_availability"


def test_resolve_category_alias_inference():
    rules = mg._load_rules()
    assert mg._resolve_category(None, "미용실 염색 예약", rules) == "beauty"
    assert mg._resolve_category("etc", "치과 진료 예약", rules) == "hospital"
    # explicit valid category wins over utterance
    assert mg._resolve_category("restaurant", "병원 가야 해", rules) == "restaurant"
    assert mg._resolve_category(None, "그냥 예약", rules) == "etc"


def test_extract_people():
    assert mg._extract_people("식당 3명 예약") == 3
    assert mg._extract_people("두 명 예약") == 2
    assert mg._extract_people("네 명이요") == 4
    assert mg._extract_people("인원 미정") is None


# --- per-scenario rendering ---------------------------------------------- #
def test_restaurant_availability():
    d = mg.generate_message(_req(
        input="내일 오후 7시에 식당 3명 예약 가능한지 물어봐줘",
        category="restaurant", target_date="2026-07-01",
        preferred_time="19:00", purpose="식당 예약"))
    assert "예약이 가능한지" in d.generated_message
    assert "3명" in d.generated_message          # people reflected in main
    assert "3명" in d.alternatives[0]            # and in the tone-matched alt
    assert len(d.alternatives) == 2


def test_restaurant_without_people_collapses_cleanly():
    d = mg.generate_message(_req(
        input="내일 7시 식당 예약 가능한지", category="restaurant",
        preferred_time="19:00"))
    assert "명" not in d.generated_message        # no dangling "명"
    assert "{" not in d.generated_message
    assert "  " not in d.generated_message        # no double spaces


def test_missing_required_is_internal_only():
    """required_fields drives an internal gap calculation; it must NOT leak into
    the response (ReservationMessageData has no missing_fields)."""
    rules = mg._load_rules()
    tpl = mg._select_template("ask_availability", "restaurant", rules)
    full = mg._build_slots(_req(input="식당 3명", category="restaurant",
                                preferred_time="19:00"), "restaurant", rules)
    none = mg._build_slots(_req(input="식당", category="restaurant"),
                           "restaurant", rules)
    assert mg._missing_required(tpl, full) == []
    assert set(mg._missing_required(tpl, none)) == {"when_raw", "people"}
    # response object exposes no missing_fields attribute
    d = mg.generate_message(_req(input="식당", category="restaurant"))
    assert not hasattr(d, "missing_fields")
    assert "missing_fields" not in d.model_dump()


def test_hospital_template_used():
    d = mg.generate_message(_req(
        input="내일 오전 10시에 병원 진료 예약 문자 써줘",
        category="hospital", target_date="2026-07-01",
        preferred_time="10:00", purpose="진료 예약"))
    assert "진료" in d.generated_message


def test_beauty_template_uses_purpose():
    d = mg.generate_message(_req(
        input="금요일 오후 3시에 미용실 염색 예약하고 싶어",
        category="beauty", preferred_time="15:00", purpose="염색"))
    assert "염색" in d.generated_message


def test_confirm_reservation():
    d = mg.generate_message(_req(
        input="안내해준 오후 6시로 예약 확정한다고 보내줘",
        category="etc", preferred_time="18:00"))
    assert "확정" in d.generated_message
    assert "6시로" in d.generated_message  # particle agreement


def test_change_reservation():
    d = mg.generate_message(_req(
        input="기존 5시 예약을 7시로 변경 가능한지 물어봐줘",
        category="etc", preferred_time="19:00"))
    assert "변경" in d.generated_message


def test_cancel_reservation():
    d = mg.generate_message(_req(
        input="오늘 예약 취소한다고 정중하게 보내줘",
        category="etc", preferred_time="13:00"))
    assert "취소" in d.generated_message


def test_check_reservation():
    d = mg.generate_message(_req(
        input="내일 2시에 예약되어 있는지 확인 부탁한다고 보내줘",
        category="etc", preferred_time="14:00"))
    assert "되어 있는지" in d.generated_message


# --- robustness / invariants --------------------------------------------- #
def test_missing_date_and_time_does_not_fail():
    d = mg.generate_message(_req(input="식당 예약 가능한지 물어봐줘",
                                 category="restaurant"))
    assert isinstance(d.generated_message, str) and d.generated_message
    assert "{" not in d.generated_message  # no dangling placeholders
    assert len(d.alternatives) == 2


def test_always_str_and_two_alternatives():
    for req in (
        _req(),  # everything empty
        _req(input="아무 말", category="meeting"),
        _req(category="hospital", preferred_time="09:30", tone="casual",
             length="long", channel="sms"),
    ):
        d = mg.generate_message(req)
        assert isinstance(d.generated_message, str) and d.generated_message
        assert isinstance(d.alternatives, list) and len(d.alternatives) == 2
        assert all(isinstance(a, str) and a for a in d.alternatives)


def test_sms_long_is_downgraded():
    long_sms = mg.generate_message(_req(category="etc", preferred_time="10:00",
                                        length="long", channel="sms"))
    # 'long' verbose prefix must not appear on SMS
    assert "바쁘신 와중에" not in long_sms.generated_message


def test_casual_tone_applied():
    d = mg.generate_message(_req(input="식당 예약 가능?", category="restaurant",
                                 preferred_time="19:00", tone="casual"))
    assert "문의해요" in d.generated_message or "부탁해요" in d.generated_message
