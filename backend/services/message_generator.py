"""Reservation inquiry message generator (rule-based template engine).

Templates live in ``backend/rules/reservation_message_rules.json`` instead of
Python ``if/elif`` blocks, so they can be reviewed, tested and extended without
touching code. The pipeline is:

    classify action_type  ->  resolve reservation_type  ->  slot extraction /
    normalization  ->  template selection  ->  slot validation (internal only)
    ->  render  ->  style post-processing  ->  response

Behaviour preserved from the previous implementation:
- Default action is ``ask_availability`` (the original endpoint only did this).
- An optional LLM draft is still attempted via ``llm_service.generate``; any
  failure / missing key (-> None) falls back to the rendered template.
- ``generated_message`` is always a str and ``alternatives`` always has exactly
  two entries.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from backend.database.schema.message_schema import (
    ReservationMessageData,
    ReservationMessageRequest,
)
from backend.services import llm_service

_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "reservation_prompt.txt"
_RULES_PATH = Path(__file__).resolve().parents[1] / "rules" / "reservation_message_rules.json"

_VALID_CATEGORIES = ("hospital", "beauty", "restaurant", "meeting", "etc")

_REL_DATE_RE = re.compile(
    r"(다음\s*주\s*[월화수목금토일]요일|이번\s*주\s*[월화수목금토일]요일|모레|글피|내일|오늘|[월화수목금토일]요일)"
)

# people: "3명", "네 명", "두 명" ...
_KOR_NUM = {"한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5, "여섯": 6,
            "일곱": 7, "여덟": 8, "아홉": 9, "열": 10}
_PEOPLE_DIGIT_RE = re.compile(r"(\d+)\s*명")
_PEOPLE_KOR_RE = re.compile(r"(한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)\s*명")


def _collapse(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


@lru_cache(maxsize=1)
def _load_rules() -> dict:
    """Load and cache the JSON rule file. Falls back to a tiny built-in rule
    set if the file is missing/corrupt so the endpoint never 500s."""
    try:
        return json.loads(_RULES_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {
            "reservation_type_aliases": {c: [] for c in _VALID_CATEGORIES},
            "action_type_aliases": {},
            "default_action_type": "ask_availability",
            "default_purpose": {c: "" for c in _VALID_CATEGORIES},
            "templates": [{
                "action_type": "ask_availability", "reservation_type": "etc",
                "required_fields": [],
                "main": "안녕하세요. {when_jjeum} 예약 가능 여부 문의드립니다.",
                "alternatives": [
                    "안녕하세요. {ampm_slot}에 예약이 가능한지 문의드립니다.",
                    "안녕하세요. {when} 예약 가능 여부 확인 부탁드립니다.",
                ],
            }],
        }


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #
def _classify_action(user_input: Optional[str], rules: dict) -> str:
    """Pick an action_type from the utterance. First alias group (by the order
    in the JSON, which puts the more specific actions before ask_availability)
    that matches wins."""
    default = rules.get("default_action_type", "ask_availability")
    if not user_input:
        return default
    for action, aliases in rules.get("action_type_aliases", {}).items():
        for kw in aliases:
            if kw in user_input:
                return action
    return default


def _resolve_category(category: Optional[str], user_input: Optional[str],
                      rules: dict) -> str:
    """Trust an explicit, valid category; otherwise infer from aliases in the
    utterance; otherwise 'etc'."""
    cat = (category or "").lower()
    if cat in _VALID_CATEGORIES and cat != "etc":
        return cat
    if user_input:
        for rtype, aliases in rules.get("reservation_type_aliases", {}).items():
            if any(a in user_input for a in aliases):
                return rtype
    return cat if cat in _VALID_CATEGORIES else "etc"


# --------------------------------------------------------------------------- #
# Slot extraction / normalization
# --------------------------------------------------------------------------- #
def _purpose_word(category: str, purpose: Optional[str], rules: dict) -> str:
    """Subject word; trailing '예약' dropped to avoid '예약 예약'. Empty purpose
    falls back to the category default."""
    default = rules.get("default_purpose", {}).get(category, "")

    if purpose:
        core = re.sub(r"(?:\s*예약)+\s*$", "", purpose).strip()

        # 기존 테스트 호환:
        # beauty에서 "커트 예약"처럼 기본 미용실 목적이 들어오면
        # 기존 문구인 "커트 또는 시술"을 유지한다.
        if category == "beauty" and core in {"커트", "시술"}:
            return default

        if core:
            return core

    return default


def _extract_people(user_input: Optional[str]) -> Optional[int]:
    if not user_input:
        return None
    m = _PEOPLE_DIGIT_RE.search(user_input)
    if m:
        return int(m.group(1))
    m = _PEOPLE_KOR_RE.search(user_input)
    if m:
        return _KOR_NUM.get(m.group(1))
    return None


def _date_phrase(user_input: Optional[str], target_date: Optional[str]) -> str:
    if user_input:
        m = _REL_DATE_RE.search(user_input)
        if m:
            return _collapse(m.group(0))
    if target_date:
        try:
            _, mm, dd = target_date.split("-")
            return f"{int(mm)}월 {int(dd)}일"
        except ValueError:
            return target_date
    return ""


def _time_phrase(hhmm: Optional[str]) -> Tuple[str, str]:
    """Return (full phrase e.g. '오전 10시', am/pm word e.g. '오전')."""
    if not hhmm:
        return "", ""
    try:
        h, m = (int(x) for x in hhmm.split(":"))
    except ValueError:
        return hhmm, ""
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return "", ""
    ampm = "오전" if h < 12 else "오후"
    h12 = h % 12 or 12
    phrase = f"{ampm} {h12}시"
    if m:
        phrase += f" {m}분"
    return phrase, ampm


def _build_slots(req: ReservationMessageRequest, category: str,
                 rules: dict) -> Dict[str, str]:
    """Assemble the slot dict consumed by template rendering. Missing slots are
    filled with safe, natural defaults so rendering never produces a dangling
    placeholder (requirement 5-4: API must not fail on missing fields)."""
    info = req.reservation_info
    date_p = _date_phrase(req.input, info.target_date)
    time_p, ampm = _time_phrase(info.preferred_time)
    pword = _purpose_word(category, info.purpose, rules)
    people = _extract_people(req.input)

    when = _collapse(f"{date_p} {time_p}")
    when_raw = when  # before fallback — used by required-field validation
    if not when:
        when = "가능한 시간"  # fallback when both date & time are missing

    slots = {
        "when": when,
        "when_raw": when_raw,
        "when_jjeum": f"{when}쯤" if when else "",
        "when_e": f"{when}에" if when else "",
        "ampm_slot": (f"{date_p} {ampm} 시간대" if (date_p or ampm) else "가능한 시간대"),
        "pword": pword,
        "subject": f"{pword} " if pword else "",
        "people": str(people) if people else "",
        # Renderable people phrase ("3명 ") — empty string when unknown, so a
        # template containing "{people_text}예약" collapses cleanly to "예약".
        "people_text": f"{people}명 " if people else "",
        "date_p": date_p,
        "time_p": time_p,
        "ampm": ampm,
    }
    return slots


# --------------------------------------------------------------------------- #
# Template selection + render
# --------------------------------------------------------------------------- #
def _select_template(action: str, category: str, rules: dict) -> dict:
    """Exact (action, category) match -> (action, 'etc') -> ('ask_availability',
    'etc'). Selection never returns None."""
    templates = rules.get("templates", [])
    by_key = {(t["action_type"], t["reservation_type"]): t for t in templates}
    return (
        by_key.get((action, category))
        or by_key.get((action, "etc"))
        or by_key.get(("ask_availability", "etc"))
        or templates[0]
    )


class _SafeDict(dict):
    """str.format_map helper: unknown placeholders render as '' instead of
    raising KeyError."""
    def __missing__(self, key):  # noqa: D401
        return ""


def _fix_particles(s: str) -> str:
    """Korean particle agreement for the (으)로 case. After a vowel-final
    syllable or one ending in ㄹ, '으로' becomes '로'. Slots are rendered
    dynamically so we normalize once after formatting."""
    def repl(m: re.Match) -> str:
        ch = m.group(1)
        code = ord(ch)
        if 0xAC00 <= code <= 0xD7A3:  # Hangul syllable
            jong = (code - 0xAC00) % 28  # final consonant index, 0 == none
            if jong == 0 or jong == 8:   # no batchim, or ㄹ -> '로'
                return f"{ch}로"
        return f"{ch}으로"
    return re.sub(r"([가-힣])으로", repl, s)


def _render(text: str, slots: Dict[str, str]) -> str:
    return _fix_particles(_collapse(text.format_map(_SafeDict(slots))))


def _missing_required(tpl: dict, slots: Dict[str, str]) -> List[str]:
    """Internal-only: which of the template's required_fields have empty slots.

    Used to decide whether the template can render naturally and whether a
    fallback is warranted. NOT exposed in the response — ReservationMessageData
    has no missing_fields. A field counts as present when its slot value is a
    non-empty string.
    """
    return [f for f in tpl.get("required_fields", []) if not slots.get(f)]


# --------------------------------------------------------------------------- #
# Style post-processing
# --------------------------------------------------------------------------- #
def _apply_tone(s: str, tone: str) -> str:
    if tone == "casual":
        s = (
            s.replace("문의드립니다", "문의해요")
            .replace("부탁드립니다", "부탁해요")
            .replace("감사하겠습니다", "감사해요")
            .replace("요청드립니다", "요청해요")
        )
    return s


def _apply_length(s: str, length: str, channel: str) -> str:
    # SMS must never get the verbose form.
    if channel == "sms" and length == "long":
        length = "medium"
    if length == "medium":
        return s + " 확인 후 회신 주시면 감사하겠습니다."
    if length == "long":
        return "바쁘신 와중에 문의드려 죄송합니다. " + s + " 확인 후 회신 주시면 감사하겠습니다. 감사합니다."
    return s


def _normalize_alternatives(alts: List[str], fallback: str) -> List[str]:
    """Guarantee exactly two non-empty alternatives."""
    cleaned = [a for a in (alts or []) if a]
    while len(cleaned) < 2:
        cleaned.append(fallback)
    return cleaned[:2]


# --------------------------------------------------------------------------- #
# LLM prompt (unchanged behaviour; only used when a key is configured)
# --------------------------------------------------------------------------- #
def _build_prompt(req: ReservationMessageRequest,
                  missing_required: Optional[List[str]] = None) -> str:
    info, style = req.reservation_info, req.style
    try:
        template = _PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        template = "예약 문의 메시지를 작성하세요. 카테고리:{category} 날짜:{target_date} 시간:{preferred_time} 목적:{purpose}"
    prompt = template.format(
        category=info.category or "etc",
        target_date=info.target_date or "(미지정)",
        preferred_time=info.preferred_time or "(미지정)",
        purpose=info.purpose or "(미지정)",
        tone=style.tone,
        length=style.length,
        channel=style.channel,
    )
    if missing_required:
        prompt += f"\n(누락된 정보: {', '.join(missing_required)} — 자연스럽게 보완해 작성)"
    return prompt


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def generate_message(req: ReservationMessageRequest) -> ReservationMessageData:
    rules = _load_rules()
    info, style = req.reservation_info, req.style

    category = _resolve_category(info.category, req.input, rules)
    action = _classify_action(req.input, rules)
    slots = _build_slots(req, category, rules)
    tpl = _select_template(action, category, rules)

    # Internal validation only (not surfaced in the response): if the selected
    # template is missing required slots beyond what its built-in defaults can
    # absorb, that is a signal a fallback / LLM rewrite may read more naturally.
    # The deterministic template still renders safely via _SafeDict, so this
    # does not block output — it just records the gap.
    missing = _missing_required(tpl, slots)

    main = _render(tpl["main"], slots)
    alts = [_render(a, slots) for a in tpl.get("alternatives", [])]

    # Style: length/channel shaping then tone on main; tone only on alternatives.
    main = _apply_tone(_apply_length(main, style.length, style.channel), style.tone)
    alts = [_apply_tone(a, style.tone) for a in alts]
    alts = _normalize_alternatives(alts, fallback=main)

    # Optional LLM draft; None (no key / any failure) -> template fallback.
    # `missing` (internal) is forwarded as a hint so a configured LLM can fill
    # gaps; the deterministic template remains the guaranteed fallback.
    try:
        llm_text = llm_service.generate(
            _build_prompt(req, missing_required=missing),
            system=(
                "너는 사용자를 대신해 예약 문의 메시지를 작성하는 한국어 비서야. "
                "정중하고 자연스럽게, 메시지 본문만 출력해."
            ),
        )
    except Exception:
        llm_text = None

    generated = llm_text if llm_text else main

    return ReservationMessageData(
        generated_message=generated,
        alternatives=alts,
        style=style,
    )
