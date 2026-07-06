"""Date/time/location policy tests: the parser must NEVER invent a slot.

Targets the additive orchestrator `schedule_parser.build_schedule_plan` and the
legacy `parse_schedule`. Base date fixed to a Monday so relative dates resolve
deterministically. Location requirement is category-driven
(schedule_location_policy.json).
"""

from backend.database.schema.schedule_schema import ScheduleParseRequest
from backend.services.schedule_parser import build_schedule_plan, parse_schedule

NOW = "2026-06-29T10:00:00+09:00"  # Monday
TOMORROW = "2026-06-30"


def _plan(text: str) -> dict:
    return build_schedule_plan(text, NOW)


# 1. no date, no time, generic 병원 -> date+time+location all missing
def test_no_date_no_time():
    p = _plan("나 병원 가려고 일정 잡아줘")
    assert p["title"] == "병원 방문"
    assert p["category"] == "health"
    assert p["date"] is None and p["time"] is None
    assert p["start_time"] is None and p["end_time"] is None
    assert {"date", "time", "location"}.issubset(set(p["missing_fields"]))
    assert p["status"] == "needs_clarification"


# 2. date only (health still needs location for generic 병원)
def test_date_only():
    p = _plan("내일 병원 일정 잡아줘")
    assert p["title"] == "병원 방문"
    assert p["date"] == TOMORROW
    assert p["time"] is None
    assert p["missing_fields"] == ["time", "location"]
    assert p["status"] == "needs_clarification"


# 3. time only (bare '3시' -> 15:00 per existing policy)
def test_time_only():
    p = _plan("3시에 병원 가는 일정 잡아줘")
    assert p["title"] == "병원 방문"
    assert p["date"] is None
    assert p["time"] == "15:00"
    assert p["missing_fields"] == ["date", "location"]


# 4. specific place + date + time -> success, nothing missing
def test_all_present_with_specific_place():
    p = _plan("내일 오후 3시에 포항성모병원 가려고 일정 잡아줘")
    assert p["title"] == "병원 방문"
    assert p["category"] == "health"
    assert p["location"] == "포항성모병원"
    assert p["date"] == TOMORROW
    assert p["time"] == "15:00"
    assert p["start_time"] == "15:00"
    assert p["end_time"] == "16:00"
    assert p["missing_fields"] == []
    assert p["status"] == "success"


# clarification messages reflect exactly what is missing (category-aware)
def test_clarification_messages():
    assert "어느 병원" in _plan("나 병원 가려고 일정 잡아줘")["clarification_message"]
    assert _plan("그거 잡아줘")["clarification_message"] == "어떤 일정으로 등록할까요?"


# legacy endpoint never fabricates date/time (already-locked behaviour)
def test_legacy_parser_reports_missing_without_fabrication():
    data = parse_schedule(ScheduleParseRequest(input="병원 예약 잡아줘", current_datetime=NOW))
    assert data.slots.date is None
    assert data.slots.start_time is None
    assert data.schedule_draft.date is None
    assert data.schedule_draft.start_time is None
    assert "date" in data.missing_fields
    assert "time" in data.missing_fields
