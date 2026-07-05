"""Build the final TTS-ready sentence for a rule-based intent (no LLM).

Pipeline, purely JSON + string rules:

    response_templates.json[intent][assistant_tone]   -> base sentence(s)
    + personalization_rules.json (nudge_strength)      -> optional nudge sentence
    + personalization_rules.json (response_length)     -> optional detail suffix
    -> truncate to the length's max sentence count
    -> tone_rules.json[assistant_tone]                 -> tone post-process
    -> global TTS normalization (strip emoji/markdown, collapse whitespace)

Design goals (mirrors schedule_parser.py's `_build_tts_text` policy):
  - never raises: any failure degrades to a safe, generic sentence instead of 500.
  - slot values (title/date/time/place/...) are inserted verbatim, never altered
    by tone/length/nudge rules — only the surrounding phrasing changes.
  - unknown intent / unknown tone / missing slot all fall back safely.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"

_SAFE_FALLBACK = "요청하신 내용을 확인했습니다."

# intent -> personalization category (nudge/detailed-suffix bucket)
_INTENT_CATEGORY: Dict[str, str] = {
    "schedule_create_success": "schedule",
    # missing-slot prompts map to "fallback" (not "schedule") so a deadline/
    # reminder nudge is never appended before we even have a date/time/title.
    "schedule_missing_date": "fallback",
    "schedule_missing_time": "fallback",
    "schedule_missing_title": "fallback",
    "todo_create_success": "todo",
    "todo_missing_title": "fallback",
    "reservation_recommend": "reservation",
    "reservation_message_created": "reservation",
    "departure_alert": "departure",
    "briefing_today": "briefing",
    "briefing_empty": "briefing",
    "emotion_overload": "emotion",
    "emotion_tired": "emotion",
    "emotion_anxious": "emotion",
    "fallback_understood": "fallback",
    "fallback_unknown": "fallback",
}

_SLOT_RE = re.compile(r"\{(\w+)\}")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?다요])\s+")
_MD_STRIP_RE = re.compile(r"[*_`#>~]|^\s*\d+[.)]\s*", re.MULTILINE)
_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]+"
)
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([.,!?])")
_MULTI_SPACE_RE = re.compile(r"\s{2,}")


# --------------------------------------------------------------------------- #
# JSON loaders (cached; path is anchored to this file, stable regardless of
# whether the process was started by uvicorn or pytest)
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _load_json(name: str) -> dict:
    try:
        with open(_DATA_DIR / name, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _templates() -> dict:
    return _load_json("response_templates.json").get("intents", {})


def _default_tone() -> str:
    return _load_json("response_templates.json").get("default_tone", "friendly")


def _tone_rules() -> dict:
    return _load_json("tone_rules.json").get("tones", {})


def _personalization() -> dict:
    return _load_json("personalization_rules.json")


def load_tone_profiles() -> dict:
    """{tone_code: {display_name, description, ...}} — reused by
    user_preference_service.get_options() for the Flutter settings screen."""
    return _load_json("tone_profiles.json").get("tones", {})


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _safe_format(template: str, slots: Optional[dict]) -> str:
    """Fill {slot} placeholders; missing/None slots become "" (never KeyError)."""
    slots = slots or {}

    def _sub(m: "re.Match[str]") -> str:
        val = slots.get(m.group(1))
        return "" if val is None else str(val)

    text = _SLOT_RE.sub(_sub, template or "")
    text = _MULTI_SPACE_RE.sub(" ", text).strip()
    text = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)
    return text


def _split_sentences(text: str) -> List[str]:
    if not text:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]


def _select_template(intent: str, tone: str) -> str:
    templates = _templates()
    intent_map = templates.get(intent)
    if not intent_map:
        intent_map = templates.get("fallback_unknown", {})
    default_tone = _default_tone()
    template = (
        intent_map.get(tone)
        or intent_map.get(default_tone)
        or next(iter(intent_map.values()), None)
    )
    return template or _SAFE_FALLBACK


def _apply_tone_rules(text: str, tone: str) -> str:
    rule = _tone_rules().get(tone, {})
    for phrase in rule.get("remove_phrases", []):
        text = text.replace(phrase, "")
    for pair in rule.get("replace", []):
        find, replace = pair.get("find"), pair.get("replace")
        if find:
            text = text.replace(find, replace or "")
    return text


def _tone_max_sentences_cap(tone: str) -> Optional[int]:
    cap = _tone_rules().get(tone, {}).get("max_sentences_cap")
    return cap if isinstance(cap, int) and cap > 0 else None


def _normalize_tts(text: str) -> str:
    """Strip markdown/emoji leftovers and collapse whitespace — this is a
    sentence meant to be read aloud, never rendered as rich text."""
    text = _EMOJI_RE.sub("", text)
    text = _MD_STRIP_RE.sub("", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)
    return text.strip()


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #
def build_tts_response(
    intent: str,
    slots: Optional[dict] = None,
    preferences: Optional[dict] = None,
    emotion: Optional[str] = None,
    context_type: Optional[str] = None,
) -> str:
    """Return a TTS-ready sentence for `intent`, styled per `preferences`.

    `preferences` is the {"assistant_tone", "response_length", "nudge_strength"}
    dict from user_preference_service.get_user_preferences(); any missing/
    invalid key falls back to its default. Never raises — any internal error
    degrades to a short, safe sentence instead of propagating.
    """
    try:
        from backend.services.user_preference_service import (
            DEFAULT_PREFERENCES,
            normalize_preference_value,
        )

        preferences = preferences or {}
        tone = (
            normalize_preference_value("assistant_tone", preferences.get("assistant_tone"))
            or DEFAULT_PREFERENCES["assistant_tone"]
        )
        length = (
            normalize_preference_value("response_length", preferences.get("response_length"))
            or DEFAULT_PREFERENCES["response_length"]
        )
        nudge = (
            normalize_preference_value("nudge_strength", preferences.get("nudge_strength"))
            or DEFAULT_PREFERENCES["nudge_strength"]
        )

        resolved_intent = intent if intent in _templates() else "fallback_unknown"
        template = _select_template(resolved_intent, tone)
        merged_slots = dict(slots or {})
        if emotion is not None:
            merged_slots.setdefault("emotion", emotion)
        base_text = _safe_format(template, merged_slots)

        sentences = _split_sentences(base_text) or [_SAFE_FALLBACK]
        category = context_type or _INTENT_CATEGORY.get(resolved_intent, "fallback")

        prule = _personalization()
        nudge_categories = (
            prule.get("nudge_strength", {}).get(nudge, {}).get("apply_to_categories", [])
        )
        if category in nudge_categories:
            nudge_sentence = prule.get("nudge_sentence_by_category", {}).get(category, {}).get(nudge)
            if nudge_sentence:
                sentences.append(nudge_sentence)

        if length == "detailed":
            suffix = prule.get("detailed_suffix_by_category", {}).get(category)
            if suffix and suffix not in sentences:
                sentences.append(suffix)

        max_sentences = prule.get("response_length", {}).get(length, {}).get("max_sentences", 2)
        sentences = sentences[:max_sentences]

        cap = _tone_max_sentences_cap(tone)
        if cap is not None:
            sentences = sentences[:cap]

        text = " ".join(sentences)
        text = _apply_tone_rules(text, tone)
        text = _normalize_tts(text)
        return text or _SAFE_FALLBACK
    except Exception:
        return _SAFE_FALLBACK
