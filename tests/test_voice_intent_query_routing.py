"""회귀 테스트: 조회성 발화가 schedule_create 로 새지 않도록(의도 라우팅 정밀화).

문제: schedule_query 가 'strong' 키워드에만 의존해, strong 에 없는 조회 질의
(예: "내일 뭐 있어?", "모레 회의 언제야")가 날짜 신호 때문에 schedule_create 로
잘못 분류되던 것을 수정. 생성 동사(추가/등록/잡아 등)가 있으면 여전히
schedule_create 로 남아야 한다.
"""

from backend.services.voice_intent_router import select_voice_intent


def _intent(text, context=None):
    return select_voice_intent(text, context=context)["intent"]


# --- 조회 질의는 schedule_query 로 --------------------------------------------
def test_whatson_with_date_is_query_not_create():
    assert _intent("내일 뭐 있어?") == "schedule_query"


def test_ref_plus_marker_is_query():
    assert _intent("모레 회의 언제야") == "schedule_query"
    assert _intent("이번 주 일정 알려줘") == "schedule_query"
    assert _intent("일정 뭐 있어") == "schedule_query"


def test_today_whatson_without_emotion_is_query():
    # 감정어가 없으면 emotion_schedule_coaching 이 아니라 schedule_query.
    assert _intent("오늘 뭐 해야 돼") == "schedule_query"


# --- 생성 발화는 여전히 schedule_create --------------------------------------
def test_create_verb_still_create_even_with_query_marker():
    assert _intent("내일 일정 추가해줘") == "schedule_create"
    assert _intent("내일 오후 3시에 병원 일정 추가해줘") == "schedule_create"


def test_datetime_statement_without_query_stays_create():
    # 질의 표지가 없는 순수 등록형 발화.
    assert _intent("내일 오후 2시에 치과 예약") == "schedule_create"


# --- 타 도메인/감정 오분류 방지 ----------------------------------------------
def test_weather_query_not_misrouted_to_schedule_query():
    # '날씨 알려줘'는 일정 지시어/‘뭐 있’류가 없어 schedule_query 로 가면 안 된다.
    assert _intent("내일 날씨 알려줘") != "schedule_query"


def test_emotion_plus_schedule_still_coaching():
    assert _intent("너무 힘들어 오늘 뭐 해야 돼") == "emotion_schedule_coaching"
