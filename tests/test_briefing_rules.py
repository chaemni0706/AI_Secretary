"""Briefing rule-engine tests.

Exercise the externalized briefing_rules.json: daypart mapping, summary/key
template usage, completed-todo handling, priority ordering, LLM fallback, and
the never-raises guarantee when the rules file is missing/corrupt.

conftest is not imported as a module; the generator is exercised directly.
"""

from backend.database.schema.briefing_schema import (
    BriefingSchedule,
    BriefingTodo,
    DailyBriefingRequest,
)
from backend.services import briefing_generator as bg


def _req(schedules=None, todos=None):
    return DailyBriefingRequest(
        date="2026-06-30",
        schedules=[BriefingSchedule(**s) for s in (schedules or [])],
        todos=[BriefingTodo(**t) for t in (todos or [])],
    )


# --- daypart -------------------------------------------------------------- #
def test_daypart_rules_from_json():
    assert bg._daypart("09:00") == "오전"
    assert bg._daypart("14:00") == "오후"
    assert bg._daypart("19:00") == "저녁"
    assert bg._daypart("23:00") == "밤"   # default / wrap
    assert bg._daypart("03:00") == "밤"
    assert bg._daypart(None) == ""


# --- default fallback when file missing/corrupt --------------------------- #
def test_briefing_rules_fallback_to_default(monkeypatch):
    """briefing_rules.json이 없을 때 default rule로 fallback되는지 확인한다.

    단, _RULES_DIR 전체를 nonexistent path로 바꾸면 priority_rules.json까지
    찾지 못해 priority 계산이 깨지므로, generate_briefing까지 호출하지 않고
    briefing rule loader의 fallback 동작만 검증한다.
    """
    bg._briefing_rules.cache_clear()

    monkeypatch.setattr(bg, "_RULES_DIR", bg.Path("/nonexistent/path/xyz"))

    rules = bg._briefing_rules()
    assert rules is bg.DEFAULT_BRIEFING_RULES
    assert rules["summary_templates"]["no_schedules"]

    bg._briefing_rules.cache_clear()


# --- summary template ----------------------------------------------------- #
def test_summary_includes_schedule_listing():
    data = bg.generate_briefing(_req([
        {"title": "오전 수업", "category": "school", "start_time": "09:00", "priority": "medium"},
        {"title": "병원 예약", "category": "hospital", "start_time": "14:00", "priority": "high"},
    ], []))
    assert "오전 수업" in data.summary
    assert "오후 병원 예약" in data.summary


def test_summary_no_schedules():
    data = bg.generate_briefing(_req([], []))
    assert data.summary == bg._briefing_rules()["summary_templates"]["no_schedules"]


# --- key points ----------------------------------------------------------- #
def test_key_points_top_and_high_todo():
    data = bg.generate_briefing(_req(
        [{"title": "병원 예약", "category": "hospital", "start_time": "14:00", "priority": "high"}],
        [{"title": "진료카드 챙기기", "priority": "high", "is_done": False}]))
    assert any("가장 중요한 일정입니다" in k for k in data.key_points)
    assert any("진료카드" in k for k in data.key_points)


def test_completed_todo_excluded_from_key_points():
    data = bg.generate_briefing(_req(
        [{"title": "병원 예약", "category": "hospital", "start_time": "14:00", "priority": "high"}],
        [{"title": "진료카드 챙기기", "priority": "high", "is_done": True}]))
    assert not any("진료카드" in k for k in data.key_points)


# --- priority order (unchanged behaviour) --------------------------------- #
def test_priority_order_high_first_then_time():
    data = bg.generate_briefing(_req([
        {"title": "기말 시험", "category": "study", "start_time": "10:00", "priority": "medium"},
        {"title": "병원 예약", "category": "hospital", "start_time": "15:00", "priority": "medium"},
        {"title": "점심 약속", "category": "personal", "start_time": "12:00", "priority": "medium"},
    ], []))
    titles = [p.title for p in data.priority_order]
    assert titles[:2] == ["기말 시험", "병원 예약"]   # highs first, by time
    assert titles[-1] == "점심 약속"


# --- LLM fallback --------------------------------------------------------- #
def test_llm_failure_falls_back_to_template(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("LLM down")
    monkeypatch.setattr(bg.llm_service, "generate", boom)
    data = bg.generate_briefing(_req(
        [{"title": "병원 예약", "category": "hospital", "start_time": "14:00", "priority": "high"}], []))
    assert data.summary and "병원 예약" in data.summary


def test_llm_summary_used_when_available(monkeypatch):
    monkeypatch.setattr(bg.llm_service, "generate", lambda *a, **k: "LLM 요약 문장")
    data = bg.generate_briefing(_req(
        [{"title": "병원 예약", "category": "hospital", "start_time": "14:00", "priority": "high"}], []))
    assert data.summary == "LLM 요약 문장"
    # priority_order / key_points stay rule-based
    assert data.priority_order[0].title == "병원 예약"
    assert data.key_points


# --- response schema unchanged ------------------------------------------- #
def test_response_schema_unchanged():
    data = bg.generate_briefing(_req(
        [{"title": "병원 예약", "category": "hospital", "start_time": "14:00", "priority": "high"}], []))
    dumped = data.model_dump()
    assert set(dumped.keys()) == {"summary", "key_points", "priority_order"}
    assert set(dumped["priority_order"][0].keys()) == {"title", "priority", "reason"}
