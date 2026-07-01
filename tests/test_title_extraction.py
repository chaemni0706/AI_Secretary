"""Title 추출 개선 회귀 테스트.

정책: '예약'은 일정의 핵심 목적이므로 title 에 보존한다 (병원 예약 -> 병원 예약).
명령형(잡아/추가해/등록해/저장해/넣어)과 '할 일로'/'일정으로' 앞부분 필러,
마감 표현(~까지)만 제거한다.

parse_schedule 을 직접 호출한다(외부 의존/DB 없음).
"""

from backend.database.schema.schedule_schema import ScheduleParseRequest
from backend.services.schedule_parser import parse_schedule

NOW = "2026-06-29T10:00:00+09:00"


def _title(text: str) -> str:
    data = parse_schedule(
        ScheduleParseRequest(input=text, current_datetime=NOW)
    )
    return data.schedule_draft.title


def test_bare_command_verb_잡아_removed():
    # '잡아'(줘 없음)만 제거하고 '예약'은 title 에 보존한다.
    assert _title("7월 4일 3시에 치과 예약 잡아") == "치과 예약"


def test_command_verb_잡아줘_removed():
    assert _title("내일 오후 2시에 병원 예약 잡아줘") == "병원 예약"


def test_noise_noun_일정_and_추가해줘_removed():
    assert _title("금요일 오전 10시에 회의 일정 추가해줘") == "회의"


def test_bare_command_verb_등록해_removed():
    assert _title("오늘 저녁 6시에 미용실 예약 등록해") == "미용실 예약"


def test_bare_command_verb_저장해_removed():
    assert _title("내일 3시에 회의 저장해") == "회의"


def test_leading_할일로_removed():
    assert _title("내일 할 일로 장보기 추가해줘") == "장보기"


def test_multiword_title_preserved():
    # 명령 동사만 제거하고 본문 명사구는 보존.
    assert _title("7월 5일 1시에 친구랑 점심 약속 잡아줘") == "친구랑 점심 약속"


def test_verb_not_over_stripping_real_word():
    # '해'(1글자)를 지우지 않으므로 '항해' 같은 단어가 잘리면 안 된다.
    assert _title("내일 3시에 항해 일정 추가해줘") == "항해"
