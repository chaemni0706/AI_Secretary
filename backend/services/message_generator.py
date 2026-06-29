"""Reservation inquiry message generator.

Template-based by default. If an OpenAI key is configured, attempts an LLM
draft via llm_service and falls back to the template on any failure.
`generated_message` and `alternatives` are always returned.
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

_SUBJECT_DEFAULT = {
    "hospital": "진료 예약",
    "beauty": "커트·시술 예약",
    "restaurant": "예약",
    "meeting": "회의",
    "etc": "예약",
}

_REL_DATE_RE = re.compile(
    r"(다음\s*주\s*[월화수목금토일]요일|이번\s*주\s*[월화수목금토일]요일|모레|글피|내일|오늘|[월화수목금토일]요일)"
)


def _i_ga(word: str) -> str:
    if not word:
        return "가"
    last = word[-1]
    if "가" <= last <= "힣":
        return "이" if (ord(last) - 0xAC00) % 28 else "가"
    return "가"


def _collapse(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


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
    ampm = "오전" if h < 12 else "오후"
    h12 = h % 12 or 12
    phrase = f"{ampm} {h12}시"
    if m:
        phrase += f" {m}분"
    return phrase, ampm


def _subject(category: str, purpose: Optional[str]) -> str:
    if purpose:
        return purpose
    return _SUBJECT_DEFAULT.get(category, _SUBJECT_DEFAULT["etc"])


def _build(category: str, date_p: str, time_p: str, ampm: str, subject: str) -> Tuple[str, List[str]]:
    if category == "meeting":
        main = f"안녕하세요. {date_p} {time_p}쯤으로 {subject} 일정을 조율하고자 합니다. 해당 시간에 가능하신지 여쭙고 싶습니다."
        alts = [
            f"안녕하세요. {date_p} {ampm} 중으로 {subject} 일정을 잡고 싶은데 가능한 시간을 알려주실 수 있을까요?",
            f"안녕하세요. {date_p} {time_p} {subject} 진행 가능 여부를 확인 부탁드립니다.",
        ]
    elif category == "restaurant":
        main = f"안녕하세요. {date_p} {time_p}쯤 예약이 가능한지 문의드립니다. 인원과 시간에 맞춰 자리가 있을까요?"
        alts = [
            f"안녕하세요. {date_p} {ampm} 시간대에 예약 가능한 자리가 있는지 문의드립니다.",
            f"안녕하세요. {date_p} {time_p} 예약 가능 여부와 가능 인원 확인 부탁드립니다.",
        ]
    else:  # hospital / beauty / etc
        main = f"안녕하세요. {date_p} {time_p}쯤 {subject}{_i_ga(subject)} 가능한지 문의드립니다. 가능한 시간이 있을까요?"
        alts = [
            f"안녕하세요. {date_p} {ampm} 시간대에 {subject} 가능한 시간이 있는지 문의드립니다.",
            f"안녕하세요. {date_p} {time_p} {subject} 가능 여부 확인 부탁드립니다.",
        ]
    return _collapse(main), [_collapse(a) for a in alts]


def _apply_tone(s: str, tone: str) -> str:
    if tone == "casual":
        s = (
            s.replace("문의드립니다", "문의해요")
            .replace("부탁드립니다", "부탁해요")
            .replace("여쭙고 싶습니다", "여쭤봐요")
            .replace("감사하겠습니다", "감사해요")
        )
    return s


def _apply_length(s: str, length: str) -> str:
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

    date_p = _date_phrase(req.input, info.target_date)
    time_p, ampm = _time_phrase(info.preferred_time)
    subject = _subject(category, info.purpose)

    main, alts = _build(category, date_p, time_p, ampm, subject)

    # apply style to template output
    main = _apply_length(_apply_tone(main, style.tone), style.length)
    main = _apply_tone(main, style.tone)
    alts = [_apply_tone(a, style.tone) for a in alts]

    # optional LLM draft (None when key absent or any failure)
    llm_text = None
    try:
        llm_text = llm_service.generate(_build_prompt(req))
    except Exception:
        llm_text = None

    generated = llm_text if llm_text else main

    return ReservationMessageData(
        generated_message=generated,
        alternatives=alts,
        style=style,
    )
