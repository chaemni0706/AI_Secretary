"""Title extraction tests for the improved rule-based schedule pipeline.

Targets `schedule_title_extractor.extract_schedule_title` directly (no DB / no
network) and a couple of orchestration-level regressions.
"""

from backend.database.schema.schedule_schema import ScheduleParseRequest
from backend.services.schedule_parser import build_schedule_plan, parse_schedule
from backend.services.schedule_title_extractor import (
    TITLE_CONFIDENCE_THRESHOLD,
    extract_schedule_title,
)

NOW = "2026-06-29T10:00:00+09:00"  # Monday


# --------------------------------------------------------------------------- #
# A. domain-keyword titles
# --------------------------------------------------------------------------- #
def test_hospital_intent_becomes_visit_title():
    r = extract_schedule_title("나 병원 가려고 일정 잡아줘")
    assert r["title"] == "병원 방문"
    assert r["category"] == "health"
    assert r["source"] == "domain_keyword"
    assert r["matched_keyword"] == "병원"
    assert r["confidence"] >= 0.85


def test_hospital_plain():
    r = extract_schedule_title("내일 병원 일정 잡아줘")
    assert r["title"] == "병원 방문"
    assert r["category"] == "health"


def test_hospital_going():
    assert extract_schedule_title("3시에 병원 가는 일정 잡아줘")["title"] == "병원 방문"
    assert extract_schedule_title("내일 오후 3시에 병원 가는 일정 잡아줘")["title"] == "병원 방문"


def test_beauty_reservation_title():
    r = extract_schedule_title("미용실 예약 잡아줘")
    assert r["title"] == "미용실 예약"
    assert r["category"] == "beauty"


def test_meeting_title():
    r = extract_schedule_title("회의 일정 등록해줘")
    assert r["title"] == "회의"
    assert r["category"] == "meeting"


# --------------------------------------------------------------------------- #
# B. sentence-pattern titles
# --------------------------------------------------------------------------- #
def test_professor_consultation_pattern():
    r = extract_schedule_title("교수님 상담 일정 잡아줘")
    assert r["title"] == "교수님 상담"
    assert r["confidence"] >= TITLE_CONFIDENCE_THRESHOLD


def test_person_cafe_keeps_person():
    r = extract_schedule_title("민수랑 카페 가는 거 추가해줘")
    assert r["title"] in ("민수랑 카페", "민수와 카페")


def test_family_dinner_keeps_person():
    r = extract_schedule_title("가족들이랑 저녁 먹는 일정 넣어줘")
    assert r["title"] in ("가족들과 저녁", "가족들이랑 저녁")


# --------------------------------------------------------------------------- #
# C / D. unclear -> low confidence, no committed title
# --------------------------------------------------------------------------- #
def test_vague_input_is_low_confidence():
    r = extract_schedule_title("그거 내일 잡아줘")
    assert r["confidence"] < TITLE_CONFIDENCE_THRESHOLD
    # low-confidence titles must not be committed by the orchestrator
    plan = build_schedule_plan("그거 내일 잡아줘", NOW)
    assert "title" in plan["missing_fields"]
    assert plan["title"] is None


# --------------------------------------------------------------------------- #
# Legacy endpoint regression: the reported bug is fixed without breaking schema
# --------------------------------------------------------------------------- #
def test_legacy_parse_schedule_title_bug_fixed():
    data = parse_schedule(ScheduleParseRequest(input="나 병원 가려고 일정 잡아줘", current_datetime=NOW))
    assert data.schedule_draft.title == "병원 방문"
    # no fabricated date/time
    assert data.slots.date is None
    assert data.slots.start_time is None
    assert "date" in data.missing_fields
    assert "time" in data.missing_fields
