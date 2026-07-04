"""Preference-aware emotion coaching (rule-based, non-diagnostic).

Wraps the existing emotion_analyzer (rule-based emotion + template coaching) and
shapes the response by the user's stored preferences:
  * preferred_tone / coaching_style -> message wording,
  * stress_triggers present in the text -> reinforced, task-splitting actions,
  * rest_recommendation_enabled -> include/exclude a rest suggestion.

Coaching stays supportive and NON-diagnostic (never names conditions). Never
raises; no external calls (LLM is not required — analyzer falls back to template
without an API key).
"""

from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from backend.database.schema.emotion_schema import EmotionAnalyzeRequest, RecentContext
from backend.database.schema.personalization_schema import (
    EmotionCoachData,
    EmotionCoachRequest,
)
from backend.services import preference_service
from backend.services.emotion_analyzer import analyze_emotion

_REST_ACTIONS = ("10분 휴식하기", "5분 산책하기", "잠깐 쉬기", "휴식하기")
_TONE_PREFIX = {
    "gentle": "괜찮아요. ",
    "warm": "많이 애쓰고 있어요. ",
    "neutral": "",
}
_STYLE_TAIL = {
    "supportive": " 천천히 함께 해봐요.",
    "coaching": " 하나씩 짚어가며 해봐요.",
    "direct": " 지금 할 수 있는 것부터 바로 시작해봐요.",
}
_STRESS_ACTIONS = ["할 일을 작게 나누기", "마감 전 알림 설정하기"]


def _is_rest_action(action: str) -> bool:
    return "휴식" in action or "쉬" in action or "산책" in action


def coach(db: Session, req: EmotionCoachRequest) -> EmotionCoachData:
    eff = preference_service.get_effective_user_preference(db, req.user_id)
    pref, meta = eff["preference"], eff["meta"]

    text = req.text or ""
    analysis = analyze_emotion(EmotionAnalyzeRequest(
        input=text,
        recent_context=RecentContext(
            sleep_hours=req.sleep_hours,
            schedule_count=req.schedule_count,
            todo_done_rate=req.todo_done_rate,
        ),
    ))

    actions: List[str] = list(analysis.recommended_actions)
    used: List[str] = ["preferred_tone", "coaching_style"]

    # stress_triggers: reinforce when a trigger keyword appears in the text
    triggered = [t for t in pref.stress_triggers if t and t in text]
    if triggered:
        used.append("stress_triggers")
        for a in _STRESS_ACTIONS:
            if a not in actions:
                actions.append(a)

    # rest recommendation toggle
    used.append("rest_recommendation_enabled")
    if pref.rest_recommendation_enabled:
        if not any(_is_rest_action(a) for a in actions):
            actions.insert(0, "10분 휴식하기")
    else:
        actions = [a for a in actions if not _is_rest_action(a)]

    actions = actions[:4]

    # message wording from tone + coaching_style (non-diagnostic base)
    prefix = _TONE_PREFIX.get(pref.preferred_tone, "")
    tail = _STYLE_TAIL.get(pref.coaching_style, _STYLE_TAIL["supportive"])
    coaching_message = f"{prefix}{analysis.coaching}{tail}"

    if meta.personalization_applied:
        meta.reason = "선호 말투와 코칭 스타일, 스트레스 키워드를 반영했습니다."
    meta.used_preferences = used

    return EmotionCoachData(
        emotion=analysis.emotion,
        coaching_message=coaching_message,
        suggested_actions=actions,
        personalization=meta,
    )
