"""Assistant response-style service (rule-based, no LLM).

Turns a user's stored voice/persona preference into a normalized *style profile*
and restyles / generates the sentences the assistant speaks:

  * build_style_profile   — normalize prefs into {tone, length, strength}
  * apply_response_style  — restyle an existing sentence (tone tweak + length)
  * build_clarification_text — ask for missing schedule info in the user's style
  * build_reminder_text   — phrase a reminder by reminder strength
  * reminder_offsets      — how many / how early reminders fire, by strength

Field-name / enum compatibility: the app historically stores
``assistant_tone`` (polite|friendly|concise|caring|professional),
``response_length`` (short|normal|detailed) and ``nudge_strength``
(low|medium|high). The product spec talks about ``assistant_tone``
(formal|friendly|caring|concise), ``response_length`` (short|medium|long) and
``reminder_strength`` (gentle|normal|strong). We KEEP the existing field names
and map BOTH vocabularies onto one canonical profile here, so nothing existing
breaks and either spelling works.

Never raises: unknown/missing values fall back to friendly / medium / normal.
"""

from __future__ import annotations

from typing import Dict, List, Optional

# canonical axes
TONES = ("formal", "friendly", "caring", "concise")
LENGTHS = ("short", "medium", "long")
STRENGTHS = ("gentle", "normal", "strong")

DEFAULT_TONE = "friendly"
DEFAULT_LENGTH = "medium"
DEFAULT_STRENGTH = "normal"

# existing-enum + spec-enum -> canonical
_TONE_MAP = {
    "formal": "formal", "polite": "formal", "professional": "formal",
    "friendly": "friendly", "neutral": "friendly",
    "caring": "caring", "warm": "caring", "gentle": "caring",
    "concise": "concise",
}
_LENGTH_MAP = {
    "short": "short",
    "medium": "medium", "normal": "medium",
    "long": "long", "detailed": "long",
}
_STRENGTH_MAP = {
    "gentle": "gentle", "low": "gentle",
    "normal": "normal", "medium": "normal",
    "strong": "strong", "high": "strong",
}

# canonical strength -> legacy nudge_strength (for tts_response_builder reuse)
STRENGTH_TO_NUDGE = {"gentle": "low", "normal": "medium", "strong": "high"}


def _norm(value: Optional[str], mapping: Dict[str, str], default: str) -> str:
    if not isinstance(value, str):
        return default
    return mapping.get(value.strip().lower(), default)


def build_style_profile(preferences: Optional[dict]) -> Dict[str, str]:
    """Normalize a raw preferences dict into {tone, length, strength}.

    Accepts either the stored field names (assistant_tone/response_length/
    nudge_strength) or the spec names (…/reminder_strength). None -> defaults.
    """
    prefs = preferences or {}
    strength_raw = prefs.get("reminder_strength")
    if strength_raw is None:
        strength_raw = prefs.get("nudge_strength")
    return {
        "tone": _norm(prefs.get("assistant_tone"), _TONE_MAP, DEFAULT_TONE),
        "length": _norm(prefs.get("response_length"), _LENGTH_MAP, DEFAULT_LENGTH),
        "strength": _norm(strength_raw, _STRENGTH_MAP, DEFAULT_STRENGTH),
    }


# --------------------------------------------------------------------------- #
# LLM 프롬프트용 스타일 지시문
# --------------------------------------------------------------------------- #
_TONE_DESC = {
    "formal": "정중하고 격식 있는",
    "friendly": "친근하고 부드러운",
    "caring": "따뜻하고 공감하는",
    "concise": "군더더기 없이 간결한",
}
_LENGTH_DESC = {
    "short": "짧게 1~2문장으로",
    "medium": "2~3문장 정도로",
    "long": "필요하면 충분히 자세하게",
}
_STRENGTH_DESC = {
    "gentle": "재촉이나 알림은 부드럽게 권하듯",
    "normal": "알림은 적당한 정도로",
    "strong": "중요한 점은 분명히 강조하고 확실히 리마인드하며",
}


