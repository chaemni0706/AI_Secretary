"""'예약' 유지 정책 회귀 테스트.

새 정책: '예약'은 일정의 핵심 목적이므로 title 에 보존한다.
명령 동사(잡아/잡아줘/추가해/등록해/저장해/넣어줘 ...)만 제거한다.

parse_schedule 을 직접 호출한다(외부 의존/DB 없음).
"""

from backend.database.schema.schedule_schema import ScheduleParseRequest
from backend.services.schedule_parser import parse_schedule

NOW = "2026-06-29T10:00:00+09:00"


def _title(text: str) -> str:
    return parse_schedule(
        ScheduleParseRequest(input=text, current_datetime=NOW)
    ).schedule_draft.title


def test_치과_예약_kept():
    assert _title("7월 4일 3시에 치과 예약 잡아") == "치과 예약"


def test_병원_예약_kept():
    assert _title("내일 오후 2시에 병원 예약 잡아줘") == "병원 예약"


def test_미용실_예약_kept():
    assert _title("오늘 저녁 6시에 미용실 예약 등록해줘") == "미용실 예약"


def test_bare_예약_not_empty_or_weird():
    # "예약 잡아줘" -> 명령 동사만 제거. title 은 비거나 이상한 값이면 안 된다.
    t = _title("예약 잡아줘")
    assert t and t.strip()
    assert ("예약" in t) or (t in {"새 일정", "병원 예약"})


def test_회의_일정_still_회의():
    # '예약'이 없는 입력은 그대로. '일정' 필러와 명령 동사만 제거.
    assert _title("금요일 오전 10시에 회의 일정 추가해줘") == "회의"
