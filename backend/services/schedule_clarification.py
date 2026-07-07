"""Clarification message builder for incomplete schedule parses.

Given the (possibly missing) title/date/time/location and the category, produce a
natural Korean prompt using the category-aware question bank
(backend/rules/schedule_clarification_questions.json), plus a shorter
``tts_text`` and a coarse ``status`` (``success`` | ``needs_clarification``).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from backend.core.config import settings
from backend.services import llm_service
from backend.services import schedule_rule_loader as rules

STATUS_SUCCESS = "success"
STATUS_NEEDS_CLARIFICATION = "needs_clarification"

_FIELD_ORDER = ("date", "time", "location")

# 되묻기 문장 최대 길이(글자). 초과하면 LLM 결과를 버리고 템플릿으로 fallback.
_CLARIFY_MAX_LEN = 80
_FIELD_KOR = {"title": "무슨 일정인지", "date": "날짜", "time": "시간", "location": "장소"}
_TONE_HINT = {
    "formal": "정중한 존댓말",
    "friendly": "친근하고 부드러운 존댓말",
    "caring": "따뜻하고 배려하는 존댓말",
    "concise": "간결한 존댓말",
}


def _llm_clarification(
    title: Optional[str], missing_fields: List[str], profile: Dict[str, str]
) -> Optional[str]:
    """부족 정보를 되묻는 자연스러운 한 문장을 LLM으로 생성. 실패/길이초과 시 None
    → 호출부는 템플릿 fallback. 말투는 style profile 의 tone 을 반영한다."""
    need = [_FIELD_KOR[f] for f in ("title", "date", "time", "location") if f in missing_fields]
    if not need:
        return None
    tone = profile.get("tone", "friendly")
    prompt = (
        f"일정 제목: {title or '아직 모름'}\n"
        f"사용자가 빠뜨린 정보: {', '.join(need)}\n"
        f"말투: {_TONE_HINT.get(tone, '친근한 존댓말')}\n"
        "위 빠진 정보를 물어보는 자연스러운 한국어 문장을 딱 1개, 40자 이내로 만들어줘. "
        "따옴표나 설명 없이 문장만 출력해."
    )
    from backend.services import assistant_style_service as style
    system = style.styled_system(
        "너는 일정 비서야. 부족한 정보를 정중히 되묻는 한 문장만 출력해.", profile
    )
    text = llm_service.generate(prompt, system=system, max_tokens=80)
    if not text:
        return None
    text = text.strip().splitlines()[0].strip()
    if not text or len(text) > _CLARIFY_MAX_LEN:
        return None  # 비었거나 너무 길면 템플릿으로.
    return text


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

    # LLM 자연어 되묻기(옵션). 비활성/키없음/실패/길이초과 시 아래 기존 템플릿 로직으로
    # 그대로 fallthrough 하므로 기존 동작은 보존된다.
    if missing_fields and settings.ENABLE_LLM_CLARIFY and llm_service.is_enabled():
        try:
            from backend.services import assistant_style_service as style
            profile = style.build_style_profile(preferences or {})
            llm_msg = _llm_clarification(title, missing_fields, profile)
        except Exception:
            llm_msg = None
        if llm_msg:
            return {
                "status": status,
                "clarification_message": llm_msg,
                "tts_text": llm_msg,
            }

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
