"""Chat orchestrator tests — full pipeline via the API (POST /api/v1/chat/respond).

Uses the shared `post` fixture (envelope-checked). No real LLM call is made
(no key configured), so answers come from the rule-based fallback.
"""

PATH = "/api/v1/chat/respond"

FORBIDDEN = ["우울증", "불안장애", "공황장애", "질환", "진단", "치료가 필요", "처방", "증상", "환자"]

SCHEDULE = {
    "current_time": "2026-06-30T15:00:00",
    "today_schedule": [
        {"id": "event-1", "title": "팀 회의", "category": "meeting", "priority": "high",
         "start_time": "2026-06-30T14:00:00", "end_time": "2026-06-30T15:00:00",
         "is_fixed": True},
        {"id": "event-2", "title": "과제 정리", "category": "study", "priority": "medium",
         "start_time": "2026-06-30T17:00:00", "end_time": "2026-06-30T18:00:00",
         "is_fixed": False},
    ],
}
PROFILE = {
    "preferred_activity": ["산책", "조용한 카페"],
    "favorite_foods": ["디저트"],
    "preferred_time_blocks": ["afternoon"],
    "preferred_study_hours": [14, 15, 16],
}


def _assert_non_diagnostic(text):
    for term in FORBIDDEN:
        assert term not in text, term


def test_overwhelmed_flow(post):
    body = post(PATH, {
        "user_id": 1,
        "message": "일정이 너무 많아서 어떻게 해야 할지 모르겠어",
        "schedule_context": SCHEDULE,
        "user_profile": PROFILE,
    })
    data = body["data"]
    assert data["selected_intent"] in ("emotion_coaching", "schedule_adjustment")
    assert data["selected_strategy"] == "mixed_affective_cognitive"
    assert data["selected_solution_category"] in ("task_structuring", "schedule_adjustment")
    assert data["answer"]
    assert data["requires_user_confirmation"] is True
    _assert_non_diagnostic(data["answer"])


def test_tired_flow(post):
    body = post(PATH, {
        "user_id": 1,
        "message": "오늘 너무 힘들어",
        "schedule_context": SCHEDULE,
        "user_profile": PROFILE,
    })
    data = body["data"]
    assert data["selected_strategy"] == "affective"
    assert data["selected_solution_category"] in (
        "immediate_recovery", "schedule_support", "task_structuring", "environment_shift"
    )
    assert data["solutions"]
    _assert_non_diagnostic(data["answer"])


def test_reschedule_flow(post):
    body = post(PATH, {
        "user_id": 1,
        "message": "과제 시간을 좀 미루고 싶어",
        "target_event_id": "event-2",
        "schedule_context": SCHEDULE,
        "user_profile": PROFILE,
    })
    data = body["data"]
    assert data["selected_intent"] == "schedule_adjustment"
    assert data["selected_solution_category"] == "schedule_adjustment"
    assert data["reschedule_candidates"], "expected reschedule candidates"
    for c in data["reschedule_candidates"]:
        assert c["requires_user_confirmation"] is True
        assert 0.0 <= c["score"] <= 1.0


def test_response_envelope_and_contract(post):
    body = post(PATH, {"message": "그냥 얘기하고 싶어"})
    data = body["data"]
    expected = {
        "selected_intent", "selected_strategy", "selected_solution_category",
        "intent_scores", "empathy_scores", "matched_keywords", "solutions",
        "reschedule_candidates", "answer", "requires_user_confirmation",
    }
    assert expected.issubset(set(data.keys()))


def test_crisis_message_is_safe(post):
    body = post(PATH, {"message": "다 사라지고 싶어"})
    data = body["data"]
    assert data["selected_solution_category"] == "safety"
    _assert_non_diagnostic(data["answer"])
    assert "전문가" in data["answer"] or "신뢰" in data["answer"]