def _as_profile(preferences_or_profile: Optional[dict]) -> Dict[str, str]:
    """이미 정규화된 profile({tone,length,strength})이면 그대로, 아니면 raw
    prefs 를 build_style_profile 로 정규화해 반환."""
    p = preferences_or_profile or {}
    if set(p) <= {"tone", "length", "strength"} and p:
        return {
            "tone": p.get("tone", DEFAULT_TONE),
            "length": p.get("length", DEFAULT_LENGTH),
            "strength": p.get("strength", DEFAULT_STRENGTH),
        }
    return build_style_profile(preferences_or_profile)


def style_instruction(preferences_or_profile: Optional[dict]) -> str:
    """사용자 스타일(tone/length/strength)을 LLM 프롬프트에 넣을 한국어 지시문으로.

    raw prefs(assistant_tone/response_length/reminder_strength) 또는 이미 만든
    profile 둘 다 받는다. 예) "[응답 스타일] 사용자는 짧게 1~2문장으로 친근하고
    부드러운 말투의 응답을 선호합니다. ..."
    """
    prof = _as_profile(preferences_or_profile)
    tone = _TONE_DESC.get(prof["tone"], _TONE_DESC[DEFAULT_TONE])
    length = _LENGTH_DESC.get(prof["length"], _LENGTH_DESC[DEFAULT_LENGTH])
    strength = _STRENGTH_DESC.get(prof["strength"], _STRENGTH_DESC[DEFAULT_STRENGTH])
    return (
        f"[응답 스타일] 사용자는 {length} {tone} 말투의 응답을 선호합니다. "
        f"{strength} 답하세요."
    )


def styled_system(base_system: Optional[str], preferences_or_profile: Optional[dict]) -> str:
    """기존 system 프롬프트 끝에 스타일 지시문을 덧붙인다. base 가 비면 지시문만."""
    base = (base_system or "").strip()
    hint = style_instruction(preferences_or_profile)
    return f"{base}\n{hint}" if base else hint


# --------------------------------------------------------------------------- #
# sentence helpers
# --------------------------------------------------------------------------- #
_FIELD_LABEL = {"date": "날짜", "time": "시간", "location": "장소"}
_FIELD_ORDER = ("date", "time", "location")


def _split_sentences(text: str) -> List[str]:
    import re
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [p.strip() for p in parts if p.strip()]


def _title_question(tone: str) -> str:
    return {
        "formal": "어떤 일정을 등록할까요? 내용을 알려주세요.",
        "friendly": "어떤 일정으로 등록할까요?",
        "caring": "어떤 일정인지 편하게 알려주시면 제가 챙겨드릴게요.",
        "concise": "무슨 일정인가요?",
    }.get(tone, "어떤 일정으로 등록할까요?")


def _lead(tone: str, title: str) -> str:
    return {
        "formal": f"{title} 일정을 등록하겠습니다.",
        "friendly": f"좋아요, {title} 일정으로 잡아둘게요.",
        "caring": f"좋아요, {title} 일정은 제가 챙겨드릴게요.",
        "concise": f"{title} 등록할게요.",
    }.get(tone, f"{title} 일정으로 잡아둘게요.")


def _has_batchim(word: str) -> bool:
    """마지막 글자에 받침이 있는지(한글 음절 기준)."""
    if not word:
        return False
    ch = word[-1]
    if not ("가" <= ch <= "힣"):
        return False
    return (ord(ch) - 0xAC00) % 28 != 0


def _join_with_wa_gwa(labels: List[str]) -> str:
    """라벨들을 자연스러운 한국어로 잇는다. 마지막 연결은 받침에 따라 '와/과'.
    예: ['날짜','시간'] -> '날짜와 시간', ['시간','장소'] -> '시간과 장소'."""
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    head = ", ".join(labels[:-1])
    connector = "과 " if _has_batchim(labels[-2]) else "와 "
    return f"{head}{connector}{labels[-1]}"


def _eul_reul(word: str) -> str:
    """받침에 맞는 목적격 조사('을'/'를')."""
    return "을" if _has_batchim(word) else "를"


def _neun_eun(word: str) -> str:
    """받침에 맞는 보조사('은'/'는')."""
    return "은" if _has_batchim(word) else "는"


