"""Rule-based emotion analysis + life-coaching (with optional LLM coaching).

A life-coaching aid, NOT a medical diagnosis. Wording stays suggestive.
- emotion / sentiment / emotion_score / risk_level: ALWAYS rule-based (safety + determinism).
- coaching sentence: LLM when a key is configured, else template.
- Crisis signals always use a fixed, safe message (LLM is bypassed).
Never raises.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import List

from backend.database.schema.emotion_schema import (
    EmotionAnalyzeData,
    EmotionAnalyzeRequest,
)
from backend.services import llm_service

_RULES_DIR = Path(__file__).resolve().parents[1] / "rules"
_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "emotion_coaching_prompt.txt"
_EMOTION_ORDER = ["fatigue", "anxiety", "sadness", "anger", "stress", "positive"]


@lru_cache(maxsize=1)
def _rules() -> dict:
    with open(_RULES_DIR / "emotion_rules.json", encoding="utf-8") as f:
        return json.load(f)


def _gerund(label: str) -> str:
    if label.endswith("하기"):
        return label[:-2] + "하는 것"
    if label.endswith("기"):
        return label[:-1] + "는 것"
    return label


def _stem_go(label: str) -> str:
    if label.endswith("하기"):
        return label[:-2] + "하고"
    if label.endswith("기"):
        return label[:-1] + "고"
    return label + "하고"


def _detect_emotion(text: str) -> tuple[str, int]:
    rules = _rules()["emotions"]
    best_emotion, best_count = "neutral", 0
    for name in _EMOTION_ORDER:
        count = sum(1 for kw in rules[name]["keywords"] if kw in text)
        if count > best_count:
            best_emotion, best_count = name, count
    return best_emotion, best_count


def _build_actions(emotion: str, ctx) -> List[str]:
    rules = _rules()
    base = list(rules["coaching_actions"].get(emotion, []))
    context_actions: List[str] = []
    if emotion == "fatigue":
        if (ctx.schedule_count or 0) >= 4:
            context_actions.append(rules["context_actions"]["busy_evening"])
        if ctx.sleep_hours is not None and ctx.sleep_hours < 6:
            context_actions.append(rules["context_actions"]["sleep_low"])
    ordered, seen = [], set()
    for a in context_actions + base:
        if a not in seen:
            ordered.append(a)
            seen.add(a)
    return ordered


def _template_coaching(opening: str, actions: List[str]) -> str:
    if len(actions) >= 2:
        body = f"{_stem_go(actions[0])} {_gerund(actions[1])}을 추천합니다"
    elif actions:
        body = f"{_gerund(actions[0])}을 추천합니다"
    else:
        body = "현재 상태를 가볍게 살펴보는 것을 추천합니다"
    return f"{opening} 오늘은 {body}."


def _build_prompt(req: EmotionAnalyzeRequest) -> str:
    ctx = req.recent_context
    try:
        template = _PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        template = "감정 기록을 보고 1~2문장의 부드러운 생활 코칭을 작성하세요. 기록:{input}"
    return template.format(
        input=req.input or "",
        sleep_hours=ctx.sleep_hours if ctx.sleep_hours is not None else "미상",
        schedule_count=ctx.schedule_count if ctx.schedule_count is not None else "미상",
        todo_done_rate=ctx.todo_done_rate if ctx.todo_done_rate is not None else "미상",
    )


def analyze_emotion(req: EmotionAnalyzeRequest) -> EmotionAnalyzeData:
    rules = _rules()
    text = req.input or ""
    ctx = req.recent_context

    # --- crisis check (always fixed, safe; LLM bypassed) ---
    if any(k in text for k in rules.get("crisis_keywords", [])):
        return EmotionAnalyzeData(
            sentiment="negative",
            emotion="sadness",
            emotion_score=0.9,
            risk_level="high",
            coaching=(
                "많이 힘든 마음이 느껴집니다. 혼자 감당하기 어렵다면 신뢰할 수 있는 "
                "사람이나 전문가와 이야기를 나누는 것을 권합니다."
            ),
            recommended_actions=[
                "신뢰할 수 있는 사람과 이야기하기",
                "전문가의 도움 구하기",
                "무리한 일정 미루기",
            ],
        )

    emotion, match_count = _detect_emotion(text)

    if emotion == "neutral":
        meta = rules["neutral"]
        sentiment, opening, score = meta["sentiment"], meta["opening"], 0.5
    else:
        meta = rules["emotions"][emotion]
        sentiment, opening = meta["sentiment"], meta["opening"]
        has_intensifier = any(w in text for w in rules.get("intensifiers", []))
        reinforced = (
            (emotion == "fatigue" and ctx.sleep_hours is not None and ctx.sleep_hours < 6)
            or (emotion in ("fatigue", "stress", "anxiety") and (ctx.schedule_count or 0) >= 4)
            or (ctx.todo_done_rate is not None and ctx.todo_done_rate < 30)
        )
        score = 0.6 + 0.12 * match_count + (0.1 if has_intensifier else 0) + (0.06 if reinforced else 0)
        score = round(min(0.95, score), 2)

    has_intensifier = any(w in text for w in rules.get("intensifiers", []))
    poor_context = (
        (ctx.sleep_hours is not None and ctx.sleep_hours < 5)
        or (ctx.todo_done_rate is not None and ctx.todo_done_rate < 30)
        or (ctx.schedule_count or 0) >= 6
    )
    risk_level = "medium" if (emotion in ("sadness", "anger") and (has_intensifier or poor_context)) else "low"

    actions = _build_actions(emotion, ctx)
    template_coaching = _template_coaching(opening, actions)

    # --- coaching (LLM, optional; non-diagnostic) ---
    llm_coaching = None
    try:
        llm_coaching = llm_service.generate(
            _build_prompt(req),
            system=(
                "너는 생활 코칭 보조 비서야. 의학적 진단을 하지 말고 '보입니다', '추천합니다'처럼 "
                "부드럽게 1~2문장으로만 코칭해. 단정적 진단 표현은 금지."
            ),
        )
    except Exception:
        llm_coaching = None
    coaching = llm_coaching if llm_coaching else template_coaching

    return EmotionAnalyzeData(
        sentiment=sentiment,
        emotion=emotion,
        emotion_score=score,
        risk_level=risk_level,
        coaching=coaching,
        recommended_actions=actions,
    )
