"""Rule-based intent router for the unified voice entry point.

Classifies a raw STT utterance into ONE of 7 voice-flow intents:

    reservation_recommendation | emotion_schedule_coaching | daily_briefing |
    schedule_query | reminder_setting | schedule_create | fallback_chat

This is intentionally a SEPARATE taxonomy from ``intent_classifier.py`` (used
only by ``/chat/respond``): that classifier's ``reservation_recommend`` means
"when should I book this appointment", while this router's
``reservation_recommendation`` means "find me a place/store" (place
discovery). Reusing one name for both would blur two different features, so
this module owns its own rule file (``rules/voice_intent_rules.json``) and
never touches ``chat_intent_rules.json``.

Priority is a CASCADE (first matching intent wins), not a max-score
comparison — this mirrors the spec's explicit ordering requirement:
"가게 추천해줘" contains a recommendation keyword so it must never fall
through to schedule_create; "오늘 진짜 피곤하다 오늘 일정 뭐야" contains a
schedule_query phrase but the emotion word upgrades it to
emotion_schedule_coaching.

Never raises: unexpected errors degrade to fallback_chat.
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

_RULES_PATH = Path(__file__).resolve().parents[1] / "rules" / "voice_intent_rules.json"

_logger = logging.getLogger("voice_intent_router")

INTENTS = (
    "reservation_recommendation",
    "emotion_schedule_coaching",
    "daily_briefing",
    "schedule_query",
    "reminder_setting",
    "schedule_create",
    "fallback_chat",
)

_HOURS_RE = re.compile(r"(\d+)\s*시간\s*전")
_MINUTES_RE = re.compile(r"(\d+)\s*분\s*전")


@lru_cache(maxsize=1)
def _rules() -> dict:
    with open(_RULES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _matched(text: str, keywords: Optional[List[str]]) -> List[str]:
    return [kw for kw in (keywords or []) if kw in text]


def parse_reminder_minutes(text: str) -> Optional[int]:
    """Extract a spoken '1시간 전' / '30분 전' offset as minutes. None if absent."""
    text = text or ""
    m = _HOURS_RE.search(text)
    if m:
        return int(m.group(1)) * 60
    m = _MINUTES_RE.search(text)
    if m:
        return int(m.group(1))
    return None


def _is_reminder_decline(text: str, rules: dict) -> bool:
    return any(kw in text for kw in rules.get("reminder_setting", {}).get("decline", []))


def _schedule_create_signal(text: str) -> bool:
    """A concrete date/time in the utterance is a strong schedule_create signal
    even without an explicit '추가해줘' verb. Reuses the existing, tested
    schedule_parser instead of duplicating its date/time regexes."""
    try:
        from backend.database.schema.schedule_schema import ScheduleParseRequest
        from backend.services.schedule_parser import parse_schedule

        data = parse_schedule(ScheduleParseRequest(input=text))
        return bool(data.slots.date or data.slots.start_time)
    except Exception:
        return False


def _result(intent: str, matched_keywords: Dict[str, List[str]], **extra) -> dict:
    out = {"intent": intent, "matched_keywords": matched_keywords}
    out.update(extra)
    _logger.info(
        "[VOICE INTENT] intent=%s matched_keywords=%s extra=%s",
        intent, matched_keywords, {k: v for k, v in extra.items()},
    )
    return out


def select_voice_intent(text: str, context: Optional[dict] = None) -> dict:
    """Classify one utterance. `context` is the client-echoed
    `last_action_context` from the previous turn (or None/{})."""
    text = text or ""
    context = context or {}
    matched_keywords: Dict[str, List[str]] = {}

    try:
        rules = _rules()

        # 1. reservation_recommendation — place/store discovery, checked FIRST.
        cfg = rules["reservation_recommendation"]
        hits = _matched(text, cfg["strong"]) + _matched(text, cfg["weak"])
        if hits:
            matched_keywords["reservation_recommendation"] = hits
            return _result("reservation_recommendation", matched_keywords)

        # 2. emotion_schedule_coaching — requires BOTH groups.
        cfg = rules["emotion_schedule_coaching"]
        emo_hits = _matched(text, cfg["emotion_keywords"])
        sched_hits = _matched(text, cfg["schedule_ref_keywords"])
        if emo_hits and sched_hits:
            matched_keywords["emotion_schedule_coaching"] = emo_hits + sched_hits
            return _result("emotion_schedule_coaching", matched_keywords)

        # 3. daily_briefing
        cfg = rules["daily_briefing"]
        hits = _matched(text, cfg["strong"])
        if hits:
            matched_keywords["daily_briefing"] = hits
            return _result("daily_briefing", matched_keywords)

        # 4. schedule_query (strong-only; see rules file comment)
        cfg = rules["schedule_query"]
        hits = _matched(text, cfg["strong"])
        if hits:
            matched_keywords["schedule_query"] = hits
            return _result("schedule_query", matched_keywords)

        # 5. reminder_setting — context-gated.
        cfg = rules["reminder_setting"]
        if context.get("type") == cfg.get("requires_context_type"):
            hits = _matched(text, cfg["strong"]) + _matched(text, cfg["weak"])
            decline = _is_reminder_decline(text, rules)
            minutes = parse_reminder_minutes(text)
            if hits or decline or minutes is not None:
                matched_keywords["reminder_setting"] = hits
                return _result(
                    "reminder_setting", matched_keywords,
                    reminder_minutes=minutes, reminder_decline=decline,
                )

        # 6. schedule_create — explicit verb OR a concrete date/time signal.
        cfg = rules["schedule_create"]
        hits = _matched(text, cfg["strong"]) + _matched(text, cfg["weak"])
        if hits or _schedule_create_signal(text):
            matched_keywords["schedule_create"] = hits
            return _result("schedule_create", matched_keywords)

        # 7. fallback_chat
        return _result("fallback_chat", matched_keywords)
    except Exception:
        _logger.exception("voice intent classification failed for text=%r", text)
        return _result("fallback_chat", {})
