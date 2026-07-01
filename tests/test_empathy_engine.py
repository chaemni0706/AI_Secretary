"""Empathy engine tests (service-level).

Strategy selection is rule-based and deterministic. The final answer must stay
non-diagnostic and never claim lived experience, even without an LLM key.
"""

from backend.services.empathy_engine import (
    build_prompt,
    generate_empathy_response,
    is_safe_answer,
    select_strategy,
)
from backend.services.intent_classifier import select_intent


def _strategy(text):
    return select_strategy(text, select_intent(text))["strategy"]


def test_affective():
    assert _strategy("오늘 너무 힘들어") == "affective"


def test_mixed_when_emotion_and_solution():
    assert _strategy("일정이 너무 많아서 어떻게 해야 할지 모르겠어") == "mixed_affective_cognitive"


def test_cognitive_for_reservation_recommend():
    assert _strategy("내일 병원 예약 언제 하면 좋을까?") == "cognitive"


def test_sleepy_mixed():
    # affect ("졸리다"/"어떡해") + implicit help request
    assert _strategy("아 졸리다 잠와 어떡해") == "mixed_affective_cognitive"


def test_sharing():
    assert _strategy("그냥 얘기하고 싶어") == "sharing"


def test_ambiguous_is_affective_or_fallback():
    assert _strategy("뭔가 기분이 이상해") in ("affective", "fallback_llm_classification")


def test_prompt_hides_reasoning_and_requests_confirmation():
    strat = select_strategy("일정이 많아서 막막해", select_intent("일정이 많아서 막막해"))
    prompt = build_prompt("일정이 많아서 막막해", strat, schedule_context={"today_schedule": []})
    assert "노출하지" in prompt  # instructs the model to hide internal reasoning
    assert "확인" in prompt


def test_fallback_answer_is_safe_without_llm():
    strat = select_strategy("오늘 너무 힘들어", select_intent("오늘 너무 힘들어"))
    out = generate_empathy_response(
        "오늘 너무 힘들어",
        strat,
        emotion_result={"emotion": "fatigue"},
        solution_context={"category": "immediate_recovery", "solutions": [
            {"title": "5분 호흡으로 잠시 숨 고르기"}
        ]},
    )
    assert out["answer"]
    assert is_safe_answer(out["answer"])


def test_safety_answer_bypasses_llm_and_is_safe():
    strat = {"strategy": "affective"}
    out = generate_empathy_response(
        "다 사라지고 싶어",
        strat,
        emotion_result={"emotion": "sadness", "risk_level": "high"},
        solution_context={"category": "safety", "solutions": []},
    )
    assert out["used_llm"] is False
    assert "전문가" in out["answer"] or "신뢰" in out["answer"]
    assert is_safe_answer(out["answer"])
