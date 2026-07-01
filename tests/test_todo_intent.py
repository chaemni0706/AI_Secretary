"""To-do intent 분류 및 To-do 제목 정제 회귀 테스트.

정책:
- 강한 To-do 신호(작성/제출/정리/장보기/마감/까지/해야 해 ...)가 있고
  schedule-override 키워드(예약/회의/약속/병원/치과/수업/방문/알림)가 없으면
  intent == "create_todo".
- override 키워드가 있으면 To-do 신호가 있어도 "create_schedule" 유지.

parse_schedule 을 직접 호출한다(외부 의존/DB 없음).
"""

from backend.database.schema.schedule_schema import ScheduleParseRequest
from backend.services.schedule_parser import parse_schedule

NOW = "2026-06-29T10:00:00+09:00"  # Monday


def _parse(text: str):
    return parse_schedule(ScheduleParseRequest(input=text, current_datetime=NOW))


# --- create_todo 로 분류되어야 하는 입력 ------------------------------------
def test_todo_보고서_작성():
    d = _parse("오늘 저녁까지 보고서 작성해야 해")
    assert d.intent == "create_todo"
    assert d.schedule_draft.title == "보고서 작성"  # 마감/어미 정리


def test_todo_장보기():
    d = _parse("내일 장보기 추가해줘")
    assert d.intent == "create_todo"
    assert d.schedule_draft.title == "장보기"


def test_todo_과제_제출():
    d = _parse("금요일까지 과제 제출")
    assert d.intent == "create_todo"
    assert d.schedule_draft.title == "과제 제출"


def test_todo_자료_정리():
    d = _parse("오늘 할 일로 자료 정리 추가해줘")
    assert d.intent == "create_todo"
    assert d.schedule_draft.title == "자료 정리"


# --- schedule-override 키워드가 있으면 create_schedule 유지 -----------------
def test_schedule_치과_예약():
    d = _parse("7월 4일 3시에 치과 예약 잡아")
    assert d.intent == "create_schedule"
    # 정책상 '예약'은 제거되어 title 은 '치과'.
    assert d.schedule_draft.title == "치과"


def test_schedule_회의():
    d = _parse("내일 오후 2시에 회의 잡아줘")
    assert d.intent == "create_schedule"
    assert d.schedule_draft.title == "회의"


def test_schedule_병원_예약_알림_stays_schedule():
    # '마감/까지' 없이 '알림'(리마인더)은 일정성으로 유지.
    d = _parse("오늘 밤 11시에 과제 마감 알림해줘")
    assert d.intent == "create_schedule"
