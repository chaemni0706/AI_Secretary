"""Empathy engine — empathy-strategy selection + response generation.

Sits ON TOP of the existing rule-based emotion analyzer. It does NOT re-detect
emotion labels (that stays in ``emotion_analyzer``); instead it consumes the
emotion + intent to decide *how* to empathize, builds a Chain-of-Empathy prompt
for the optional LLM, and always provides a safe rule-based fallback answer.

Guarantees:
- Never raises.
- LLM is optional; when ``llm_service.generate`` returns None (no key / failure)
  the rule-based ``answer`` is used. Same contract as every other service.
- Diagnostic / clinical wording is screened out; a draft containing forbidden
  terms is discarded in favour of the template.
- The assistant never claims lived experience and never states it will change a
  schedule automatically.

Public API:
    load_rules() -> dict
    score_empathy(text) -> dict
    select_strategy(text, intent_result=None) -> dict
    build_prompt(user_message, strategy, schedule_context=None,
                 user_profile=None, solution_context=None) -> str
    generate_empathy_response(user_message, strategy, emotion_result,
                              solution_context=None, schedule_context=None,
                              user_profile=None) -> dict
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from backend.services import llm_service

_RULES_PATH = Path(__file__).resolve().parents[1] / "rules" / "empathy_rules.json"

STRATEGIES = (
    "affective",
    "cognitive",
    "sharing",
    "mixed_affective_cognitive",
    "direct_task",
    "fallback_llm_classification",
)

# Diagnostic / clinical phrasings that must never appear in the final answer.
# Aligned with the existing emotion_analyzer contract (superset).
_FORBIDDEN_TERMS = (
    "우울증", "불안장애", "공황장애", "질환", "진단", "치료가 필요", "처방",
    "증상", "환자", "상담 치료", "장애", "병이",
)

# Phrasings that falsely claim the assistant has lived experience.
_EXPERIENCE_CLAIMS = ("나도 그런 적", "나도 그랬", "내 경험", "나도 겪")

_TASK_INTENTS = {
    "schedule_create",
    "schedule_query",
    "daily_briefing",
    "reservation_recommend",
    "reservation_message",
}


@lru_cache(maxsize=1)
def load_rules() -> dict:
    with open(_RULES_PATH, encoding="utf-8") as f:
        return json.load(f)


def is_safe_answer(text: str) -> bool:
    """True when text is free of diagnostic wording and false experience claims."""
    if any(term in text for term in _FORBIDDEN_TERMS):
        return False
    if any(claim in text for claim in _EXPERIENCE_CLAIMS):
        return False
    return True


def _matched(text: str, keywords: List[str]) -> List[str]:
    return [kw for kw in keywords if kw in text]


def score_empathy(text: str) -> Dict[str, float]:
    """Weighted score per empathy *signal* (not per strategy)."""
    rules = load_rules()
    text = text or ""
    scores: Dict[str, float] = {}
    for name, cfg in rules["signals"].items():
        hits = _matched(text, cfg["keywords"])
        scores[name] = float(cfg["weight"] * len(hits))
    return scores


def _matched_signal_keywords(text: str) -> Dict[str, List[str]]:
    rules = load_rules()
    text = text or ""
    out: Dict[str, List[str]] = {}
    for name, cfg in rules["signals"].items():
        hits = _matched(text, cfg["keywords"])
        if hits:
            out[name] = hits
    return out


def select_strategy(text: str, intent_result: Optional[dict] = None) -> dict:
    """Choose one empathy strategy from signal scores + intent.

    Returns {"strategy", "scores", "matched_keywords", "intent"}.
    """
    scores = score_empathy(text)
    intent = (intent_result or {}).get("intent", "fallback")

    emotion = scores.get("emotion_expression", 0.0)
    solution = scores.get("solution_request", 0.0)
    sharing = scores.get("sharing_wish", 0.0)
    task = scores.get("task_intent", 0.0)

    # 1. Explicit wish to just talk -> sharing.
    if sharing > 0 and sharing >= emotion:
        strategy = "sharing"
    # 2. Both feeling AND a solve request -> mixed.
    elif emotion > 0 and solution > 0:
        strategy = "mixed_affective_cognitive"
    # 3. Schedule-adjustment intent always has an affective + cognitive tension.
    elif intent == "schedule_adjustment":
        strategy = "mixed_affective_cognitive"
    # 4. Feeling only -> affective.
    elif emotion > 0:
        strategy = "affective"
    # 5. Clear functional task, little/no affect -> depends on intent.
    elif intent in _TASK_INTENTS:
        # reservation_recommend reads as "analyze the situation" -> cognitive;
        # the rest are pure task execution -> direct_task.
        strategy = "cognitive" if intent == "reservation_recommend" else "direct_task"
    elif solution > 0 or task > 0:
        strategy = "cognitive"
    # 6. Nothing confident -> let an LLM decide (rule fallback still answers).
    else:
        strategy = "fallback_llm_classification"

    return {
        "strategy": strategy,
        "scores": scores,
        "matched_keywords": _matched_signal_keywords(text),
        "intent": intent,
    }


# --------------------------------------------------------------------------- #
# Chain-of-Empathy prompt (internal reasoning stays hidden from the user)
# --------------------------------------------------------------------------- #
def build_prompt(
    user_message: str,
    strategy: dict,
    schedule_context: Optional[dict] = None,
    user_profile: Optional[dict] = None,
    solution_context: Optional[dict] = None,
) -> str:
    strategy_name = strategy.get("strategy", "affective") if isinstance(strategy, dict) else str(strategy)
    rules = load_rules()
    strat_desc = rules["strategy_descriptions"].get(strategy_name, "")

    sched_json = json.dumps(schedule_context or {}, ensure_ascii=False)
    profile_json = json.dumps(user_profile or {}, ensure_ascii=False)
    solution_json = json.dumps(solution_context or {}, ensure_ascii=False)

    return (
        "너는 생활 밀착형 AI 일정 비서야. 아래 절차로 **내부적으로만** 추론하고, "
        "추론 과정은 최종 답변에 절대 노출하지 마.\n"
        "1. 사용자의 감정을 추론한다.\n"
        "2. 감정의 원인을 추론한다.\n"
        "3. 사용자의 의도를 추론한다.\n"
        f"4. 선택된 공감 전략에 맞게 응답한다. (전략: {strategy_name} — {strat_desc})\n"
        "5. 선택된 해결책 category와 solution_type을 자연스럽게 반영한다.\n"
        "6. 일정 정보가 있으면 빈 시간, 휴식, 준비 행동, 우선순위 정리, 일정 조정 후보를 활용한다.\n"
        "7. 사용자의 일정을 자동으로 변경하지 않는다.\n"
        "8. 실행성 제안은 반드시 사용자에게 확인을 요청한다.\n"
        "9. 내부 추론 과정은 최종 답변에 노출하지 않는다.\n\n"
        "출력 규칙: 감정을 먼저 인정하고, 3~5문장으로 자연스럽게. "
        "의학적 진단·치료·상담사처럼 단정하지 말 것. "
        "'나도 그런 적 있어'처럼 실제 경험이 있는 것처럼 말하지 말 것. "
        "'추가할까요?', '정리해볼까요?', '이 시간으로 옮겨볼까요?'처럼 확인을 받는 표현으로 끝낼 것.\n\n"
        f"[사용자 메시지]\n{user_message}\n\n"
        f"[일정 정보]\n{sched_json}\n\n"
        f"[사용자 프로필]\n{profile_json}\n\n"
        f"[선택된 해결책]\n{solution_json}\n"
    )


# --------------------------------------------------------------------------- #
# Rule-based fallback answer (used whenever the LLM is unavailable/unsafe)
# --------------------------------------------------------------------------- #
_STRATEGY_OPENING = {
    "affective": "지금 많이 지치고 힘든 마음이 느껴져요.",
    "cognitive": "상황을 함께 차근히 정리해볼게요.",
    "sharing": "이야기를 편하게 들려주셔서 좋아요. 그런 마음이 들 수 있어요.",
    "mixed_affective_cognitive": "일이 많아 막막하게 느껴지는 마음이 이해돼요.",
    "direct_task": "요청하신 내용을 도와드릴게요.",
    "fallback_llm_classification": "지금 마음이 어떤지 좀 더 살펴볼게요.",
}

_CATEGORY_CONFIRM = {
    "immediate_recovery": "지금 잠깐 회복할 수 있는 짧은 방법부터 함께 해볼까요?",
    "schedule_support": "일정을 미루기보다 준비 시간을 확보하는 쪽으로 도와드릴까요?",
    "task_structuring": "바로 일정을 미루기보다 할 일을 작게 나누는 방식부터 정리해볼까요?",
    "environment_shift": "잠깐 기분을 환기할 수 있는 방법을 추천해드릴까요?",
    "schedule_adjustment": "조정 가능한 일정의 후보 시간을 함께 살펴보고, 옮길지 정해볼까요?",
    "safety": "혼자 감당하기 어렵다면 신뢰할 수 있는 사람이나 전문가와 이야기 나누는 것을 권해요. 도움받을 수 있는 곳을 함께 찾아볼까요?",
}


def _fallback_answer(strategy_name: str, solution_context: Optional[dict]) -> str:
    opening = _STRATEGY_OPENING.get(strategy_name, _STRATEGY_OPENING["fallback_llm_classification"])
    sc = solution_context or {}
    category = sc.get("category")
    solutions = sc.get("solutions") or []

    middle = ""
    if solutions:
        first = solutions[0]
        title = first.get("title")
        if title:
            middle = f" {title} 방법이 도움이 될 수 있어요."

    confirm = _CATEGORY_CONFIRM.get(category, "괜찮으시면 함께 정리해볼까요?")

    answer = f"{opening}{middle} {confirm}"
    # Safety net: guarantee the returned text is clean.
    if not is_safe_answer(answer):
        return "지금 마음이 많이 힘드신 것 같아요. 무리하지 않으셔도 괜찮아요. 함께 천천히 정리해볼까요?"
    return answer


def generate_empathy_response(
    user_message: str,
    strategy: dict,
    emotion_result: Optional[dict] = None,
    solution_context: Optional[dict] = None,
    schedule_context: Optional[dict] = None,
    user_profile: Optional[dict] = None,
) -> dict:
    """Produce the final assistant answer.

    Tries the LLM (Chain-of-Empathy prompt); on None / failure / forbidden
    wording, falls back to the rule-based template. Returns
    {"answer", "used_llm"}.
    """
    strategy_name = strategy.get("strategy", "affective") if isinstance(strategy, dict) else str(strategy)

    # Safety category: force the fixed safe answer, bypass the LLM entirely.
    if (solution_context or {}).get("category") == "safety":
        return {"answer": _fallback_answer("affective", solution_context), "used_llm": False}

    llm_draft = None
    try:
        prompt = build_prompt(
            user_message=user_message,
            strategy=strategy,
            schedule_context=schedule_context,
            user_profile=user_profile,
            solution_context=solution_context,
        )
        base_system = (
            "너는 생활 밀착형 AI 일정 비서야. 의학적 진단을 하지 말고, "
            "감정을 먼저 인정한 뒤 3~5문장으로 부드럽게 답해. "
            "실제 경험이 있는 것처럼 말하지 말고, 실행성 제안은 사용자 확인을 받아."
        )
        # 사용자 스타일(말투/길이/알림강도)이 있으면 프롬프트에 반영.
        from backend.services import assistant_style_service as style
        system = style.styled_system(base_system, user_profile) if user_profile else base_system
        llm_draft = llm_service.generate(prompt, system=system)
    except Exception:
        llm_draft = None

    if llm_draft and is_safe_answer(llm_draft):
        return {"answer": llm_draft, "used_llm": True}

    return {"answer": _fallback_answer(strategy_name, solution_context), "used_llm": False}
