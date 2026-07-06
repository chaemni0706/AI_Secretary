"""Clarification message builder for incomplete schedule parses.

Given the (possibly missing) title/date/time/location and the category, produce a
natural Korean prompt using the category-aware question bank
(backend/rules/schedule_clarification_questions.json), plus a shorter
``tts_text`` and a coarse ``status`` (``success`` | ``needs_clarification``).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from backend.services import schedule_rule_loader as rules

STATUS_SUCCESS = "success"
STATUS_NEEDS_CLARIFICATION = "needs_clarification"

_FIELD_ORDER = ("date", "time", "location")


def _question_for(category: str, field: str) -> Optional[str]:
    banks = rules.load_clarification_questions()
    cat_bank = banks.get(category, {})
    if field in cat_bank and cat_bank[field] is not None:
        return cat_bank[field]
    default = banks.get("default", {})
    return default.get(field)


def build_clarification(
    *,
    category: str,
    title: Optional[str],
    missing_fields: List[str],
    date_text: Optional[str] = None,
    time_text: Optional[str] = None,
    preferences: Optional[dict] = None,
) -> Dict:
    """Return {status, clarification_message, tts_text}.

    When `preferences` is provided, the message/tts are phrased in the user's
    voice style via assistant_style_service (additive). Without preferences the
    original category-question-bank behaviour is preserved byte-for-byte.
    """
    banks = rules.load_clarification_questions()
    status = STATUS_SUCCESS if not missing_fields else STATUS_NEEDS_CLARIFICATION

    if preferences is not None:
        from backend.services import assistant_style_service as style
        profile = style.build_style_profile(preferences)
        message = style.build_clarification_text(title, missing_fields, profile)
        # tts is the same styled sentence, shortened if length!=long
        short_profile = dict(profile)
        if short_profile.get("length") == "long":
            short_profile["length"] = "medium"
        tts = style.build_clarification_text(title, missing_fields, short_profile)
        return {"status": status, "clarification_message": message, "tts_text": tts}

    # title missing dominates — ask what the schedule even is.
    if "title" in missing_fields or not title:
        q = _question_for(category, "title") or "어떤 일정으로 등록할까요?"
        return {"status": status, "clarification_message": q, "tts_text": q}

    field_missing = [f for f in _FIELD_ORDER if f in missing_fields]

    if not field_missing:
        when = " ".join(x for x in (date_text, time_text) if x)
        msg = f"{title} 일정을 {when}에 등록할게요." if when else f"{title} 일정을 등록할게요."
        return {"status": status, "clarification_message": msg.replace("  ", " "),
                "tts_text": f"{title} 일정을 등록할게요."}

    # date+time+location all missing -> combined category template if available.
    cat_bank = banks.get(category, {})
    if set(field_missing) == {"date", "time", "location"} and cat_bank.get("date_time_location"):
        msg = cat_bank["date_time_location"].format(title=title)
        return {"status": status, "clarification_message": msg, "tts_text": msg}

    parts = [q for q in (_question_for(category, f) for f in field_missing) if q]
    message = " ".join(parts) if parts else "부족한 정보를 알려주세요."
    tts = parts[0] if parts else message
    return {"status": status, "clarification_message": message, "tts_text": tts}
