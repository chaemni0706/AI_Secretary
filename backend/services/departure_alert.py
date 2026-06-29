"""Rule-based departure / preparation planner.

Computes a recommended leave time, a preparation checklist (category + weather,
de-duplicated) and notification times. Never raises: a malformed start time
yields leave_time=None with an empty notification list.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from backend.database.schema.alert_schema import (
    ChecklistItem,
    DeparturePlanData,
    DeparturePlanRequest,
    NotificationItem,
)

_RULES_DIR = Path(__file__).resolve().parents[1] / "rules"


@lru_cache(maxsize=1)
def _checklist_rules() -> dict:
    with open(_RULES_DIR / "checklist_rules.json", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _notification_rules() -> dict:
    with open(_RULES_DIR / "notification_rules.json", encoding="utf-8") as f:
        return json.load(f)


def _wa_gwa(word: str) -> str:
    if not word:
        return "와"
    last = word[-1]
    if "가" <= last <= "힣":
        return "과" if (ord(last) - 0xAC00) % 28 else "와"
    return "와"


def _eul_reul(word: str) -> str:
    if not word:
        return "를"
    last = word[-1]
    if "가" <= last <= "힣":
        return "을" if (ord(last) - 0xAC00) % 28 else "를"
    return "를"


def _to_min(hhmm: str) -> Optional[int]:
    try:
        h, m = (int(x) for x in hhmm.split(":"))
    except (ValueError, AttributeError):
        return None
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return h * 60 + m


def _to_hhmm(minutes: int) -> str:
    minutes %= 24 * 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _build_checklist(category: str, weather: Optional[str]) -> List[ChecklistItem]:
    """Category base items + weather extras, de-duplicated by item name."""
    rules = _checklist_rules()
    cats = rules.get("categories", {})
    raw = list(cats.get(category, cats.get("etc", [])))
    if weather:
        raw += rules.get("weather", {}).get(weather.lower(), [])

    items: List[ChecklistItem] = []
    seen: set[str] = set()
    for x in raw:
        name = x.get("item")
        if not name or name in seen:
            continue
        seen.add(name)
        items.append(ChecklistItem(**x))
    return items


def _items_phrase(checklist: List[ChecklistItem]) -> str:
    names = [c.item for c in checklist[:2]]
    if not names:
        return "필요한 준비물"
    if len(names) == 1:
        a = names[0]
        return f"{a}{_eul_reul(a)}"
    a, b = names[0], names[1]
    return f"{a}{_wa_gwa(a)} {b}{_eul_reul(b)}"


def _prep_message(offset: int, title: str, phrase: str) -> str:
    if offset >= 60:
        return f"{title} 준비를 시작할 시간입니다. {phrase} 미리 챙겨두세요."
    return f"{title} 시간이 다가옵니다. {phrase} 챙기고 출발을 준비하세요."


def _build_notifications(
    start_min: int,
    leave_min: int,
    pref,
    phrase: str,
    title: str,
) -> List[NotificationItem]:
    rules = _notification_rules()
    styles = rules.get("styles", {})

    # Forgetful users are escalated to the stronger style.
    style_name = pref.notification_style
    if pref.forgetful:
        style_name = rules.get("escalate_when_forgetful", "strong")
    style = styles.get(style_name, styles.get("normal", {}))

    # minute -> message (dict de-dupes identical times automatically)
    by_time: Dict[int, str] = {}

    # 1) reminders before the schedule start
    for off in style.get("before_start_minutes", []):
        t = start_min - off
        if t >= 0:
            by_time[t] = _prep_message(off, title, phrase)

    # 2) the departure (leave-time) reminder wins on any time collision
    if style.get("notify_at_leave", True):
        by_time[leave_min] = f"지금 출발하면 {title} 시간에 맞출 수 있습니다."

    # 3) late-prone users get an extra nudge shortly before leaving.
    #    The schema exposes "forgetful" as the late-prone signal; an explicit
    #    "late_prone" preference is honored too when present.
    late_prone = bool(getattr(pref, "late_prone", False)) or pref.forgetful
    if late_prone:
        extra = rules.get("late_prone_minutes_before_leave", 10)
        t = leave_min - extra
        if t >= 0 and t not in by_time:
            by_time[t] = f"곧 출발해야 합니다. {phrase} 다시 한 번 확인하세요."

    # naturally ordered by time
    return [
        NotificationItem(time=_to_hhmm(t), message=by_time[t])
        for t in sorted(by_time)
    ]


def build_departure_plan(req: DeparturePlanRequest) -> DeparturePlanData:
    sch, ctx, pref = req.schedule, req.context, req.user_preference

    checklist = _build_checklist((sch.category or "etc").lower(), ctx.weather)

    start_min = _to_min(sch.start_time)
    travel = max(0, ctx.estimated_travel_minutes)
    buffer = max(0, ctx.buffer_minutes)

    # Malformed start time -> safe partial response.
    if start_min is None:
        return DeparturePlanData(
            leave_time=None,
            estimated_travel_minutes=travel,
            buffer_minutes=buffer,
            checklist=checklist,
            notifications=[],
        )

    # leave_time = start - travel - buffer  (e.g. 14:00 - 35 - 10 = 13:15)
    leave_min = max(0, start_min - travel - buffer)
    leave_time = _to_hhmm(leave_min)

    notifications = _build_notifications(
        start_min, leave_min, pref, _items_phrase(checklist), sch.title
    )

    return DeparturePlanData(
        leave_time=leave_time,
        estimated_travel_minutes=travel,
        buffer_minutes=buffer,
        checklist=checklist,
        notifications=notifications,
    )
