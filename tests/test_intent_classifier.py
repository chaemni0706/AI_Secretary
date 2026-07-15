"""Intent classifier tests (service-level, rule-based)."""

from backend.services.intent_classifier import select_intent


def _intent(text):
    return select_intent(text)["intent"]


def test_reservation_message():
    assert _intent("예약 문자 써줘") == "reservation_message"


def test_reservation_recommend():
    assert _intent("내일 병원 예약 언제 하면 좋을까?") == "reservation_recommend"


def test_schedule_query():
    assert _intent("오늘 일정 알려줘") == "schedule_query"


def test_schedule_adjustment():
    assert _intent("일정이 너무 많아서 하나 옮기고 싶어") == "schedule_adjustment"


def test_emotion_coaching():
    assert _intent("오늘 너무 힘들어") == "emotion_coaching"


def test_smalltalk():
    assert _intent("그냥 얘기하고 싶어") == "smalltalk"


def test_fallback_on_empty():
    assert _intent("") == "fallback"


def test_scores_shape():
    result = select_intent("오늘 일정 알려줘")
    assert isinstance(result["scores"], dict)
    assert result["scores"]["schedule_query"] > 0
