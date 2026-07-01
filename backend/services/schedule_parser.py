"""Rule-based Korean natural-language schedule parser.

Extracts intent, date/time expressions, title, category and priority from a
free-text utterance. Never raises on bad input: anything it cannot resolve is
reported via `missing_fields`.

Policy notes:
- Title strips date/time expressions, command verbs (잡아/추가해/등록해/저장해/
  넣어/해야 해 ...), deadline markers (~까지) and filler nouns (일정/스케줄/예약) /
  leading fillers (할 일로/일정으로 ...). ('예약' 제거는 팀 회귀 테스트
  test_reservation_word_not_left_in_title 로 고정된 정책이다.)
- To-do intent: strong to-do signals (작성/제출/정리/장보기/마감/까지 ...) classify
  as create_todo, unless a schedule-override keyword (예약/회의/약속/병원/알림 ...)
  is present.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple

from backend.database.schema.schedule_schema import (
    ScheduleDraft,
    ScheduleParseData,
    ScheduleParseRequest,
    ScheduleSlots,
)

_RULES_DIR = Path(__file__).resolve().parents[1] / "rules"

_WEEKDAY = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}

# Command/verb endings to strip from the end of a title (longest first).
# '~줘' 없는 명령형(잡아/추가해/등록해/저장해/넣어 등)도 함께 제거한다.
_VERB_TAILS = sorted(
    [
        "잡아줘", "잡아 줘", "추가해줘", "추가 해줘", "넣어줘", "넣어 줘",
        "알림해줘", "알림 해줘", "알려줘", "등록해줘", "만들어줘", "예약해줘",
        "저장해줘", "저장 해줘",
        # bare command forms (without 줘)
        "추가해", "추가 해", "등록해", "등록 해", "저장해", "저장 해",
        "예약해", "만들어", "알림해", "넣어", "잡아",
        "해야 해", "해야해", "해야 돼", "해야돼", "해야겠다", "해야지",
        "해줘", "해 줘", "있어", "줘", "좀", "해주세요", "주세요", "잡고",
    ],
    key=len,
    reverse=True,
)

# Filler nouns that are noise when trailing a title ("운동 일정" -> "운동",
# "병원 예약" -> "병원"). '예약' 제거는 test_reservation_word_not_left_in_title
# 로 고정된 기존 정책이다.
_NOISE_NOUNS = ["일정", "스케줄", "예약"]

# Combined trailing tokens stripped from a title, longest first.
_TITLE_TAILS = sorted(_VERB_TAILS + _NOISE_NOUNS, key=len, reverse=True)

# Filler tokens dropped when they LEAD a title:
#   "예약 진료" -> "진료", "할 일로 장보기" -> "장보기".
_LEADING_NOISE = ("할 일로", "할일로", "일정으로", "예약", "일정", "스케줄", "더", "동안")

# --- intent classification signals ----------------------------------------- #
# 강한 To-do 신호.
_TODO_KEYWORDS = (
    "해야 해", "해야돼", "해야 돼", "해야겠다", "해야지",
    "하기", "할 일", "할일", "장보기", "장 보기",
    "작성", "제출", "정리", "준비", "확인", "마감", "까지",
)
# 아래 신호가 있으면 To-do 신호가 있어도 일정(schedule)으로 유지한다.
# ('알림'은 시간 기반 리마인더 → 일정성으로 취급)
_SCHEDULE_OVERRIDE = (
    "예약", "회의", "미팅", "약속", "수업", "병원", "치과", "방문", "알림",
)

# category 기반 기본 title (title 이 비었을 때만 사용).
_CATEGORY_DEFAULT_TITLE = {
    "hospital": "병원 예약",
    "meeting": "회의",
    "beauty": "미용실 예약",
    "restaurant": "식당 예약",
    "school": "수업",
    "exercise": "운동",
    "shopping": "장보기",
}

_DURATION_RE = re.compile(
    r"(?:\d+\s*시간(?:\s*\d+\s*분)?|\d+\s*분)(?:\s*(?:짜리|동안|만)(?=\s|$))?"
)


@lru_cache(maxsize=1)
def _load_category_rules() -> Tuple[list, str]:
    with open(_RULES_DIR / "category_rules.json", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg.get("rules", []), cfg.get("default", "etc")


@lru_cache(maxsize=1)
def _load_priority_rules() -> dict:
    with open(_RULES_DIR / "priority_rules.json", encoding="utf-8") as f:
        return json.load(f)


def _base_datetime(req: ScheduleParseRequest) -> datetime:
    if req.current_datetime:
        try:
            return datetime.fromisoformat(req.current_datetime)
        except ValueError:
            pass
    return datetime.now()


# --------------------------------------------------------------------------- #
# Date parsing
# --------------------------------------------------------------------------- #
def _extract_date(text: str, base: datetime) -> Tuple[Optional[str], Optional[str]]:
    """Return (resolved 'YYYY-MM-DD', matched expression) or (None, None)."""
    base_date = base.date()

    # ISO 'YYYY-MM-DD'
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            try:
                return base_date.replace(year=y, month=mo, day=d).isoformat(), m.group(0)
            except ValueError:
                pass

    # 다음 주 <요일> / 이번 주 <요일>
    m = re.search(r"(다음\s*주|담주|이번\s*주|금주)\s*([월화수목금토일])요일", text)
    if m:
        target = _WEEKDAY[m.group(2)]
        delta = (target - base_date.weekday()) % 7
        this_week = base_date + timedelta(days=delta)
        if re.match(r"다음\s*주|담주", m.group(1)):
            this_week += timedelta(days=7)
        return this_week.isoformat(), m.group(0)

    # N월 N일
    m = re.search(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일", text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        year = base_date.year
        try:
            resolved = base_date.replace(year=year, month=month, day=day)
        except ValueError:
            return None, m.group(0)
        if resolved < base_date:
            resolved = resolved.replace(year=year + 1)
        return resolved.isoformat(), m.group(0)

    # M/D (슬래시 표기, 예: '7/3', '7 / 3'). 월 1-12, 일 1-31 일 때만 날짜로 인정.
    m = re.search(r"(?<!\d)(\d{1,2})\s*/\s*(\d{1,2})(?!\d)", text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            year = base_date.year
            try:
                resolved = base_date.replace(year=year, month=month, day=day)
            except ValueError:
                resolved = None
            if resolved is not None:
                if resolved < base_date:
                    resolved = resolved.replace(year=year + 1)
                return resolved.isoformat(), m.group(0)

    # relative day words
    for word, offset in (("글피", 3), ("모레", 2), ("내일", 1), ("오늘", 0)):
        if word in text:
            return (base_date + timedelta(days=offset)).isoformat(), word

    # bare weekday (e.g. 금요일) -> next occurrence (including today)
    m = re.search(r"([월화수목금토일])요일", text)
    if m:
        target = _WEEKDAY[m.group(1)]
        delta = (target - base_date.weekday()) % 7
        return (base_date + timedelta(days=delta)).isoformat(), m.group(0)

    return None, None


# --------------------------------------------------------------------------- #
# Time parsing
# --------------------------------------------------------------------------- #
def _extract_time(text: str) -> Tuple[Optional[str], Optional[str], bool]:
    """Return (resolved 'HH:mm', matched expression, ambiguous)."""
    # HH:mm (24h)
    m = re.search(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)", text)
    if m:
        return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}", m.group(0), False

    m = re.search(
        r"(오전|오후|아침|저녁|밤|점심|낮|새벽)?\s*(\d{1,2})\s*시(?!간)\s*"
        r"(?:(\d{1,2})\s*분|반)?",
        text,
    )
    if not m:
        return None, None, False

    meridiem, hour_s, minute_s = m.group(1), m.group(2), m.group(3)
    hour = int(hour_s)
    # '3시 반' -> 30분
    if minute_s:
        minute = int(minute_s)
    elif "반" in m.group(0):
        minute = 30
    else:
        minute = 0

    if not (0 <= hour <= 23) or not (0 <= minute <= 59):
        return None, None, False

    ambiguous = False

    if meridiem in ("오전", "아침", "새벽"):
        if hour == 12:
            hour = 0
    elif meridiem in ("오후", "저녁", "점심", "낮"):
        if hour < 12:
            hour += 12
    elif meridiem == "밤":
        if hour < 12:
            hour += 12
        elif hour == 12:
            hour = 0
    else:
        if 1 <= hour <= 11:
            hour += 12
        ambiguous = True

    return f"{hour:02d}:{minute:02d}", m.group(0).strip(), ambiguous


def _add_one_hour(hhmm: str) -> str:
    t = datetime.strptime(hhmm, "%H:%M") + timedelta(hours=1)
    return t.strftime("%H:%M")


# --------------------------------------------------------------------------- #
# Title / category / priority
# --------------------------------------------------------------------------- #
def _extract_title(text: str, date_expr: Optional[str], time_expr: Optional[str]) -> str:
    work = text
    for expr in (date_expr, time_expr):
        if expr:
            work = work.replace(expr, " ")
    work = _DURATION_RE.sub(" ", work)
    # 마감 표현 제거 (금요일까지 / 저녁까지 / 3시까지 -> 토큰 통째로 제거)
    work = re.sub(r"\S*까지", " ", work)
    work = re.sub(r"(?:^|\s)에(?=\s|$)", " ", " " + work + " ")
    work = re.sub(r"\s+", " ", work).strip()

    changed = True
    while changed and work:
        changed = False
        for v in _TITLE_TAILS:
            if work.endswith(v):
                work = work[: -len(v)].strip()
                changed = True
                break
        if changed:
            continue
        for w in _LEADING_NOISE:
            if work == w or work.startswith(w + " "):
                work = work[len(w):].strip()
                changed = True
                break
    return work.strip()


def _detect_category(*texts: str) -> str:
    rules, default = _load_category_rules()
    for text in texts:
        if not text:
            continue
        for rule in rules:
            for kw in rule["keywords"]:
                if kw in text:
                    return rule["category"]
    return default


def _detect_priority(category: str, *texts: str) -> str:
    cfg = _load_priority_rules()
    joined = " ".join(t for t in texts if t)
    if any(kw in joined for kw in cfg.get("high_keywords", [])):
        return "high"
    if any(kw in joined for kw in cfg.get("low_keywords", [])):
        return "low"
    cat_priority = cfg.get("category_priority", {})
    if category in cat_priority:
        return cat_priority[category]
    return cfg.get("default", "medium")


def _default_title(category: str, is_todo: bool) -> str:
    if is_todo:
        return "새 할 일"
    return _CATEGORY_DEFAULT_TITLE.get(category, "새 일정")


def _classify_intent(text: str, has_date: bool, has_time: bool,
                     has_title: bool, has_category: bool) -> str:
    """create_todo / create_schedule / unknown."""
    is_override = any(k in text for k in _SCHEDULE_OVERRIDE)
    is_todo_signal = (not is_override) and any(k in text for k in _TODO_KEYWORDS)
    if is_todo_signal:
        return "create_todo"
    if has_date or has_time or has_title or has_category:
        return "create_schedule"
    return "unknown"


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def parse_schedule(req: ScheduleParseRequest) -> ScheduleParseData:
    text = (req.input or "").strip()
    base = _base_datetime(req)

    date_value, date_expr = _extract_date(text, base)
    start_time, time_expr, ambiguous = _extract_time(text)
    end_time = _add_one_hour(start_time) if start_time else None
    title = _extract_title(text, date_expr, time_expr)

    category = _detect_category(title, re.sub(re.escape(time_expr or ""), "", text))
    priority = _detect_priority(category, title, text)

    missing: List[str] = []
    if not date_value:
        missing.append("date")
    if not start_time:
        missing.append("time")
    if not title:
        missing.append("title")
    if ambiguous:
        missing.append("time_ambiguity")

    has_date, has_time = bool(date_value), bool(start_time)
    has_title, has_category = bool(title), category != "etc"

    intent = _classify_intent(text, has_date, has_time, has_title, has_category)
    is_todo = intent == "create_todo"

    confidence = round(
        min(
            0.95,
            0.40
            + 0.18 * has_date
            + 0.18 * has_time
            + 0.10 * has_title
            + 0.08 * has_category,
        ),
        2,
    )

    final_title = title or _default_title(category, is_todo)

    slots = ScheduleSlots(
        title=title or None,
        date_expression=date_expr,
        time_expression=time_expr,
        date=date_value,
        start_time=start_time,
        end_time=end_time,
        category=category,
        location=None,
    )

    draft = ScheduleDraft(
        title=final_title,
        category=category,
        date=date_value,
        start_time=start_time,
        end_time=end_time,
        location=None,
        memo=None,
        priority=priority,
        source="ai",
    )

    return ScheduleParseData(
        intent=intent,
        confidence=confidence,
        slots=slots,
        schedule_draft=draft,
        missing_fields=missing,
    )