def _ask(tone: str, fields: List[str]) -> str:
    labels = [_FIELD_LABEL[f] for f in fields if f in _FIELD_LABEL]
    if not labels:
        return ""
    joined = _join_with_wa_gwa(labels)
    obj = _eul_reul(joined)  # 조사는 마지막 글자 받침 기준.
    # natural single-time phrasing for friendly/concise
    if tone == "formal":
        return f"{joined}{obj} 알려주세요."
    if tone == "friendly":
        if fields == ["time"]:
            return "시간은 언제로 할까요?"
        if fields == ["date"]:
            return "날짜는 언제로 할까요?"
        return f"{joined}{_neun_eun(joined)} 어떻게 할까요?"
    if tone == "caring":
        return f"편하신 {joined}{obj} 알려주시면 이어서 등록해드릴게요."
    # concise
    return f"{joined}{obj} 알려주세요."


def _tail(tone: str) -> str:
    return {
        "formal": "확인 후 등록해 드리겠습니다.",
        "friendly": "알려주시면 바로 등록해둘게요.",
        "caring": "무리하지 않으셔도 괜찮아요, 천천히 알려주세요.",
        "concise": "",
    }.get(tone, "")


def build_clarification_text(
    title: Optional[str], missing_fields: List[str], style_profile: Dict[str, str]
) -> str:
    """Build a style-aware clarification prompt for missing schedule info."""
    tone = style_profile.get("tone", DEFAULT_TONE)
    length = style_profile.get("length", DEFAULT_LENGTH)

    if "title" in missing_fields or not title:
        return _title_question(tone)

    fields = [f for f in _FIELD_ORDER if f in missing_fields]
    if not fields:
        # everything present -> a short confirmation
        return {
            "formal": f"{title} 일정을 등록하겠습니다.",
            "friendly": f"좋아요, {title} 일정으로 등록해둘게요.",
            "caring": f"{title} 일정은 제가 잘 챙겨둘게요.",
            "concise": f"{title} 등록할게요.",
        }.get(tone, f"{title} 일정으로 등록해둘게요.")

    ask = _ask(tone, fields)
    if length == "short":
        return ask or _lead(tone, title)

    text = f"{_lead(tone, title)} {ask}".strip()
    if length == "long":
        tail = _tail(tone)
        if tail:
            text = f"{text} {tail}"
    return text


def build_reminder_text(title: str, style_profile: Dict[str, str]) -> str:
    """Phrase a reminder sentence by reminder strength (tone-neutral core)."""
    strength = style_profile.get("strength", DEFAULT_STRENGTH)
    if strength == "gentle":
        return f"곧 {title} 일정이 있어요. 가볍게 확인해주세요."
    if strength == "strong":
        return f"중요한 일정입니다. {title} 일정을 꼭 확인해주세요."
    return f"{title} 일정이 예정되어 있어요."


def reminder_offsets(style_profile: Dict[str, str]) -> List[int]:
    """Minutes-before offsets by strength: gentle=1, normal=2, strong=3 reminders."""
    strength = style_profile.get("strength", DEFAULT_STRENGTH)
    if strength == "gentle":
        return [30]
    if strength == "strong":
        return [1440, 60, 10]
    return [60, 10]


def apply_response_style(text: str, style_profile: Dict[str, str]) -> str:
    """Restyle an already-built sentence: light tone tweaks + length control.

    Slot-free: only surrounding phrasing/length is changed. Never raises.
    """
    try:
        tone = style_profile.get("tone", DEFAULT_TONE)
        length = style_profile.get("length", DEFAULT_LENGTH)

        sentences = _split_sentences(text) or [text.strip()]
        if length == "short":
            sentences = sentences[:1]
        elif length == "medium":
            sentences = sentences[:2]
        # long: keep all

        out = " ".join(sentences).strip()

        # conservative tone tweaks (safe, reversible-ish word swaps only)
        if tone == "formal":
            for a, b in (("할게요", "하겠습니다"), ("줄래요", "주세요"), ("할까요", "하시겠어요")):
                out = out.replace(a, b)
        elif tone == "concise":
            out = out.replace("좋아요, ", "").replace("그럼 ", "")
        return out or (text or "").strip()
    except Exception:
        return (text or "").strip()
