"""Solution recommender tests (service-level).

Verifies the fixed category set, the selection ORDER, and that every solution
carries the required contract fields.
"""

from backend.services.empathy_engine import select_strategy
from backend.services.intent_classifier import select_intent
from backend.services.solution_recommender import recommend_solutions


def _recommend(message, schedule_context=None, user_profile=None):
    intent = select_intent(message)
    empathy = select_strategy(message, intent)
    return recommend_solutions(
        intent_result=intent,
        empathy_result=empathy,
        schedule_context=schedule_context,
        user_profile=user_profile,
        user_message=message,
    )


def test_risk_expression_selects_safety():
    out = _recommend("다 사라지고 싶어")
    assert out["category"] == "safety"


def test_free_time_under_10_selects_immediate_recovery():
    ctx = {
        "current_time": "2026-06-30T14:55:00",
        "today_schedule": [
            {"id": "e1", "title": "회의", "category": "meeting", "priority": "high",
             "start_time": "2026-06-30T15:00:00", "end_time": "2026-06-30T16:00:00",
             "is_fixed": True},
        ],
    }
    # imminent important event would also fire; free<10 is checked FIRST per spec
    out = _recommend("좀 지치네", ctx)
    assert out["category"] == "immediate_recovery"


def test_imminent_important_event_selects_schedule_support():
    ctx = {
        "current_time": "2026-06-30T14:00:00",
        "today_schedule": [
            {"id": "e1", "title": "면접", "category": "interview", "priority": "high",
             "start_time": "2026-06-30T15:00:00", "end_time": "2026-06-30T16:00:00",
             "is_fixed": True},
        ],
    }
    out = _recommend("좀 지치네", ctx)
    assert out["category"] == "schedule_support"


def test_overwhelmed_selects_task_structuring():
    out = _recommend("일정이 너무 많아서 뭐부터 해야 할지 막막해")
    assert out["category"] == "task_structuring"


def test_free_and_profile_selects_environment_shift():
    ctx = {
        "current_time": "2026-06-30T14:00:00",
        "today_schedule": [
            {"id": "e1", "title": "저녁 약속", "category": "etc", "priority": "low",
             "start_time": "2026-06-30T19:00:00", "end_time": "2026-06-30T20:00:00",
             "is_fixed": False},
        ],
    }
    profile = {"preferred_activity": ["산책"], "favorite_foods": ["디저트"]}
    out = _recommend("기분이 좀 그래", ctx, profile)
    assert out["category"] == "environment_shift"


def test_reschedule_wish_with_low_priority_selects_schedule_adjustment():
    ctx = {
        "current_time": "2026-06-30T15:00:00",
        "today_schedule": [
            {"id": "e2", "title": "과제 정리", "category": "study", "priority": "medium",
             "start_time": "2026-06-30T17:00:00", "end_time": "2026-06-30T18:00:00",
             "is_fixed": False},
        ],
    }
    out = _recommend("과제 시간을 좀 미루고 싶어", ctx)
    assert out["category"] == "schedule_adjustment"


def test_every_solution_has_contract_fields():
    out = _recommend("일정이 너무 많아서 뭐부터 해야 할지 막막해")
    assert out["solutions"]
    for s in out["solutions"]:
        for field in ("category", "solution_type", "title", "reason",
                      "action_buttons", "requires_user_confirmation"):
            assert field in s
        assert s["requires_user_confirmation"] is True
        assert isinstance(s["action_buttons"], list) and s["action_buttons"]
