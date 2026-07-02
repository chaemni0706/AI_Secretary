"""Reservation inquiry message generator.

Template-based by default so the endpoint produces a natural Korean message
even without an OpenAI key. If a key is configured, an LLM draft is attempted
via `llm_service` and any failure falls back to the template. `generated_message`
and exactly-two `alternatives` are always returned.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple

from backend.database.schema.message_schema import (
    ReservationMessageData,
    ReservationMessageRequest,
)
from backend.services import llm_service

_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "reservation_prompt.txt"

# Default subject word per category (used when no purpose is supplied).
_DEFAULT_PURPOSE = {
    "hospital": "진료",
    "beauty": "커트",
    "restaurant": "",
    "meeting": "",
    "etc": "",
}

_REL_DATE_RE = re.compile(
    r"(다음\s*주\s*[월화수목금토일]요일|이번\s*주\s*[월화수목금토일]요일|모레|글피|내일|오늘|[월화수목금토일]요일)"
)


def _collapse(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _purpose_word(category: str, purpose: Optional[str]) -> str:
    """Subject word for the message; trailing '예약' is dropped to avoid '예약 예약'.

    If stripping leaves nothing (e.g. purpose == "예약"), fall back to the
    category default — never to the original word, which would reintroduce the
    duplication.
    """
    if purpose:
        core = re.sub(r"(?:\s*예약)+\s*$", "", purpose).strip()
        if core:
            return core
    return _DEFAULT_PURPOSE.get(category, "")


def _date_phrase(user_input: Optional[str], target_date: Optional[str]) -> str:
    """Human-friendly date: reuse a relative phrase from the utterance, else 'M월 D일'."""
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


def _build_template(category: str, date_p: str, time_p: str, ampm: str,
                    pword: str) -> Tuple[str, List[str]]:
    """Return (main_message, [alt1, alt2]) for the category. Always 2 alternatives."""
    when = _collapse(f"{date_p} {time_p}")
    when_jjeum = f"{when}쯤" if when else ""
    when_e = f"{when}에" if when else ""
    ampm_slot = f"{date_p} {ampm} 시간대" if (date_p or ampm) else "가능한 시간대"

    if category == "hospital":
        main = f"안녕하세요. {when_jjeum} {pword} 예약이 가능한지 문의드립니다. 가능한 시간이 있을까요?"
        alts = [
            f"안녕하세요. {ampm_slot}에 {pword} 예약이 가능한 시간이 있는지 문의드립니다.",
            f"안녕하세요. {when} {pword} 예약 가능 여부를 확인 부탁드립니다.",
        ]
    elif category == "beauty":
        main = f"안녕하세요. {when_jjeum} 커트 또는 시술 예약 가능한 시간이 있을까요?"
        alts = [
            f"안녕하세요. {ampm_slot}에 커트나 시술 예약이 가능한지 문의드립니다.",
            f"안녕하세요. {when} 미용실 예약 가능 여부를 확인 부탁드립니다.",
        ]
    elif category == "restaurant":
        subject = f"{pword} " if pword else ""
        main = f"안녕하세요. {when_e} {subject}예약이 가능한지 문의드립니다."
        alts = [
            f"안녕하세요. {ampm_slot}에 예약이 가능한 자리가 있는지 문의드립니다.",
            f"안녕하세요. {when} 예약 가능 여부와 가능 인원 확인 부탁드립니다.",
        ]
    elif category == "meeting":
        main = f"안녕하세요. {when_e} 회의 일정 조율이 가능할지 확인 부탁드립니다."
        alts = [
            f"안녕하세요. {date_p} {ampm} 중으로 회의 일정을 조율하고 싶은데 가능한 시간을 알려주실 수 있을까요?",
            f"안녕하세요. {when} 회의 진행 가능 여부를 확인 부탁드립니다.",
        ]
    else:  # etc / unknown
        main = f"안녕하세요. {when_jjeum} 예약 가능 여부 문의드립니다."
        alts = [
            f"안녕하세요. {ampm_slot}에 예약이 가능한지 문의드립니다.",
            f"안녕하세요. {when} 예약 가능 여부 확인 부탁드립니다.",
        ]

    return _collapse(main), [_collapse(a) for a in alts]


def _apply_tone(s: str, tone: str) -> str:
    if tone == "casual":
        s = (
            s.replace("문의드립니다", "문의해요")
            .replace("부탁드립니다", "부탁해요")
            .replace("감사하겠습니다", "감사해요")
        )
    return s


def _apply_length(s: str, length: str, channel: str) -> str:
    # SMS must not get the verbose form.
    if channel == "sms" and length == "long":
        length = "medium"
    if length == "medium":
        return s + " 확인 후 회신 주시면 감사하겠습니다."
    if length == "long":
        return "바쁘신 와중에 문의드려 죄송합니다. " + s + " 확인 후 회신 주시면 감사하겠습니다. 감사합니다."
    return s


def _build_prompt(req: ReservationMessageRequest) -> str:
    info, style = req.reservation_info, req.style
    try:
        template = _PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        template = "예약 문의 메시지를 작성하세요. 카테고리:{category} 날짜:{target_date} 시간:{preferred_time} 목적:{purpose}"
    return template.format(
        category=info.category or "etc",
        target_date=info.target_date or "(미지정)",
        preferred_time=info.preferred_time or "(미지정)",
        purpose=info.purpose or "(미지정)",
        tone=style.tone,
        length=style.length,
        channel=style.channel,
    )


def generate_message(req: ReservationMessageRequest) -> ReservationMessageData:
    info, style = req.reservation_info, req.style
    category = (info.category or "etc").lower()
    if category not in ("hospital", "beauty", "restaurant", "meeting"):
        category = "etc"

    date_p = _date_phrase(req.input, info.target_date)
    time_p, ampm = _time_phrase(info.preferred_time)
    pword = _purpose_word(category, info.purpose)

    main, alts = _build_template(category, date_p, time_p, ampm, pword)

    # Apply style: length/channel shaping then tone (main); tone only for alts.
    main = _apply_tone(_apply_length(main, style.length, style.channel), style.tone)
    alts = [_apply_tone(a, style.tone) for a in alts]

    # Optional LLM draft; None (no key / any failure) -> template fallback.
    llm_text = None
    try:
        llm_text = llm_service.generate(
            _build_prompt(req),
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
