"""Rule-based departure / preparation planner.

Computes recommended leave time, a preparation checklist (category + weather)
and notification times. Never raises: malformed time yields leave_time=None.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

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
    rules = _checklist_rules()
    cats = rules.get("categories", {})
    base = cats.get(category, cats.get("etc", []))
    items = [ChecklistItem(**x) for x in base]
    if weather:
        for x in rules.get("weather", {}).get(weather.lower(), []):
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

    leave_min = max(0, start_min - travel - buffer)
    leave_time = _to_hhmm(leave_min)

    # notification offsets (minutes before leave_time)
    style = pref.notification_style
    if pref.forgetful:
        style = _notification_rules().get("escalate_when_forgetful", "strong")
    offsets = _notification_rules().get("styles", {}).get(
        style, _notification_rules().get("styles", {}).get("normal", [30, 0])
    )

    phrase = _items_phrase(checklist)
    title = sch.title
    notifications: List[NotificationItem] = []
    for off in sorted(set(offsets), reverse=True):
        t = leave_min - off
        if t < 0:
            continue  # adjust: drop reminders that fall before midnight
        if off == 0:
            msg = f"지금 출발하면 {title} 시간에 맞출 수 있습니다."
        elif off >= 60:
            msg = f"{title} 준비를 시작할 시간입니다. {phrase} 미리 챙겨두세요."
        else:
            msg = f"{title} 전입니다. {phrase} 챙기세요."
        notifications.append(NotificationItem(time=_to_hhmm(t), message=msg))

    notifications.sort(key=lambda n: n.time)

    return DeparturePlanData(
        leave_time=leave_time,
        estimated_travel_minutes=travel,
        buffer_minutes=buffer,
        checklist=checklist,
        notifications=notifications,
    )
