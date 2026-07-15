"""Rule-based fallback parser for the ENHANCED parse endpoint.

Produces the flat field set (title/date/start_time/.../category/confidence)
used by ``schedule_parse_service``. Reuses the battle-tested date/time/title
helpers from the existing ``schedule_parser`` (so behaviour stays consistent
with /ai/schedule/parse) and adds three things the enhanced spec needs:

  * week-relative weekday resolution (이번 주/다음 주 <요일>) so that, from a
    mid-week base date, 다음 주 월요일 lands on the NEXT calendar week's Monday;
  * bare time-of-day defaults (아침/오전/점심/오후/저녁/밤) when no explicit
    "N시" is present;
  * the enhanced category enum (health/beauty/study/work/meal/personal/other),
    loaded from rules/schedule_category_rules.json.

Never raises: anything unresolved is simply left as None.
"""

from __future__ import annotations

import json
import re
from datetime import date as date_cls
from datetime import datetime, time, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional, Tuple

# Reuse the existing, tested rule helpers rather than duplicating them.
from backend.services.schedule_parser import (
    _WEEKDAY,
    _add_one_hour,
    _extract_date,
    _extract_time,
    _extract_title,
)

_RULES_DIR = Path(__file__).resolve().parents[1] / "rules"

# "이번 주/다음 주 <요일>" — resolved week-relative (see module docstring).
# Tried BEFORE the generic _extract_date so the week offset is applied correctly.
_WEEK_WEEKDAY_RE = re.compile(
    r"(다음\s*주|담주|다음주|이번\s*주|이번주|금주)\s*([월화수목금토일])요일"
)

# bare time-of-day -> default 'HH:MM'.
_DAYPART_DEFAULTS = [
    ("새벽", "06:00"),
    ("아침", "09:00"),
    ("오전", "10:00"),
    ("점심", "12:00"),
    ("낮", "13:00"),
    ("오후", "15:00"),
    ("저녁", "19:00"),
    ("밤", "21:00"),
]

# keyword -> generated title when the cleaned title is empty/unclear.
_TITLE_KEYWORDS = [
    ("병원", "병원 일정"),
    ("치과", "치과 예약"),
    ("미용실", "미용실 예약"),
    ("네일", "네일 예약"),
    ("회의", "회의"),
    ("미팅", "미팅"),
    ("스터디", "스터디"),
]

_CATEGORY_TITLE_DEFAULT = {
    "health": "병원 일정",
    "beauty": "미용실 예약",
    "study": "스터디",
    "work": "회의",
    "meal": "식사 약속",
    "personal": "개인 약속",
    "other": "새 일정",
}


@lru_cache(maxsize=1)
def _load_rules() -> Dict:
    with open(_RULES_DIR / "schedule_category_rules.json", encoding="utf-8") as f:
        return json.load(f)


def allowed_categories() -> set:
    return set(_load_rules().get("allowed", []))


def base_datetime(today: Optional[str]) -> datetime:
    """Resolve the base datetime. `today` ('YYYY-MM-DD') wins for deterministic
    tests; otherwise fall back to the server clock."""
    if today:
        try:
            return datetime.combine(date_cls.fromisoformat(today), time(0, 0))
        except (ValueError, TypeError):
            pass
    return datetime.now()


def _extract_week_weekday(text: str, base: datetime) -> Tuple[Optional[str], Optional[str]]:
    m = _WEEK_WEEKDAY_RE.search(text)
    if not m:
        return None, None
    target = _WEEKDAY[m.group(2)]
    monday_this_week = base.date() - timedelta(days=base.date().weekday())
    week_offset = 1 if re.match(r"(다음\s*주|담주|다음주)", m.group(1)) else 0
    resolved = monday_this_week + timedelta(days=7 * week_offset + target)
    return resolved.isoformat(), m.group(0)


def _detect_category(text: str, title: str) -> str:
    cfg = _load_rules()
    for source in (title, text):
        if not source:
            continue
        for rule in cfg.get("rules", []):
            for kw in rule["keywords"]:
                if kw in source:
                    return rule["category"]
    return cfg.get("default", "other")


def _daypart_time(text: str) -> Optional[str]:
    for word, hhmm in _DAYPART_DEFAULTS:
        if word in text:
            return hhmm
    return None


def _title_from_keywords(text: str) -> Optional[str]:
    for kw, title in _TITLE_KEYWORDS:
        if kw in text:
            return title
    return None


def parse(text: str, base: datetime) -> Dict:
    """Rule-based parse -> flat dict. Pure function, never raises."""
    text = (text or "").strip()

    date_value, date_expr = _extract_week_weekday(text, base)
    if not date_value:
        date_value, date_expr = _extract_date(text, base)
    start_time, time_expr, ambiguous = _extract_time(text)

    # No explicit "N시" -> fall back to a bare time-of-day default.
    daypart_default = False
    if not start_time:
        dp = _daypart_time(text)
        if dp:
            start_time, daypart_default = dp, True

    end_time = _add_one_hour(start_time) if start_time and not daypart_default else None

    title = _extract_title(text, date_expr, time_expr)
    category = _detect_category(text, title or "")

    if not title:
        title = _title_from_keywords(text) or _CATEGORY_TITLE_DEFAULT.get(category, "새 일정")

    has_date, has_time = bool(date_value), bool(start_time)
    has_cat = category != _load_rules().get("default", "other")

    confidence = round(
        min(0.9, 0.35 + 0.25 * has_date + 0.20 * has_time + 0.10 * bool(title) + 0.10 * has_cat),
        2,
    )

    return {
        "title": title or None,
        "date": date_value,
        "start_time": start_time,
        "end_time": end_time,
        "category": category,
        "location": None,
        "memo": None,
        "confidence": confidence,
        "ambiguous": ambiguous,
        "daypart_default": daypart_default,
        "has_date": has_date,
        "has_time": has_time,
    }
